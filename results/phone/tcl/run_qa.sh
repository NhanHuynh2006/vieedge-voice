#!/bin/bash
# TCL T506T: free questions without retrieval and history (the CPU-only defaults), 4 and 8 LLM threads, 0.8B and 2B.
set -u
O=results/phone/tcl
bench/phone_wavs.sh test_qa qwen3.5-0.8b-vi-voice-Q4_0.gguf none 12 $O/qa_08b_cpu_norag "--ez ack true --ez rag false --ei history 0"
bench/phone_wavs.sh test_qa qwen3.5-0.8b-vi-voice-Q4_0.gguf none 12 $O/qa_08b_cpu_norag_t8 "--ez ack true --ez rag false --ei history 0 --ei llmthreads 8"
bench/phone_wavs.sh test_qa qwen3.5-2b-vi-voice-Q4_0.gguf none 12 $O/qa_2b_cpu_norag "--ez ack true --ez rag false --ei history 0"
echo ALL DONE
