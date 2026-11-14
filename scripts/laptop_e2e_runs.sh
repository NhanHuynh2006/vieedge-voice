#!/usr/bin/env bash
# End-to-end validation on the laptop (file audio, ONNX encoder instead of the HEF, llama.cpp on CPU).
# Rows are labelled os_cfg=laptop: they show the ablations work and their direction, NOT Pi latencies.
set -uo pipefail
cd "$(dirname "$0")/.."
E="env -u PYTHONPATH nice .venv/bin/python bench/bench_e2e.py -c deploy/config/vieedge-laptop.yaml --manifest e2e_synth --turns 30 --sessions 1"
M="--set llm.model=llm/gguf/qwen2.5-1.5b-vi-voice-Q4_K_M.gguf"
$E --exp S5-on-lap $M
$E --exp S5-off-lap $M --set stt.incremental.enabled=false
$E --exp P1-full-lap $M --set pipeline.stream_sentences=false
$E --exp P3-cpu-lap $M --set stt.backend=ct2
$E --exp P3-noisy10dB-lap $M --manifest e2e_synth_snr10
