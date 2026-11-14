#!/bin/bash
# non-invasive: nothing installed, output in /tmp. idle + stress-ng (cores 0-2) + 40% spinner on core 3, cyclictest on core 3
D=${1:-300}
pct() { python3 - "$1" <<'P'
import sys,re
rows=[l.split() for l in open(sys.argv[1]) if re.match(r'^\d+\s+\d+',l)]
h=[(int(r[0]),int(r[1])) for r in rows]; n=sum(c for _,c in h); out={}
for q in (0.99,0.9999,0.99999):
    a=0
    for us,c in h:
        a+=c
        if a>=q*n: out[q]=us;break
mx=[l for l in open(sys.argv[1]) if 'Max Latencies' in l]
print("samples=%d max_us=%s p99=%s p99.99=%s p99.999=%s"%(n,mx[0].split()[-1] if mx else -1,out.get(0.99),out.get(0.9999),out.get(0.99999)))
P
}
echo "kernel=$(uname -r) governor=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) temp=$(cat /sys/class/thermal/thermal_zone0/temp)"
cyclictest -m -q -a 3 -t1 -p 80 -i 1000 -D $D -h 5000 > /tmp/cyc_idle.txt 2>&1; echo "idle: $(pct /tmp/cyc_idle.txt)"
taskset -c 0-2 stress-ng --cpu 3 --vm 1 --vm-bytes 512M --io 2 --sched 0 --timeout $((D+20))s >/dev/null 2>&1 &
taskset -c 3 stress-ng --cpu 1 --cpu-load 40 --timeout $((D+20))s >/dev/null 2>&1 &
sleep 8; cyclictest -m -q -a 3 -t1 -p 80 -i 1000 -D $D -h 5000 > /tmp/cyc_load.txt 2>&1; echo "stress: $(pct /tmp/cyc_load.txt)"
for p in $(pgrep -x stress-ng); do kill $p; done
echo "temp_after=$(cat /sys/class/thermal/thermal_zone0/temp)"; echo JIT_DONE
