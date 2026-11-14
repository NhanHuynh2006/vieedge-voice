#!/usr/bin/env bash
# LoRA robust to speech-recognition errors (Mousavi et al. 2024; Sun et al. 2023) vs the clean-text LoRA.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
PY="env -u PYTHONPATH $ROOT/.venv/bin/python"
pkill -x llama-server 2>/dev/null; sleep 3
B=llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf
N=llm/gguf/qwen3.5-0.8b-vi-voice-asr-Q4_K_M.gguf
(cd bench && $PY eval_noisy_qa.py $B)
$PY training/lora_train.py --base models/hf/Qwen__Qwen3.5-0.8B --name qwen3.5-0.8b-vi-voice-asr --micro 2 --epochs 2 --asr-aug
$PY training/merge_quantize.py --base models/hf/Qwen__Qwen3.5-0.8B --lora training/runs/qwen3.5-0.8b-vi-voice-asr/adapter \
    --name qwen3.5-0.8b-vi-voice-asr --quants Q4_K_M
(cd bench && $PY eval_noisy_qa.py $N)
(setsid nohup scripts/run_teacher.sh > results/logs/teacher-server.log 2>&1 &)
for i in $(seq 100); do curl -sf localhost:8090/health >/dev/null && break; sleep 3; done
$PY bench/judge.py results/raw/answers_CLEAN_qwen3.5-0.8b-vi-voice-*.jsonl results/raw/answers_NOISY_qwen3.5-0.8b-vi-voice-*.jsonl
pkill -x llama-server
echo PIPELINE-DONE
