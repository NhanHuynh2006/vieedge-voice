# Hồ sơ dự thi: nguồn số liệu

Mọi số trong `paper/vieedge_paper.pdf` và `poster/vieedge_poster.pdf` truy về các tệp sau.
`make_figures.py` sinh lại hình và thống kê (`figures/stats.txt`): `.venv/bin/python docs/submission/make_figures.py`.

| Nội dung | Nguồn |
|---|---|
| Độ trễ, cơ cấu thời gian, bootstrap, Wilcoxon | `results/raw/{CMP2-YOCTO,CMP-PIOS-O0-v2,YO-LAT}-*.json`, `results/phone/raw/phone_*.json`, `figures/stats.txt` |
| WER đầu đối đầu (Bảng 1) | kết quả chạy `bench/bench_zipformer.py` 12/10/2026 (chỉ còn trong nhật ký phiên, chưa ghi vào `experiments.csv`); WER 300 câu: dòng `S6` |
| Whisper-tiny 0,529 và PhoWhisper-tiny 0,114 trên riêng VIVOS | tính lại từ `results/raw/stt_S2cpu-ref_vivos_test.jsonl`, `stt_S1-ref_vivos_test.jsonl` |
| Lượng tử, MCQ | `docs/OPTIMIZATION_NOTES.md`, `results/experiments.csv` (`M1q-Q40-f16`) |
| Tốc độ thiết bị | `results/phone/fold7_llama_bench_20261021.md`, `fold7_bigger_models_20261021.txt` |
| Tra cứu, công suất, nhiễu | `results/phone/fold7_tuning_20261027.md` |
| Chạy liên tục | `results/phone/fold7_campaign_20261027.md`, `raw/phone_soak.json` |
| Jitter 30 phút | `results/jitter_long/*/cyclictest_load.txt` |
| Hailo-8L | `results/hailo_compile/`, `docs/OPTIMIZATION_NOTES.md` |
| Đánh giá LLM | `README.md`, `results/experiments.csv` (`M2`, `NOISYZIP`, `RAGZIPS`) |

Biên dịch: xem lệnh ở đầu `paper/vieedge_paper.tex` (2 lần) và `poster/vieedge_poster.tex`; PDF ra đúng tên `24119068_Huỳnh Lê Thành Nhân_Report.pdf` và `..._Poster.pdf`.

Ảnh bảng điều khiển (`figures/dashboard*.png`): chụp 03/11/2026 khi chạy `python -m vieedge run -c deploy/config/vieedge-laptop.yaml --set audio.backend=remote` trên máy tính xách tay, câu hỏi từ `data/e2e/synth` gửi qua `bench/phone_client.py`. Số trên ảnh là của lần chạy minh hoạ đó.
Lưu đồ: `figures/luu_do.drawio` (mở bằng extension draw.io), bản xuất `figures/luu_do.pdf`.
Chỉ tiêu trong Bảng 2: `docs/proposal_round1.md` mục 5.
