#!/usr/bin/env bash
# Same scheduling-latency test on any OS image (run as root on the Pi): cyclictest on core 3 at SCHED_FIFO 80, 1 kHz,
# idle / under stress-ng + real LLM inference pinned on cores 0-2. Prints max and p99.9-ish via the histogram.
#   sudo scripts/rt_compare.sh [seconds=60] [gguf]
D=${1:-60}; M=${2:-$(ls ~/vieedge/models/llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf /opt/vieedge/models/llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf 2>/dev/null | head -1)}
LB=$(command -v llama-bench || ls ~/llama.cpp/build/bin/llama-bench /usr/bin/llama-bench 2>/dev/null | head -1)
echo "kernel=$(uname -r) cfg=$(cat /etc/vieedge/env 2>/dev/null) governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
cyc() { cyclictest -m -q -a 3 -t1 -p 80 -i 1000 -D "$D" -h 1000 | awk '/Max Latencies/{mx=$NF} /Avg Latencies/{av=$NF} /Histogram Overflow/{ov=$NF} END{print "max_us="mx" avg_us="av" overflow>1ms="ov}'; }
echo -n "idle:        "; cyc
taskset -c 0-2 stress-ng --cpu 3 --vm 1 --vm-bytes 512M --io 1 --timeout $((D+10))s >/dev/null 2>&1 &
( while true; do taskset -c 0-2 "$LB" -m "$M" -t 3 -p 256 -n 128 -r 1 >/dev/null 2>&1; done ) & L=$!
sleep 5; echo -n "stress+LLM:  "; cyc
kill $L 2>/dev/null; wait $L 2>/dev/null; pkill -x stress-ng; pkill -x llama-bench; echo done
