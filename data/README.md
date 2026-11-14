# data/ (không commit — PLAN §16)

Tải lại bằng `python scripts/download_data.py` (manifest JSONL trong `data/manifests/`).

| Thư mục | Nguồn | Giấy phép | Dùng cho |
|---|---|---|---|
| asr_test/vivos | VIVOS (AILAB, ĐHQG-HCM) — test 760 câu, train 11 660 câu | CC BY-NC-SA 4.0 | WER (test), hiệu chỉnh INT8 (train) |
| asr_test/fleurs_vi | Google FLEURS vi_vn — test 857, train 2 994 | CC BY 4.0 | WER (test), hiệu chỉnh (train) |
| calib/librispeech | LibriSpeech dev-clean | CC BY 4.0 | hiệu chỉnh tiếng Anh (ablation S4) |
| noise/demand | DEMAND 16 kHz: PCAFETER, PRESTO, PSTATION, OMEETING | CC BY 4.0 | WER trong ồn SNR 20/10/5 dB |
| llm_bench | Global-MMLU `vi` (CohereLabs) | Apache-2.0 | kiến thức LLM theo mức lượng tử |
| llm_bench/vmlu_val | bản sao tập validation VMLU (vilm/vmlu_val) | chưa ghi giấy phép → chỉ dùng nội bộ | tín hiệu phụ |
| qa | tự sinh bằng teacher (training/gen_qa.py) | của nhóm | LoRA (train 90 %) + đánh giá (test 10 %) |
| e2e | câu hỏi nói (tổng hợp hoặc 🧑 ghi âm) | – | end-to-end |

Common Voice tiếng Việt không còn phân phối qua Hugging Face Hub (chuyển sang Mozilla Data Collective, cần tài khoản);
FLEURS được dùng thay. Không bao giờ dùng tập test để hiệu chỉnh hay huấn luyện.
