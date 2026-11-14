# VieEdge-Voice

Trợ lý hỏi đáp bằng giọng nói tiếng Việt chạy **hoàn toàn offline** trên **Raspberry Pi 5 + Hailo-8L (13 TOPS)**,
hệ điều hành **Yocto (scarthgap) + PREEMPT_RT**. NPU lo phần *nghe* (encoder PhoWhisper INT8), CPU lo phần
*nghĩ* (LLM llama.cpp) và *nói* (Piper vi_VN), lõi 3 được cô lập cho luồng âm thanh thời gian thực.

## Bản cuối (11/2026)

- **Hồ sơ dự thi:** báo cáo [docs/submission/paper](docs/submission/paper), poster [docs/submission/poster](docs/submission/poster), slide [docs/submission/slides](docs/submission/slides) (bản `_v2` có thêm điện thoại TCL T506T; bản gốc giữ nguyên).
- **Ứng dụng Android** (`android/`): chạy toàn bộ đường ống trên máy, 85 thẻ sơ cứu/thiên tai có nguồn, GPS và bản đồ ngoại tuyến, lịch sử trò chuyện. Hai bản dựng: `snapdragon` (Galaxy Z Fold7, NPU Hexagon) và `generic` (mọi máy arm64, chỉ CPU).
- **Tệp lớn ở mục [Releases](../../releases):** 2 APK, mô hình đã tinh chỉnh Qwen3.5 0,8 tỉ và 2 tỉ (GGUF Q4_0), các LoRA adapter, chỉ mục Wikipedia tiếng Việt (SQLite FTS5). Mô hình gốc (Qwen, Zipformer-vi của hynt, giọng Piper) và các tập dữ liệu công khai (VIVOS…) không đưa lên; tải lại theo [docs/REFERENCES.md](docs/REFERENCES.md) và các script trong `scripts/`.
- **Kết quả đo:** `results/` (Pi OS và Yocto-RT: `results/compare/SUMMARY.md`; điện thoại: `results/phone/`; thẻ an toàn: `results/an_toan/TOM_TAT.md`).

Kế hoạch gốc: [PLAN.md](PLAN.md). Hướng dẫn chạy từng thí nghiệm trên thiết bị: [docs/RUNBOOK.md](docs/RUNBOOK.md).

```
Mic ─► [RT audio process: lõi 3, SCHED_FIFO 80, mlockall] ─► ring buffer (shared memory)
          │
          ├─► Silero VAD + endpointing ◄── nút push-to-talk (GPIO17) / nút trên dashboard
          └─► ASR tăng dần: log-mel (CPU) → ENCODER PhoWhisper INT8 trên Hailo-8L → DECODER CTranslate2 (CPU, KV cache)
                 partial mỗi 750 ms · "speculative final" ngay khi người dùng ngừng nói
                        ▼
              chuẩn hoá câu hỏi → llama-server (lõi 0–2, KV-cache system prompt, streaming, speculative decoding)
                        ▼
              tách câu (câu đầu cắt sớm) → chuẩn hoá văn bản tiếng Việt (số, ngày, giờ, đơn vị…) → Piper VITS (ONNX)
                        ▼
              ring buffer phát → loa         Telemetry (timestamp từng stage, CPU, NPU, RAM, nhiệt, W, xrun) → dashboard
```

## Trạng thái

| Hạng mục | Trạng thái |
|---|---|
| Pipeline đầy đủ (`src/vieedge`) | ✅ chạy end-to-end trên laptop (audio file/sounddevice, encoder ONNX thay cho HEF) |
| PhoWhisper → ONNX theo patch của hailo-whisper (cửa sổ 10 s/5 s) | ✅ đã export + kiểm tra: encoder ONNX + decoder CT2 cho cùng kết quả với PhoWhisper gốc |
| Bộ hiệu chỉnh INT8 tiếng Việt / tiếng Anh (S4) | ✅ `hailo_compile/work/calib/*.npy` (1024 mẫu, chỉ từ tập train) |
| Biên dịch HEF bằng Hailo DFC 3.34 | ⚠️ biên dịch được (INT8 và INT8+fine-tune GPU) nhưng cosine so với ONNX chỉ 0,84 / 0,66 (< 0,9) → **chưa dùng được**; STT mặc định là Zipformer trên CPU |
| HEF Whisper gốc của Hailo cho Hailo-8L (S2) | ✅ đã tải về `models/stt/hef/` |
| Dữ liệu hỏi–đáp tự sinh + lọc + kiểm tra sự thật | ✅ `data/qa/` (teacher Qwen3.5-9B trên GPU laptop) |
| LoRA (Qwen2.5-1.5B, Qwen3.5-2B, Qwen2.5-0.5B, Qwen3.5-0.8B) + merge + GGUF F16…Q3_K_M (imatrix) | ✅ `training/runs/`, `models/llm/gguf/` |
| Yocto image (kas, meta-vieedge, PREEMPT_RT, Hailo 4.24, llama.cpp/CT2/ORT/espeak-ng) | ✅ build cả O2 và O3/O4 (`images/{o2,rt}/*.wic.bz2`), đã flash và chạy trên Pi 5 (Yocto-RT, `isolcpus=3`) |
| Dashboard realtime, push-to-talk, LED, so sánh CPU vs NPU, Pi OS vs Yocto | ✅ `src/vieedge/web` |
| Benchmark S0–S5, M0–M5, T0–T2, P1–P3, O0–O4 + bảng/biểu đồ | ✅ script trong `bench/`; đã đo Pi OS và Yocto-RT (jitter, độ trễ đầu cuối, RAM) → `results/compare/SUMMARY.md` |
| Đường nhanh (luật phản xạ Go2 + hỏi–đáp có sẵn, âm thanh tổng hợp sẵn) và xác nhận tức thì | ✅ `src/vieedge/fastpath`: 0,52 s so với 2,1–3,6 s qua LLM |
| Thẻ sơ cứu và ứng phó thiên tai có nguồn (kịch bản mất sóng) | ✅ `src/vieedge/safety`, `data/an_toan`: 42 thẻ, 42 nguồn; đúng thẻ 79/84 câu độc lập (gõ), 40/84 qua giọng tổng hợp; xem `results/an_toan/TOM_TAT.md` |
| Điện thoại làm micro + loa (trang web `/phone` https và ứng dụng Android), Pi như máy chủ | ✅ chạy thử bằng điện thoại giả lập (ws và wss); 🧑 chưa thử trên điện thoại thật |
| Ứng dụng Android chạy trọn vòng trên Fold7 (NPU Hexagon), 12 câu tổng hợp | ✅ tiếng đầu 0,54 s (có xác nhận), câu trả lời thật 1,3–1,7 s; chạy 62 lượt không giảm tốc; `results/phone/fold7_campaign_20261027.md` |
| Nghe/nói bằng loa + mic USB cắm vào Pi | 🧑 chưa thử (Pi chưa cắm thiết bị âm thanh) |

Không có con số nào trong tài liệu được viết tay: tất cả lấy từ `results/experiments.csv` (cột `os_cfg`
phân biệt số đo trên laptop với Raspberry Pi).

## Kết quả trên Raspberry Pi 5 (Pi OS và Yocto-RT)

Chi tiết và hạn chế: [docs/report/report.md](docs/report/report.md), [results/compare/SUMMARY.md](results/compare/SUMMARY.md).

| Chỉ số (cùng board, cùng bài đo, Q4_0) | Pi OS nguyên bản | Yocto-RT |
|---|---|---|
| Jitter lõi 3 khi tải nặng (max, 5 phút) | 105 µs | **85 µs** |
| Jitter 30 phút (max) | 127 µs | **92 µs** |
| Câu trả lời thật bắt đầu, yên (p50 / p95) | **1,60 / 3,62 s** | 2,02 / 3,78 s |
| Lệnh Go2 qua đường nhanh | 0,53 s | 0,52 s |
| RAM sau boot | ≈ 500 MB | 285 MB |
| LLM Qwen3.5-0.8B Q4_0, nạp prompt / sinh (token/s) | 125,7 / 18,1 | chưa đo |

Yocto-RT giảm đỉnh jitter (19–28 %) và RAM, **không** làm LLM hay độ trễ trả lời nhanh hơn (Pi OS nhanh hơn ≈ 0,4 s khi yên).

## Kết quả đã đo trên laptop (không phụ thuộc phần cứng)

Từ `results/experiments.csv` (os_cfg = laptop; đầy đủ ở [docs/report/tables.md](docs/report/tables.md), hình ở `docs/report/figures/`).
Đây **không phải** số đo trên Pi 5 — độ trễ/tokens/s phải đo lại trên thiết bị theo RUNBOOK.

| Hạng mục | Kết quả |
|---|---|
| WER VIVOS+FLEURS (2×300 câu), PhoWhisper-tiny | 30 s: 0,250 · cửa sổ 10 s: 0,203 · encoder ONNX đã patch cho Hailo (FP32) + decoder CT2: 0,211 |
| PhoWhisper-base | 30 s: 0,222 · encoder 5 s: 0,235 · **encoder 10 s: 0,158** |
| Whisper-tiny gốc (trọng số của HEF Hailo, S2) | 0,603 → lý do phải dùng PhoWhisper |
| Global-MMLU vi (400 câu) Q4_K_M | Gemma-4-E2B 0,51 · Qwen3.5-2B 0,485 · Qwen3-1.7B 0,455 · Qwen2.5-1.5B 0,418 · SeaLLMs-v3-1.5B 0,343 · Qwen3.5-0.8B 0,328 · Qwen2.5-0.5B 0,315 |
| LoRA (giám khảo LLM, 345 câu test, 1–5) | Qwen2.5-1.5B 3,33 → **3,81** (bịa 0,33 → 0,26) · Qwen3.5-2B 3,70 → **4,17** (bịa 0,25 → 0,12) · Qwen2.5-0.5B 2,70 → 3,20 · Gemma-4-E2B (không LoRA) 4,34 |
| Ảnh hưởng LoRA lên kiến thức (cùng Q4_K_M) | Qwen2.5-1.5B 0,418 → 0,373 · Qwen3.5-2B 0,485 → 0,445 (bản LoRA F16: 0,485; Q5_K_M: 0,473) |
| Chuẩn hoá văn bản TTS (T2, đọc ngược bằng ASR) | WER 0,351 → **0,137** |
| End-to-end (laptop, 30 lượt): ngừng nói → âm thanh đầu p50 | speculative ASR bật 1 494 ms / tắt 1 604 ms · không streaming theo câu 1 756 ms |

**Chọn LLM cho Pi:** cấu hình mặc định hiện là `qwen3.5-0.8b-vi-voice-Q4_0` (nhanh nhất; xem `docs/OPTIMIZATION_NOTES.md`); trước đây là `qwen2.5-1.5b-vi-voice-Q4_K_M` (chính xác hơn, chậm hơn ≈0,8 s). Ứng viên chất lượng cao hơn: `qwen3.5-2b-vi-voice-Q5_K_M`/`Q4_K_M` (lai linear-attention, có lớp MTP)
và `gemma-4-e2b-Q4_K_M` — quyết định cuối theo tokens/s + TTFT đo trên Pi (RUNBOOK §3, `--set llm.model=…`).

## Cấu trúc

```
vieedge-voice/
├── PLAN.md
├── yocto/            kas.yml (O2), kas-rt.yml (O3/O4), build.sh, meta-vieedge/
├── hailo_compile/    HF→openai ckpt, export ONNX, calib set, DFC convert + drift check, Dockerfile, run_all.sh
├── src/vieedge/
│   ├── audio/        rt_engine.py (process RT), ring.py, capture.py, playback.py, vad.py, echo_guard.py
│   ├── stt/          cpu_ct2.py, hailo_encoder.py, cpu_decoder.py, incremental.py, mel.py, tokens.py
│   ├── llm/          llamacpp_stream.py, prompts.py
│   ├── tts/          vi_normalize.py, phonemizer.py, piper_tts.py, segmenter.py
│   ├── telemetry/    timeline.py, sysmon.py, power.py
│   ├── web/          server.py + static/ (dashboard, compare)
│   ├── pipeline.py   gpio.py  config.py  rt.py  textproc.py  __main__.py
├── training/         gen_qa.py, lora_train.py, merge_quantize.py
├── bench/            bench_stt/llm/tts/e2e.py, os_bench.sh, xrun_test.py, judge.py, check_encoder_drift.py, make_tables/plots.py
├── review_app/       duyệt nhanh 🧑 (hỏi–đáp, MOS, đọc số)
├── deploy/           config (pi / pios / laptop), systemd, vieedge-tune, vieedge-osmode, pios_setup.sh
├── scripts/          download_models.py, download_data.py, run_teacher.sh, stage_models.sh, deploy_models.sh
├── data/  models/    (không commit — tải/sinh bằng scripts)
├── results/          experiments.csv, raw/, turns/, os/
└── docs/             proposal_round1.md, RUNBOOK.md, qa_prep.md, REFERENCES.md, report/, poster/
```

## Chạy nhanh trên laptop

```bash
uv venv --python 3.11 .venv && uv pip install --python .venv/bin/python -e ".[laptop,dev]" torch transformers peft
.venv/bin/python scripts/download_models.py && .venv/bin/python scripts/download_data.py
env -u PYTHONPATH .venv/bin/python -m vieedge run -c deploy/config/vieedge-laptop.yaml     # mở http://127.0.0.1:8000
env -u PYTHONPATH .venv/bin/python -m pytest -q
```
(`env -u PYTHONPATH` chỉ cần nếu máy có ROS trong PYTHONPATH.)

## Trên Raspberry Pi 5

* **Yocto (O2–O4):** `./yocto/build.sh` hoặc `./yocto/build.sh rt` → flash `images/{o2,rt}/vieedge-image-{o2,rt}.wic.bz2` → `./scripts/stage_models.sh && ./scripts/deploy_models.sh <ip>`. Chi tiết: [yocto/README.md](yocto/README.md).
* **Raspberry Pi OS (O0/O1, phương án dự phòng của cổng 5 ngày):** `deploy/scripts/pios_setup.sh [--o1] [--rt-kernel]`.

Dashboard: kết nối điện thoại vào Wi-Fi `VieEdge-Voice` (mật khẩu `vieedge2026`) → `http://192.168.50.1:8000`.
