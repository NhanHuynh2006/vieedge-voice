#!/usr/bin/env bash
# Everything after the Q&A set exists (PLAN §5.2, P3 of the roadmap), on the laptop GPU:
#   1. LoRA: Qwen2.5-1.5B (main), Qwen2.5-0.5B (small model for M2 + speculative draft for M3), Qwen3.5-0.8B
#   2. merge + GGUF quantisation ladder F16/Q8_0/Q6_K/Q5_K_M/Q4_K_M/Q3_K_M (+ imatrix)
#   3. knowledge accuracy (Global-MMLU vi, 400 items) for every candidate and quant  -> M1q rows (laptop, GPU)
#   4. spoken answers on the held-out Q&A test split + LLM judge                     -> M2 rows
# The teacher server (port 8090) must be stopped for steps 1-3 (VRAM) and running for step 4.
set -uo pipefail
cd "$(dirname "$0")/.."
PY="env -u PYTHONPATH .venv/bin/python"
STEP=${1:-all}
stop_teacher() { pkill -x llama-server 2>/dev/null; sleep 3; }
start_teacher() { (setsid nohup scripts/run_teacher.sh > results/logs/teacher-server.log 2>&1 &); for i in $(seq 100); do curl -sf localhost:8090/health >/dev/null && return; sleep 3; done; }

if [[ $STEP == all || $STEP == lora ]]; then
  stop_teacher
  $PY training/lora_train.py --base models/hf/Qwen__Qwen2.5-1.5B-Instruct --name qwen2.5-1.5b-vi-voice
  $PY training/lora_train.py --base models/hf/Qwen__Qwen2.5-0.5B-Instruct --name qwen2.5-0.5b-vi-voice
  $PY training/lora_train.py --base models/hf/Qwen__Qwen3.5-0.8B --name qwen3.5-0.8b-vi-voice --micro 2 || echo "!! qwen3.5-0.8b LoRA failed"
  # Qwen3.5-2B had the best Global-MMLU-vi of the base candidates (M2q) -> second main candidate
  $PY training/lora_train.py --base models/hf/Qwen__Qwen3.5-2B --name qwen3.5-2b-vi-voice --micro 2 || echo "!! qwen3.5-2b LoRA failed"
fi

if [[ $STEP == all || $STEP == quant ]]; then
  $PY training/merge_quantize.py --base models/hf/Qwen__Qwen2.5-1.5B-Instruct --lora training/runs/qwen2.5-1.5b-vi-voice/adapter \
      --name qwen2.5-1.5b-vi-voice --imatrix
  $PY training/merge_quantize.py --base models/hf/Qwen__Qwen2.5-0.5B-Instruct --lora training/runs/qwen2.5-0.5b-vi-voice/adapter \
      --name qwen2.5-0.5b-vi-voice --quants Q8_0 Q4_K_M
  [[ -d training/runs/qwen3.5-0.8b-vi-voice/adapter ]] && $PY training/merge_quantize.py --base models/hf/Qwen__Qwen3.5-0.8B \
      --lora training/runs/qwen3.5-0.8b-vi-voice/adapter --name qwen3.5-0.8b-vi-voice --quants Q8_0 Q4_K_M
  [[ -d training/runs/qwen3.5-2b-vi-voice/adapter ]] && $PY training/merge_quantize.py --base models/hf/Qwen__Qwen3.5-2B \
      --lora training/runs/qwen3.5-2b-vi-voice/adapter --name qwen3.5-2b-vi-voice --imatrix
fi

if [[ $STEP == all || $STEP == quality ]]; then
  stop_teacher
  scripts/mcq_all.sh     # grammar-constrained Global-MMLU-vi for all candidates + both quantisation ladders
fi

if [[ $STEP == all || $STEP == answers ]]; then
  stop_teacher
  $PY bench/bench_llm.py -c deploy/config/vieedge-laptop.yaml --gpu --speed 0 --answers 0 --exp M2 \
      --models llm/gguf/qwen2.5-1.5b-vi-voice-Q4_K_M.gguf llm/gguf/qwen2.5-1.5b-Q4_K_M.gguf llm/gguf/qwen2.5-0.5b-vi-voice-Q4_K_M.gguf \
               llm/gguf/qwen2.5-0.5b-Q4_K_M.gguf llm/gguf/qwen3.5-2b-Q4_K_M.gguf llm/gguf/qwen3-1.7b-Q4_K_M.gguf llm/gguf/gemma-4-e2b-Q4_K_M.gguf \
               $( [[ -f models/llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf ]] && echo llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf) \
               $( [[ -f models/llm/gguf/qwen3.5-2b-vi-voice-Q4_K_M.gguf ]] && echo llm/gguf/qwen3.5-2b-vi-voice-Q4_K_M.gguf)
  start_teacher
  $PY bench/judge.py results/raw/answers_M2_*.jsonl
fi
