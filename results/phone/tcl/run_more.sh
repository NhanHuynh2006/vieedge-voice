#!/bin/bash
# TCL T506T, second session: same per-stage benchmark and llama-bench as the Fold7, retrieval run with history 0.
set -u
O=results/phone/tcl
export ANDROID_SERIAL=JJVW69HMPFMZVGBQ
adb install -r dist/VieEdgeVoice-generic.apk | tail -1
adb shell pm grant vn.vieedge.voice android.permission.RECORD_AUDIO; adb shell pm grant vn.vieedge.voice android.permission.ACCESS_FINE_LOCATION
bench/phone_wavs.sh test_v45 qwen3.5-0.8b-vi-voice-Q4_0.gguf none 30 $O/stagebench "--ez stagebench true"
bench/phone_wavs.sh test_qa qwen3.5-0.8b-vi-voice-Q4_0.gguf none 12 $O/qa_08b_cpu_rag_h0 "--ez ack true --ez rag true --ei history 0"
# llama-bench, generic ARMv8.0 build, 4 threads (as the Fold7 CPU row) and 8 threads
adb shell mkdir -p /data/local/tmp/lb/lib /data/local/tmp/gguf
adb push third_party/llama.cpp/build-android-generic/bin/llama-bench /data/local/tmp/lb/ >/dev/null
for f in third_party/llama.cpp/build-android-generic/bin/*.so; do adb push $f /data/local/tmp/lb/lib/ >/dev/null; done
adb push models/llm/gguf/qwen3.5-0.8b-vi-voice-Q4_0.gguf models/llm/gguf/qwen3.5-2b-vi-voice-Q4_0.gguf /data/local/tmp/gguf/ >/dev/null
adb shell chmod 755 /data/local/tmp/lb/llama-bench
adb shell "cd /data/local/tmp/lb && LD_LIBRARY_PATH=lib ./llama-bench -m /data/local/tmp/gguf/qwen3.5-0.8b-vi-voice-Q4_0.gguf,/data/local/tmp/gguf/qwen3.5-2b-vi-voice-Q4_0.gguf -p 128 -n 64 -r 2 -t 4 2>/dev/null" > $O/llama_bench.md
adb shell "cd /data/local/tmp/lb && LD_LIBRARY_PATH=lib ./llama-bench -m /data/local/tmp/gguf/qwen3.5-0.8b-vi-voice-Q4_0.gguf -p 128 -n 64 -r 2 -t 8 2>/dev/null" > $O/llama_bench_t8.md
adb shell rm -rf /data/local/tmp/lb /data/local/tmp/gguf
echo ALL DONE
