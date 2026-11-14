#!/usr/bin/env bash
# O0-O4 measurements on the device (PLAN §6 "Hệ điều hành", §7.4). Run as root on the Pi:
#   OS_CFG=O4 ./os_bench.sh [minutes_per_test]
# Measures: boot -> "ready to listen", idle RAM/CPU, cyclictest + rtla timerlat max latency on the
# audio core (idle / stress-ng / real LLM load on cores 0-2), ALSA xruns per hour under LLM load,
# governor + throttling before/after. Results: results/os/<OS_CFG>-<date>/ and one experiments.csv row.
set -uo pipefail
MIN=${1:-5}
HERE="$(cd "$(dirname "$0")" && pwd)"
OS_CFG=${OS_CFG:-$( (grep -s VIEEDGE_OS_CFG /etc/vieedge/env || echo VIEEDGE_OS_CFG=unknown) | cut -d= -f2)}
RES=${VIEEDGE_RESULTS:-/opt/vieedge/results}
OUT="$RES/os/${OS_CFG}-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
CFG=${VIEEDGE_CONFIG:-/etc/vieedge/config.yaml}
PY=${PY:-python3}
LLAMA=${LLAMA_BENCH:-$(command -v llama-bench || echo ~/llama.cpp/build/bin/llama-bench)}
MODEL=${LLM_MODEL:-/opt/vieedge/models/llm/gguf/qwen2.5-1.5b-vi-voice-Q4_K_M.gguf}
AUDIO_CPU=3
LOAD_CPUS=0-2
DUR=$((MIN * 60))
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/log.txt"; }

thermal() { cat /sys/class/thermal/thermal_zone0/temp; (vcgencmd get_throttled 2>/dev/null || cat /sys/devices/platform/soc/soc:firmware/get_throttled 2>/dev/null); }
log "OS_CFG=$OS_CFG kernel=$(uname -r) $(uname -v)"; vieedge-tune status > "$OUT/tune_status.txt" 2>&1 || true
thermal > "$OUT/thermal_before.txt"

# ---------------- boot time & idle footprint
log "boot"
systemd-analyze > "$OUT/systemd-analyze.txt" 2>&1 || true
systemd-analyze blame 2>/dev/null | head -20 > "$OUT/blame.txt" || true
READY=$(cat /run/vieedge-ready 2>/dev/null | cut -d' ' -f1)
if [[ -n "$READY" ]]; then
  BOOT_T=$(awk -v r="$READY" -v now="$(date +%s.%N)" -v up="$(cut -d' ' -f1 /proc/uptime)" 'BEGIN{printf "%.2f", r-(now-up)}')
  log "kernel start -> assistant ready: ${BOOT_T}s"
fi
log "idle footprint (assistant running, nobody talking) 60 s"
free -m > "$OUT/free_idle.txt"
vmstat 1 60 > "$OUT/vmstat_idle.txt"

# ---------------- latency tests
run_cyclic() {  # $1 = tag
  cyclictest -m -q -a $AUDIO_CPU -t1 -p 80 -i 1000 -D $DUR -h 2000 > "$OUT/cyclictest_$1.txt" 2>&1
  grep -E "Max Latencies" "$OUT/cyclictest_$1.txt" | awk '{print $NF}'
}
run_timerlat() {
  if command -v rtla >/dev/null; then
    rtla timerlat top -c $AUDIO_CPU -d ${DUR}s -q > "$OUT/timerlat_$1.txt" 2>&1 || true
  fi
}
llm_load_start() {  # real LLM inference on cores 0-2 in a loop
  ( while true; do taskset -c $LOAD_CPUS "$LLAMA" -m "$MODEL" -t 3 -p 256 -n 128 -r 1 > /dev/null 2>&1; done ) &
  LOADPID=$!
}
llm_load_stop() { kill $LOADPID 2>/dev/null; pkill -x llama-bench 2>/dev/null; wait $LOADPID 2>/dev/null; }

systemctl stop vieedge 2>/dev/null   # free the sound card + cores for the synthetic tests
log "cyclictest idle";  C_IDLE=$(run_cyclic idle)
log "  max ${C_IDLE} us"
log "cyclictest under stress-ng (cores 0-2)"
taskset -c $LOAD_CPUS stress-ng --cpu 3 --vm 1 --vm-bytes 512M --io 1 --timeout ${DUR}s > /dev/null 2>&1 &
C_STRESS=$(run_cyclic stress); wait
log "  max ${C_STRESS} us"
log "cyclictest + rtla timerlat under real LLM load"
llm_load_start; C_LLM=$(run_cyclic llm); llm_load_stop
log "  max ${C_LLM} us"
llm_load_start; run_timerlat llm; llm_load_stop

# ---------------- xruns under LLM load (same RT audio process as the assistant)
log "ALSA xruns under LLM load"
llm_load_start
XR=$($PY "$HERE/xrun_test.py" -c "$CFG" --minutes "$MIN" --tag llm-load | tail -1)
llm_load_stop
echo "$XR" > "$OUT/xruns.json"
XRH=$(echo "$XR" | $PY -c "import json,sys;print(round(json.load(sys.stdin)['xruns_per_h'],2))" 2>/dev/null || echo "")
log "  xruns/h: $XRH"

# ---------------- LLM throughput under this OS (RT may cost a little — report honestly)
TOKS=$(taskset -c $LOAD_CPUS "$LLAMA" -m "$MODEL" -t 3 -p 128 -n 128 -r 3 -o json 2>/dev/null | $PY -c "
import json,sys
d=json.load(sys.stdin); print(round([x for x in d if x.get('n_gen',0)>0][0]['avg_ts'],2))" 2>/dev/null || echo "")
log "llama-bench tg128 tokens/s: $TOKS"
thermal > "$OUT/thermal_after.txt"
systemctl start vieedge 2>/dev/null

$PY - "$OUT" "$OS_CFG" "${C_IDLE:-}" "${C_STRESS:-}" "${C_LLM:-}" "${XRH:-}" "${TOKS:-}" "${BOOT_T:-}" "$HERE" <<'PYEOF'
import sys
sys.path.insert(0, sys.argv[9])
from common import append_experiment
out, osc, ci, cs, cl, xr, toks, boot = sys.argv[1:9]
idle = open(f"{out}/free_idle.txt").read().splitlines()[1].split()
append_experiment({"exp_id": osc, "os_cfg": osc, "cyclictest_max_us": cl, "xruns_per_h": xr, "tok_s": toks,
                   "ram_mb": idle[2],
                   "notes": f"cyclictest_max_us idle={ci} stress={cs} llm={cl};boot_to_ready_s={boot};dir={out}"},
                  raw={"dir": out})
PYEOF
log "done -> $OUT"
