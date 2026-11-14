#!/bin/bash
# Plays the wavs of one folder in the app's files/ through the full on-device pipeline (adb test hook) and saves the log.
#   ANDROID_SERIAL=<id> bench/phone_wavs.sh <folder> <model.gguf> <device: HTP0|GPUOpenCL|none> <warm s> <out prefix> [extras]
set -u
F=$1; M=$2; DEV=$3; WARM=$4; OUT=$5; EXTRA=${6:-}   # EXTRA: more am-start extras, e.g. "--ei asrthreads 4 --ez hotwords false"
W=$(adb shell run-as vn.vieedge.voice ls files/$F </dev/null | tr -d '\r' | sed "s|^|/data/user/0/vn.vieedge.voice/files/$F/|" | paste -sd, -)
adb logcat -G 16M </dev/null; adb shell run-as vn.vieedge.voice rm -f files/turns.jsonl </dev/null; adb logcat -c
adb shell am start -S -n vn.vieedge.voice/.MainActivity --es model "$M" --es device "$DEV" --ei warm "$WARM" $EXTRA --es wavs "$W" >/dev/null </dev/null
t0=$(date +%s); peak=0
while ! adb logcat -d | grep -qE "VieEdge.*TEST done|VieEdge.*STAGEBENCH|FATAL EXCEPTION|VieEdge.*TEST start.*err=[^n]"; do
  sleep 10
  kb=$(adb shell dumpsys meminfo vn.vieedge.voice </dev/null | awk '/TOTAL PSS:/{print $3; exit} /TOTAL:/{print $2; exit}')
  [ -n "$kb" ] && [ "$kb" -gt "$peak" ] 2>/dev/null && peak=$kb
  [ $(( $(date +%s) - t0 )) -gt 3000 ] && { echo TIMEOUT; break; }
done
adb logcat -d | grep -E "TEST start|TEST turn|TEST done|STAGEBENCH|FATAL|AndroidRuntime" > "$OUT.log"
adb shell run-as vn.vieedge.voice cat files/turns.jsonl > "$OUT.turns.jsonl" </dev/null
echo "peak_pss_kb=$peak temp=$(adb shell dumpsys battery </dev/null | awk '/ temperature:/{print $2/10; exit}') elapsed_s=$(( $(date +%s) - t0 ))" | tee "$OUT.meta"
grep -E "TEST start|FATAL" "$OUT.log" | head -3
