#!/usr/bin/env bash
# GGUF for every LLM candidate without LoRA (M1/M2 baselines). Sequential to stay within 14 GB RAM.
set -uo pipefail
cd "$(dirname "$0")/.."
PY="env -u PYTHONPATH .venv/bin/python"
conv() { nice -n 10 $PY training/merge_quantize.py --base models/hf/$1 --name $2 --quants ${3:-Q4_K_M Q8_0} || echo "!! $2 failed"; }
conv Qwen__Qwen2.5-0.5B-Instruct qwen2.5-0.5b
conv Qwen__Qwen2.5-1.5B-Instruct qwen2.5-1.5b "Q4_K_M Q8_0"
conv Qwen__Qwen3-0.6B qwen3-0.6b
conv Qwen__Qwen3-1.7B qwen3-1.7b
conv Qwen__Qwen3.5-0.8B qwen3.5-0.8b
conv Qwen__Qwen3.5-2B qwen3.5-2b
conv SeaLLMs__SeaLLMs-v3-1.5B-Chat seallm-v3-1.5b
conv google__gemma-4-E2B-it gemma-4-e2b "Q4_K_M"
ls -la models/llm/gguf
