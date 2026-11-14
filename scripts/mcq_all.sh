#!/usr/bin/env bash
# Global-MMLU-vi (400 items, stratified) for every GGUF, grammar-constrained single-letter answers (laptop GPU).
set -uo pipefail
cd "$(dirname "$0")/.."
L="env -u PYTHONPATH .venv/bin/python bench/bench_llm.py -c deploy/config/vieedge-laptop.yaml --gpu --speed 0 --quality 400"
$L --exp M2q --models llm/gguf/qwen2.5-0.5b-Q4_K_M.gguf llm/gguf/qwen2.5-1.5b-Q4_K_M.gguf llm/gguf/qwen3-0.6b-Q4_K_M.gguf \
   llm/gguf/qwen3-1.7b-Q4_K_M.gguf llm/gguf/qwen3.5-0.8b-Q4_K_M.gguf llm/gguf/qwen3.5-2b-Q4_K_M.gguf llm/gguf/seallm-v3-1.5b-Q4_K_M.gguf \
   llm/gguf/gemma-4-e2b-Q4_K_M.gguf llm/gguf/qwen2.5-0.5b-vi-voice-Q4_K_M.gguf llm/gguf/qwen3.5-0.8b-vi-voice-Q4_K_M.gguf
for m in qwen2.5-1.5b-vi-voice qwen3.5-2b-vi-voice; do
  $L --exp M1q --models $(for q in F16 Q8_0 Q6_K Q5_K_M Q4_K_M Q3_K_M; do echo llm/gguf/$m-$q.gguf; done)
done
