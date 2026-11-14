#!/usr/bin/env bash
# Hardware-independent reference numbers on the laptop (rows get os_cfg=laptop): WER of every STT variant
# that does not need the NPU, incl. the FP32 ONNX encoder that is the input of the HEF compile
# (= upper bound for S3 before INT8). Latency columns from these rows are NOT Pi numbers.
set -uo pipefail
cd "$(dirname "$0")/.."
B="env -u PYTHONPATH nice -n 5 .venv/bin/python bench/bench_stt.py -c deploy/config/vieedge-laptop.yaml --limit 300 --snr 10"
$B --exp S0-ref --set stt.backend=ct2 --set stt.ct2.model=stt/ct2/phowhisper-tiny-float32 --set stt.ct2.compute_type=float32 --set stt.ct2.window_s=30
$B --exp S1-ref --set stt.backend=ct2 --set stt.ct2.window_s=30
$B --exp S1w-ref --set stt.backend=ct2 --set stt.ct2.window_s=10
$B --exp S3fp32-ref --set stt.backend=hybrid --set stt.hybrid.encoder=onnx --notes "FP32 ONNX encoder (pre-HEF) + CT2 int8 decoder"
$B --exp S1-base-ref --set stt.backend=ct2 --set stt.ct2.model=stt/ct2/phowhisper-base-int8 --set stt.ct2.window_s=30
$B --exp S3fp32-base5s-ref --set stt.backend=hybrid --set stt.hybrid.encoder=onnx --set stt.hybrid.onnx=stt/onnx/phowhisper-base-encoder-5s.onnx --set stt.hybrid.decoder=stt/ct2/phowhisper-base-int8
$B --exp S3fp32-base10s-ref --set stt.backend=hybrid --set stt.hybrid.encoder=onnx --set stt.hybrid.onnx=stt/onnx/phowhisper-base-encoder-10s.onnx --set stt.hybrid.decoder=stt/ct2/phowhisper-base-int8
$B --exp S2cpu-ref --set stt.backend=ct2 --set stt.ct2.model=stt/ct2/whisper-tiny-int8 --set stt.ct2.window_s=30 --notes "original Whisper tiny on CPU (S2 decoder weights)"
