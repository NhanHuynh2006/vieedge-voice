#!/bin/bash
# Galaxy Z Fold7: the same battery as results/phone/tcl (07/11/2026), so both phones are measured with identical inputs.
set -u
O=results/phone/fold7
bench/phone_wavs.sh test_v45 qwen3.5-0.8b-vi-voice-Q4_0.gguf none 20 $O/stagebench "--ez stagebench true"
bench/phone_wavs.sh test_qa qwen3.5-0.8b-vi-voice-Q4_0.gguf none 12 $O/qa_08b_cpu_norag "--ez ack true --ez rag false --ei history 0"
bench/phone_wavs.sh test_qa qwen3.5-0.8b-vi-voice-Q4_0.gguf none 12 $O/qa_08b_cpu_rag "--ez ack true --ez rag true --ei history 0"
bench/phone_wavs.sh test_qa qwen3.5-0.8b-vi-voice-Q4_0.gguf HTP0 12 $O/qa_08b_npu_norag "--ez ack true --ez rag false --ei history 0"
bench/phone_wavs.sh test_qa qwen3.5-2b-vi-voice-Q4_0-imx.gguf HTP0 12 $O/qa_2b_npu_norag "--ez ack true --ez rag false --ei history 0"
bench/phone_wavs.sh test_qa qwen3.5-2b-vi-voice-Q4_0-imx.gguf HTP0 12 $O/qa_2b_npu_rag "--ez ack true --ez rag true --ei history 0"
bench/phone_wavs.sh test_qa qwen3.5-2b-vi-voice-Q4_0.gguf none 12 $O/qa_2b_cpu_norag "--ez ack true --ez rag false --ei history 0"
echo ALL DONE
