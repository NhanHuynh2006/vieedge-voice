#!/usr/bin/env bash
# End-to-end run on the laptop restricted to 3 cores (Pi 5 has 3 "thinking" cores) with CPU-only STT/LLM/TTS.
# Absolute times are ~2-3x faster than the Pi; use it to compare *relative* gains of tuning options.
#   scripts/pi_like_e2e.sh <exp_id> [--set key=value ...]
set -uo pipefail
cd "$(dirname "$0")/.."
EXP=$1; shift
exec taskset -c 0-2 env -u PYTHONPATH .venv/bin/python bench/bench_e2e.py -c deploy/config/vieedge-laptop.yaml \
  --exp "$EXP" --manifest e2e_synth --turns "${TURNS:-16}" --sessions 1 --timeout 120 \
  --set os_cfg=laptop-3core --set stt.backend=ct2 --set stt.ct2.threads=2 --set llm.threads=3 --set tts.threads=1 \
  --set 'pipeline.preload_stt=[]' --set llm.model=llm/gguf/qwen2.5-1.5b-vi-voice-Q4_K_M.gguf "$@"
