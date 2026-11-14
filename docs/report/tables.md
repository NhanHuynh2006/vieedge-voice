# Bảng kết quả (sinh tự động từ results/experiments.csv)

Tổng số dòng thí nghiệm: 125. Cột `os_cfg = laptop` là số đo trên laptop phát triển, không phải Raspberry Pi 5 (chỉ dùng cho chỉ số không phụ thuộc phần cứng như WER/độ chính xác).

## STT (S0–S5)

| exp_id | os_cfg | stt_model | stt_where | stt_prec | calib_lang | wer | wer_noisy | temp_max | notes |
|---|---|---|---|---|---|---|---|---|---|
| S0-ref | laptop | phowhisper-tiny-float32 | cpu | float32 | – | 0.2496 | 0.2793 | 79 | sets=vivos_test+fleurs_vi_test;n=300;lat_p50_ms=486;window=30s |
| S1-ref | laptop | phowhisper-tiny-int8 | cpu | int8 | – | 0.2504 | 0.2797 | 78 | sets=vivos_test+fleurs_vi_test;n=300;lat_p50_ms=334;window=30s |
| S1w-ref | laptop | phowhisper-tiny-int8 | cpu | int8 | – | 0.2033 | 0.2452 | 79 | sets=vivos_test+fleurs_vi_test;n=300;lat_p50_ms=222;window=10s |
| S3fp32-ref | laptop | phowhisper-tiny-encoder-10s.onnx | cpu-onnx+cpu | enc-FP32(ONNX)+dec-int8 | – | 0.2113 | 0.2436 | 77 | FP32 ONNX encoder (pre-HEF) + CT2 int8 decoder;sets=vivos_test+fleurs_vi_test;n=300;lat_p50_ms=176;window=10.0s |
| S1-base-ref | laptop | phowhisper-base-int8 | cpu | int8 | – | 0.2218 | 0.2424 | 83 | sets=vivos_test+fleurs_vi_test;n=300;lat_p50_ms=405;window=30s |
| S3fp32-base5s-ref | laptop | phowhisper-base-encoder-5s.onnx | cpu-onnx+cpu | enc-FP32(ONNX)+dec-int8 | – | 0.2351 | 0.2542 | 81 | sets=vivos_test+fleurs_vi_test;n=300;lat_p50_ms=295;window=5.0s |
| S3fp32-base10s-ref | laptop | phowhisper-base-encoder-10s.onnx | cpu-onnx+cpu | enc-FP32(ONNX)+dec-int8 | – | 0.1584 | 0.1861 | 79 | sets=vivos_test+fleurs_vi_test;n=300;lat_p50_ms=273;window=10.0s |
| S2cpu-ref | laptop | whisper-tiny-int8 | cpu | int8 | – | 0.6033 | 0.6713 | 78 | original Whisper tiny on CPU (S2 decoder weights);sets=vivos_test+fleurs_vi_test;n=300;lat_p50_ms=252;window=30s |
| S5-on-lap | laptop | phowhisper-tiny-encoder-10s.onnx | cpu | – | – | 0.3649 | – | 70 | manifest=e2e_synth;turns=30x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=9;file-audio |
| S5-off-lap | laptop | phowhisper-tiny-encoder-10s.onnx | cpu | – | – | 0.3621 | – | 71 | manifest=e2e_synth;turns=30x1sess;spec_hit=0.00;endpoint_ms=500;stream=True;first_words=9;file-audio |
| S6 | laptop | zipformer-vi-30M-int8 | cpu | int8 | – | 0.0414 | – | 89 | sherpa-onnx offline RNNT greedy; VIVOS only (FLEURS in its train set); lat_p50_ms=28.6;rtf_p50=0.0082; |

## LLM (M0–M5)

| exp_id | os_cfg | llm_model | llm_quant | lora | spec_dec | threads | ttft_ms | tok_s | ram_mb | llm_bench_acc | answer_score | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M2-gen | laptop | qwen2.5-1.5b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=1.3 |
| M2-gen | laptop | qwen2.5-1.5b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=1.0 |
| M2-gen | laptop | qwen2.5-0.5b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=0.8 |
| M2-gen | laptop | qwen2.5-0.5b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=1.0 |
| M2-gen | laptop | qwen3.5-2b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=1.5 |
| M2-gen | laptop | qwen3-1.7b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=2.0 |
| M2-gen | laptop | gemma-4-e2b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=4.5 |
| M2-gen | laptop | qwen3.5-0.8b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=1.3 |
| M2-gen | laptop | qwen3.5-2b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | – | – | gpu-offload(quality only);load_s=1.5 |
| M2 | laptop | gemma-4-e2b-Q4_K_M.gguf | – | no | – | – | – | – | – | – | 4.335 | judge=teacher;correct=4.438;concise=3.925;listen=4.643;halluc_rate=0.087;unknown_q_correct=4.78125;n=345 |
| M2 | laptop | qwen2.5-0.5b-Q4_K_M.gguf | – | no | – | – | – | – | – | – | 2.701 | judge=teacher;correct=2.551;concise=2.754;listen=2.797;halluc_rate=0.455;unknown_q_correct=3.78125;n=345 |
| M2 | laptop | qwen2.5-0.5b-vi-voice-Q4_K_M.gguf | – | yes | – | – | – | – | – | – | 3.201 | judge=teacher;correct=2.899;concise=3.13;listen=3.574;halluc_rate=0.443;unknown_q_correct=4.5625;n=345 |
| M2 | laptop | qwen2.5-1.5b-Q4_K_M.gguf | – | no | – | – | – | – | – | – | 3.331 | judge=teacher;correct=3.351;concise=3.18;listen=3.461;halluc_rate=0.328;unknown_q_correct=4.40625;n=345 |
| M2 | laptop | qwen2.5-1.5b-vi-voice-Q4_K_M.gguf | – | yes | – | – | – | – | – | – | 3.807 | judge=teacher;correct=3.574;concise=3.626;listen=4.22;halluc_rate=0.258;unknown_q_correct=4.6875;n=345 |
| M2 | laptop | qwen3-1.7b-Q4_K_M.gguf | – | no | – | – | – | – | – | – | 3.691 | judge=teacher;correct=3.412;concise=3.664;listen=3.997;halluc_rate=0.313;unknown_q_correct=3.65625;n=345 |
| M2 | laptop | qwen3.5-0.8b-vi-voice-Q4_K_M.gguf | – | yes | – | – | – | – | – | – | 3.632 | judge=teacher;correct=3.374;concise=3.551;listen=3.971;halluc_rate=0.325;unknown_q_correct=4.375;n=345 |
| M2 | laptop | qwen3.5-2b-Q4_K_M.gguf | – | no | – | – | – | – | – | – | 3.698 | judge=teacher;correct=3.742;concise=3.31;listen=4.041;halluc_rate=0.246;unknown_q_correct=4.25;n=345 |
| M2 | laptop | qwen3.5-2b-vi-voice-Q4_K_M.gguf | – | yes | – | – | – | – | – | – | 4.17 | judge=teacher;correct=4.017;concise=3.983;listen=4.51;halluc_rate=0.116;unknown_q_correct=4.6875;n=345 |
| M2q | laptop | qwen2.5-0.5b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | 0.315 | – | gpu-offload(quality only);load_s=0.8 |
| M2q | laptop | qwen2.5-1.5b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | 0.4175 | – | gpu-offload(quality only);load_s=1.0 |
| M2q | laptop | qwen3-0.6b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | 0.26 | – | gpu-offload(quality only);load_s=1.0 |
| M2q | laptop | qwen3-1.7b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | 0.455 | – | gpu-offload(quality only);load_s=1.3 |
| M2q | laptop | qwen3.5-0.8b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | 0.3275 | – | gpu-offload(quality only);load_s=1.3 |
| M2q | laptop | qwen3.5-2b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | 0.485 | – | gpu-offload(quality only);load_s=1.5 |
| M2q | laptop | seallm-v3-1.5b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | 0.3425 | – | gpu-offload(quality only);load_s=1.0 |
| M2q | laptop | gemma-4-e2b-Q4_K_M.gguf | Q4_K_M | no | no | 6 | – | – | – | 0.51 | – | gpu-offload(quality only);load_s=3.5 |
| M2q | laptop | qwen2.5-0.5b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | 0.3125 | – | gpu-offload(quality only);load_s=1.0 |
| M2q | laptop | qwen3.5-0.8b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | 0.3325 | – | gpu-offload(quality only);load_s=1.3 |
| M1q | laptop | qwen2.5-1.5b-vi-voice-F16.gguf | F16 | yes | no | 6 | – | – | – | 0.38 | – | gpu-offload(quality only);load_s=2.3 |
| M1q | laptop | qwen2.5-1.5b-vi-voice-Q8_0.gguf | Q8_0 | yes | no | 6 | – | – | – | 0.395 | – | gpu-offload(quality only);load_s=3.3 |
| M1q | laptop | qwen2.5-1.5b-vi-voice-Q6_K.gguf | Q6_K | yes | no | 6 | – | – | – | 0.3725 | – | gpu-offload(quality only);load_s=1.3 |
| M1q | laptop | qwen2.5-1.5b-vi-voice-Q5_K_M.gguf | Q5_K_M | yes | no | 6 | – | – | – | 0.3725 | – | gpu-offload(quality only);load_s=1.3 |
| M1q | laptop | qwen2.5-1.5b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | 0.3725 | – | gpu-offload(quality only);load_s=1.5 |
| M1q | laptop | qwen2.5-1.5b-vi-voice-Q3_K_M.gguf | Q3_K_M | yes | no | 6 | – | – | – | 0.3475 | – | gpu-offload(quality only);load_s=1.0 |
| M1q | laptop | qwen3.5-2b-vi-voice-F16.gguf | F16 | yes | no | 6 | – | – | – | 0.485 | – | gpu-offload(quality only);load_s=4.5 |
| M1q | laptop | qwen3.5-2b-vi-voice-Q8_0.gguf | Q8_0 | yes | no | 6 | – | – | – | 0.4825 | – | gpu-offload(quality only);load_s=2.3 |
| M1q | laptop | qwen3.5-2b-vi-voice-Q6_K.gguf | Q6_K | yes | no | 6 | – | – | – | 0.4975 | – | gpu-offload(quality only);load_s=1.8 |
| M1q | laptop | qwen3.5-2b-vi-voice-Q5_K_M.gguf | Q5_K_M | yes | no | 6 | – | – | – | 0.4725 | – | gpu-offload(quality only);load_s=1.5 |
| M1q | laptop | qwen3.5-2b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | 0.445 | – | gpu-offload(quality only);load_s=1.5 |
| M1q | laptop | qwen3.5-2b-vi-voice-Q3_K_M.gguf | Q3_K_M | yes | no | 6 | – | – | – | 0.37 | – | gpu-offload(quality only);load_s=1.5 |
| M1q-Q40 | laptop | qwen3.5-0.8b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | 0.3325 | – | gpu-offload(quality only);load_s=1.3 |
| M1q-Q40 | laptop | qwen3.5-0.8b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | 0.3325 | – | gpu-offload(quality only);load_s=1.3 |
| M1q-Q40 | laptop | qwen3.5-0.8b-vi-voice-Q4_0.gguf | Q4_0 | yes | no | 6 | – | – | – | 0.325 | – | gpu-offload(quality only);load_s=1.5 |
| M1q-Q40 | laptop | qwen3.5-0.8b-vi-voice-IQ4_NL.gguf | IQ4_NL | yes | no | 6 | – | – | – | 0.34 | – | gpu-offload(quality only);load_s=1.5 |
| M1q-Q40 | laptop | qwen3.5-0.8b-vi-voice-Q8_0.gguf | Q8_0 | yes | no | 6 | – | – | – | 0.3925 | – | gpu-offload(quality only);load_s=1.3 |
| M1q-Q40-f16 | laptop | qwen3.5-0.8b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | 0.3325 | – | gpu-offload(quality only);load_s=1.3 |
| M1q-Q40-f16 | laptop | qwen3.5-0.8b-vi-voice-Q4_0.gguf | Q4_0 | yes | no | 6 | – | – | – | 0.3075 | – | gpu-offload(quality only);load_s=1.3 |
| M1q-Q40-f16 | laptop | qwen3.5-0.8b-vi-voice-IQ4_NL.gguf | IQ4_NL | yes | no | 6 | – | – | – | 0.34 | – | gpu-offload(quality only);load_s=1.3 |
| M1q-Q40-f16 | laptop | qwen3.5-0.8b-vi-voice-Q8_0.gguf | Q8_0 | yes | no | 6 | – | – | – | 0.3925 | – | gpu-offload(quality only);load_s=1.5 |
| M1q-2B-Q40 | laptop | qwen3.5-2b-vi-voice-Q4_0.gguf | Q4_0 | yes | no | 6 | – | – | – | 0.4475 | – | gpu-offload(quality only);load_s=5.0 |
| M1q-2B-Q40 | laptop | qwen3.5-2b-vi-voice-Q4_0-old.gguf | – | yes | no | 6 | – | – | – | 0.45 | – | gpu-offload(quality only);load_s=1.8 |
| M1q-2B-Q40 | laptop | qwen3.5-2b-vi-voice-Q4_K_M.gguf | Q4_K_M | yes | no | 6 | – | – | – | 0.445 | – | gpu-offload(quality only);load_s=1.8 |
| M1q-2B-Q40 | laptop | qwen3.5-2b-vi-voice-Q8_0.gguf | Q8_0 | yes | no | 6 | – | – | – | 0.4825 | – | gpu-offload(quality only);load_s=2.3 |

## TTS (T0–T2)

| exp_id | os_cfg | threads | notes |
|---|---|---|---|
| tune-base | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=9;file-audio |
| tune-w5 | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=5;file-audio |
| tune-w3 | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=3;file-audio |
| tune-spec | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=5;file-audio |
| tune-08b | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=5;file-audio |
| tune-05b | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=5;file-audio |
| tune-stt-fixed10 | laptop | 2 | sets=vivos_test+fleurs_vi_test;n=150;lat_p50_ms=160;window=10s |
| tune-stt-adaptive | laptop | 2 | sets=vivos_test+fleurs_vi_test;n=150;lat_p50_ms=146;window=10s;REJECTED: adaptive window (3/5/8/10 s) doubled WER, code removed |
| tune-08b-ep350 | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=350;stream=True;first_words=5;file-audio |
| tune-08b-fa | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=5;file-audio |
| tune-final | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |
| tune-zip | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |
| tune-ab-ct2 | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |
| tune-ab-zip | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |
| tune-ab2-ct2 | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |
| tune-ab2-zip | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |
| tune-rag-off | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |
| tune-rag-on | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |
| tune-rag-small | laptop | 3 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio |

## Hệ thống (P1–P3)

| exp_id | os_cfg | stt_where | llm_model | first_audio_p50 | first_audio_p95 | first_audio_p99 | ttft_ms | tok_s | wer | power_w | j_per_turn | xruns_per_h | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P1-full-lap | laptop | cpu | qwen2.5-1.5b-vi-voice-Q4_K_M.gguf | 1756 | 2111 | 2168 | 124.7 | 51.76 | 0.3621 | – | – | 0 | manifest=e2e_synth;turns=30x1sess;spec_hit=1.00;endpoint_ms=500;stream=False;first_words=9;file-audio |
| P3-cpu-lap | laptop | cpu | qwen2.5-1.5b-vi-voice-Q4_K_M.gguf | 1388 | 1680 | 1844 | 121.8 | 50.88 | 0.3678 | – | – | 0 | manifest=e2e_synth;turns=30x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=9;file-audio |
| P3-noisy10dB-lap | laptop | cpu | qwen2.5-1.5b-vi-voice-Q4_K_M.gguf | 1366 | 1686 | 1743 | 125.4 | 51.38 | 0.3477 | – | – | 0 | manifest=e2e_synth_snr10;turns=30x1sess;spec_hit=1.00;endpoint_ms=500;stream=True;first_words=9;file-audio |
| PIOS-O1-ragfalse | O1 | cpu | qwen3.5-0.8b-vi-voice-Q4_K_M.gguf | 2324 | 3424 | 3482 | 357.6 | 11.96 | 0.3118 | 3.18 | 23.8 | 0 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio;device=pi5-piOS |
| PIOS-O1-ragtrue | O1 | cpu | qwen3.5-0.8b-vi-voice-Q4_K_M.gguf | 2974 | 4573 | 4604 | 1233 | 12.32 | 0.3441 | 3.3 | 27.9 | 0 | manifest=e2e_synth;turns=16x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio;device=pi5-piOS |
| PO0-CMD-fast | O0 | cpu | qwen3.5-0.8b-vi-voice-Q4_0.gguf | 526 | 5798 | 8900 | 555.2 | 12.78 | 0.4853 | 3.19 | 14.9 | 0 | manifest=e2e_cmd;turns=12x1sess;spec_hit=1.00;endpoint_ms=400;stream=True;first_words=5;file-audio;governor=ondemand;device=pi5-piOS-stock-O0 |

## Hệ điều hành (O0–O4)

_Chưa có số đo — chạy script tương ứng trên thiết bị._
