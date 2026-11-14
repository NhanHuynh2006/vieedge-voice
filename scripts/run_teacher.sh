#!/usr/bin/env bash
# Teacher / judge LLM on the laptop GPU (llama.cpp Vulkan build; CUDA 13.1 nvcc is broken with glibc 2.43).
# -lm none: weights uploaded to VRAM, host copy freed (mmap kept ~9 GB resident -> OOM on 14 GB RAM).
# --cache-ram 256: the host-side prompt cache defaults to 8 GiB and grew the process to 8 GB again.
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL="${TEACHER_MODEL:-models/teacher/Qwen3.5-9B-Q4_K_M.gguf}"
REASONING="${REASONING:-off}"   # "on" for the fact-check pass of gen_qa.py --verify and judge.py
exec third_party/llama.cpp/build/bin/llama-server -m "$MODEL" --host 127.0.0.1 --port 8090 -ngl 99 -c 16384 -np 4 \
  --jinja -rea "$REASONING" --no-webui -lm none --cache-ram 256
