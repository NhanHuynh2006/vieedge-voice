#!/usr/bin/env bash
# Identical benchmark suite for the OS comparison (Pi OS vs Yocto, O1/O2/O4), run as root ON the Pi:
#   sudo bench/compare_os.sh <tag> [minutes_per_latency_test=5]      e.g. tag = PIOS-O1 | YOCTO-O2 | YOCTO-RT-O4
# Same board, same models, same config, same tests, cooled to the same start temperature. Output: results/jitter_long/<tag>-<date>/
#  1. static   : kernel, rootfs size, boot time, RAM after boot, idle CPU
#  2. jitter   : cyclictest (core 3, SCHED_FIFO 80, 1 kHz) idle and under heavy load -> max / p99 / p99.99 / p99.999
#  3. e2e      : 16 question turns, quiet and with a noisy neighbour on all cores -> first-audio p50/p95
set -uo pipefail
TAG=${1:?tag}; MIN=${2:-5}; DUR=$((MIN*60))
HERE="$(cd "$(dirname "$0")" && pwd)"; SRC="$(dirname "$HERE")"
OUT="$SRC/results/jitter_long/$TAG-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$OUT"
for d in ~/vieedge /opt/vieedge; do [[ -d $d/models ]] && VROOT=$d && break; done
M=$(ls $VROOT/models/llm/gguf/qwen3.5-0.8b-vi-voice-Q4_0.gguf $VROOT/models/llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf 2>/dev/null | head -1)
[[ -n $M ]] || { echo "no GGUF found under $VROOT/models/llm/gguf"; exit 1; }
LB=$(command -v llama-bench || ls ~/vieedge/llama.cpp/build/bin/llama-bench ~/llama.cpp/build/bin/llama-bench 2>/dev/null | head -1)
PY=$(ls $VROOT/venv/bin/python 2>/dev/null || command -v python3)
CFG=${VIEEDGE_CONFIG:-/etc/vieedge/config.yaml}
log() { echo "[$(date +%T)] $*" | tee -a "$OUT/log.txt"; }
systemctl stop vieedge 2>/dev/null; sleep 5
cool() { while [[ $(cat /sys/class/thermal/thermal_zone0/temp) -gt 55000 ]]; do sleep 10; done; }

cool(){ while [[ $(cat /sys/class/thermal/thermal_zone0/temp) -gt 55000 ]]; do sleep 10; done; }
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
log "jitter under heavy load ${MIN} min"; cool; heavy_start; sleep 10; cyc load; heavy_stop

echo COMPARE_DONE
