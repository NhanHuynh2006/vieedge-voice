# Tài liệu tham khảo

## Bài báo
1. A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, I. Sutskever. *Robust Speech Recognition via Large-Scale Weak Supervision* (Whisper). ICML 2023.
2. T.-T. Le, L. T. Nguyen, D. Q. Nguyen. *PhoWhisper: Automatic Speech Recognition for Vietnamese*. ICLR 2024 Tiny Papers. arXiv:2406.02555.
3. J. Kim, J. Kong, J. Son. *Conditional Variational Autoencoder with Adversarial Learning for End-to-End Text-to-Speech* (VITS). ICML 2021.
4. E. Frantar, S. Ashkboos, T. Hoefler, D. Alistarh. *GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers*. ICLR 2023.
5. G. Xiao, J. Lin, M. Seznec, H. Wu, J. Demouth, S. Han. *SmoothQuant*. ICML 2023.
6. J. Lin et al. *AWQ: Activation-aware Weight Quantization for LLM Compression and Acceleration*. MLSys 2024.
7. E. J. Hu et al. *LoRA: Low-Rank Adaptation of Large Language Models*. ICLR 2022. — T. Dettmers et al. *QLoRA*. NeurIPS 2023.
8. Y. Leviathan, M. Kalman, Y. Matias. *Fast Inference from Transformers via Speculative Decoding*. ICML 2023.
9. S. Laskaridis et al. *MELTing Point: Mobile Evaluation of Language Transformers*. MobiCom 2024.
10. T. Stivers et al. *Universals and cultural variation in turn-taking in conversation*. PNAS 2009.
11. F. Reghenzani, G. Massari, W. Fornaciari. *The Real-Time Linux Kernel: A Survey on PREEMPT_RT*. ACM Computing Surveys 2019.
12. De Wit, Paolillo. *A Preliminary Assessment of the Real-Time Capabilities of Real-Time Linux on Raspberry Pi 5*. OSPERT 2024.
13. S. Singh et al. *Global MMLU: Understanding and Addressing Cultural and Linguistic Biases in Multilingual Evaluation*. 2024 (bộ Global-MMLU).

## Phần mềm (phiên bản dùng trong dự án)
| Thành phần | Phiên bản / commit | Giấy phép |
|---|---|---|
| hailocs/hailo-whisper | `ebe7a853` (+ openai/whisper `517a43e` với patch Hailo) | MIT |
| hailo-apps speech_recognition (tham khảo API InferModel, URL HEF) | main 2026-10 | MIT |
| Hailo HEF Whisper tiny/base cho Hailo-8L | S3 hailo-csdata (resources_config.yaml) | theo Hailo |
| HailoRT / hailo-pci / firmware (meta-hailo `hailo8-scarthgap`) | 4.24.0 | MIT / GPL-2.0 / Hailo |
| Hailo Dataflow Compiler | 3.x (🧑 tải từ Developer Zone) | độc quyền Hailo |
| llama.cpp | v0.5.0 `7fe450e1` | MIT |
| CTranslate2 | 4.8.2 | MIT |
| ONNX Runtime | 1.30.0 | MIT |
| espeak-ng | 1.52.0 | GPL-3.0+ |
| Piper voices vi_VN (vais1000-medium, 25hours_single-low, vivos-x_low) | rhasspy/piper-voices | xem MODEL_CARD từng giọng |
| sherpa-onnx (chạy Zipformer-vi) | 1.13.8 | Apache-2.0 |
| Silero VAD | silero-vad (ONNX) | MIT |
| OpenBLAS | 0.3.34 | BSD-3 |
| Yocto Poky / meta-openembedded / meta-raspberrypi | scarthgap (5.0.x) | MIT / nhiều |
| ktomanek/edge_whisper (số liệu tham khảo encoder-NPU/decoder-CPU) | – | – |

## Mô hình
| Mô hình | Vai trò | Giấy phép |
|---|---|---|
| vinai/PhoWhisper-tiny, -base | STT tiếng Việt | BSD-3-Clause |
| openai/whisper-tiny, -base | baseline S2 | MIT |
| Qwen/Qwen2.5-1.5B-Instruct, Qwen2.5-0.5B-Instruct | LLM chính + draft | Apache-2.0 |
| Qwen/Qwen3-1.7B, Qwen3-0.6B, Qwen3.5-0.8B, Qwen3.5-2B | ứng viên | Apache-2.0 |
| google/gemma-4-E2B-it | ứng viên | Apache-2.0 |
| SeaLLMs/SeaLLMs-v3-1.5B-Chat | ứng viên Đông Nam Á | SeaLLMs license |
| hynt/Zipformer-30M-RNNT-6000h (STT tiếng Việt, int8) | STT mặc định | CC BY-NC-ND 4.0 (phi thương mại, không chỉnh sửa) |
| Qwen3.5-9B (GGUF Q4_K_M, unsloth) | teacher / giám khảo trên laptop | Apache-2.0 |

## Dữ liệu
| Bộ | Giấy phép | Ghi chú |
|---|---|---|
| VIVOS | CC BY-NC-SA 4.0 | phi thương mại — phù hợp nghiên cứu/thi |
| FLEURS vi_vn | CC BY 4.0 | thay Common Voice (không còn trên HF Hub) |
| LibriSpeech dev-clean | CC BY 4.0 | hiệu chỉnh tiếng Anh |
| DEMAND | CC BY 4.0 | tạp âm |
| Global-MMLU (vi) | Apache-2.0 | benchmark chính |
| Wikipedia tiếng Việt (wikimedia/wikipedia 20231101.vi) | CC BY-SA 3.0 / GFDL | kho tri thức offline của RAG (200.000 bài dài nhất, 1,7 triệu đoạn) |
| VMLU validation (bản sao vilm/vmlu_val) | chưa xác minh | chỉ dùng nội bộ, không công bố số liệu nếu chưa xác minh giấy phép với vmlu.ai |
