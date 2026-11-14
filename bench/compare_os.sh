#!/usr/bin/env bash
# Identical benchmark suite for the OS comparison (Pi OS vs Yocto, O1/O2/O4), run as root ON the Pi:
#   sudo bench/compare_os.sh <tag> [minutes_per_latency_test=5]      e.g. tag = PIOS-O1 | YOCTO-O2 | YOCTO-RT-O4
# Same board, same models, same config, same tests, cooled to the same start temperature. Output: results/compare/<tag>-<date>/
#  1. static   : kernel, rootfs size, boot time, RAM after boot, idle CPU
#  2. jitter   : cyclictest (core 3, SCHED_FIFO 80, 1 kHz) idle and under heavy load -> max / p99 / p99.99 / p99.999
#  3. e2e      : 16 question turns, quiet and with a noisy neighbour on all cores -> first-audio p50/p95
set -uo pipefail
TAG=${1:?tag}; MIN=${2:-5}; DUR=$((MIN*60))
HERE="$(cd "$(dirname "$0")" && pwd)"; SRC="$(dirname "$HERE")"
OUT="$SRC/results/compare/$TAG-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$OUT"
for d in ~/vieedge /opt/vieedge; do [[ -d $d/models ]] && VROOT=$d && break; done
M=$(ls $VROOT/models/llm/gguf/qwen3.5-0.8b-vi-voice-Q4_0.gguf $VROOT/models/llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf 2>/dev/null | head -1)
[[ -n $M ]] || { echo "no GGUF found under $VROOT/models/llm/gguf"; exit 1; }
LB=$(command -v llama-bench || ls ~/vieedge/llama.cpp/build/bin/llama-bench ~/llama.cpp/build/bin/llama-bench 2>/dev/null | head -1)
PY=$(ls $VROOT/venv/bin/python 2>/dev/null || command -v python3)
CFG=${VIEEDGE_CONFIG:-/etc/vieedge/config.yaml}
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/log.txt"; }
systemctl stop vieedge 2>/dev/null; sleep 5
cool() { while [[ $(cat /sys/class/thermal/thermal_zone0/temp) -gt 55000 ]]; do sleep 10; done; }

# ---- 1. static
{ echo "tag=$TAG"; echo "kernel=$(uname -r)"; uname -v; echo "cmdline=$(cat /proc/cmdline)"; echo "governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
  echo "rootfs_used_MB=$(df -m / | awk 'NR==2{print $3}')"; echo "uptime_s=$(cut -d' ' -f1 /proc/uptime)"
  free -m | sed -n 2p | awk '{print "ram_used_MB="$3" ram_available_MB="$7}'
  echo "procs=$(ps -e --no-headers | wc -l)"; echo "systemd_units_running=$(systemctl list-units --state=running --no-legend 2>/dev/null | wc -l)"
  systemd-analyze 2>/dev/null | head -1; } > "$OUT/static.txt"
vmstat 1 30 | tail -n +3 | awk '{u+=$13;s+=$14;i+=$15;n++} END{printf "idle_cpu_busy_pct=%.1f\n", 100-i/n}' >> "$OUT/static.txt"
cat "$OUT/static.txt" | tee -a "$OUT/log.txt" >/dev/null

# ---- 2. jitter
pct() { python3 - "$1" <<'P'
import sys,re
rows=[l.split() for l in open(sys.argv[1]) if re.match(r'^\d+\s+\d+',l)]
h=[(int(r[0]),int(r[1])) for r in rows]
n=sum(c for _,c in h); mx=0; out={}
for q in (0.99,0.9999,0.99999):
    acc=0
    for us,c in h:
        acc+=c
        if acc>=q*n: out[q]=us;break
mxl=[l for l in open(sys.argv[1]) if 'Max Latencies' in l]
mx=int(mxl[0].split()[-1]) if mxl else -1
print(f"samples={n} max_us={mx} p99_us={out.get(0.99)} p99.99_us={out.get(0.9999)} p99.999_us={out.get(0.99999)}")
P
}
cyc() { [[ $1 == idle ]] && cool; cyclictest -m -q -a 3 -t1 -p 80 -i 1000 -D "$DUR" -h 5000 > "$OUT/cyclictest_$1.txt" 2>&1; log "cyclictest $1: $(pct "$OUT/cyclictest_$1.txt")"; }
heavy_start() {  # noisy neighbour: CPU+memory+disk+scheduler stress and real LLM inference on cores 0-2, plus one spinner on the audio core
  taskset -c 0-2 stress-ng --cpu 3 --vm 1 --vm-bytes 512M --io 2 --hdd 1 --sched 0 --timeout $((DUR+120))s > /dev/null 2>&1 & echo $! > "$OUT/.stress"
  ( while true; do taskset -c 0-2 "$LB" -m "$M" -t 3 -p 256 -n 128 -r 1 > /dev/null 2>&1; done ) & echo $! > "$OUT/.llm"
  taskset -c 3 stress-ng --cpu 1 --cpu-load 40 --timeout $((DUR+120))s > /dev/null 2>&1 & echo $! > "$OUT/.core3"
}
heavy_stop() { kill $(cat "$OUT/.llm") 2>/dev/null; kill $(cat "$OUT/.stress") $(cat "$OUT/.core3") 2>/dev/null; pkill -x llama-bench; pkill -x stress-ng; sleep 3; }
log "jitter idle ${MIN} min";  cyc idle
log "jitter under heavy load ${MIN} min"; cool; heavy_start; sleep 10; cyc load; heavy_stop

# ---- 3. end-to-end first-audio latency
e2e() {  # $1 exp suffix
  [[ $1 == quiet ]] && cool; cd "$SRC/bench" && taskset -c 0-3 $PY bench_e2e.py -c "$CFG" --exp "CMP-$TAG-$1" --manifest e2e_synth --turns 16 --sessions 1 --timeout 240 \
    --set rag.enabled=false --set pipeline.ack.enabled=false --set fastpath.enabled=false --set os_cfg=$TAG > "$OUT/e2e_$1.txt" 2>&1
  log "e2e $1: $(tail -1 "$SRC/results/experiments.csv" | cut -d, -f1,17-22 )"
}
e2e quiet
taskset -c 0-2 stress-ng --cpu 3 --vm 1 --vm-bytes 512M --io 2 --timeout 3000s > /dev/null 2>&1 & ST=$!
taskset -c 3 stress-ng --cpu 1 --cpu-load 40 --timeout 3000s > /dev/null 2>&1 & ST2=$!
e2e loaded; kill $ST $ST2 2>/dev/null; pkill -x stress-ng
log "DONE -> $OUT"; echo COMPARE_DONE
