#!/bin/bash
# TCL T506T test battery (07/11/2026), run from the repo root with ANDROID_SERIAL set.
set -u
O=results/phone/tcl
bench/phone_wavs.sh test_v3  qwen3.5-0.8b-vi-voice-Q4_0.gguf none 1 $O/safety_v3_08b_cpu
bench/phone_wavs.sh test_v45 qwen3.5-0.8b-vi-voice-Q4_0.gguf none 1 $O/safety_v45_08b_cpu_t4 "--ei asrthreads 4"
bench/phone_wavs.sh test_v45 qwen3.5-0.8b-vi-voice-Q4_0.gguf none 1 $O/safety_v45_08b_cpu_greedy_t4 "--ei asrthreads 4 --ez hotwords false"
bench/phone_wavs.sh test_qa  qwen3.5-0.8b-vi-voice-Q4_0.gguf none 12 $O/qa_08b_cpu "--ez ack true"
bench/phone_wavs.sh test_qa  qwen3.5-2b-vi-voice-Q4_0.gguf none 12 $O/qa_2b_cpu "--ez ack true"
echo ALL DONE
