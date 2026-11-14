# PhoWhisper → HEF cho Hailo-8L (PLAN §5.1, S3/S4)

Chạy trên laptop x86. Dựa trên [hailocs/hailo-whisper](https://github.com/hailocs/hailo-whisper) (commit `ebe7a85`),
dùng đúng patch "Hailo-compatible" của họ cho mã OpenAI Whisper (Conv1d→Conv2d, cửa sổ âm thanh cố định, tách MatMul cuối).

| Bước | Script | Cần DFC? | Trạng thái |
|---|---|---|---|
| 1. HF PhoWhisper → checkpoint định dạng openai-whisper | `hf_to_openai.py` | không | ✅ `work/phowhisper-{tiny,base}.pt` |
| 2. Export ONNX encoder (tiny 10 s/5 s, base 5 s/10 s) + decoder chuỗi cố định | `export_phowhisper.py` | không | ✅ `work/onnx/` |
| 3. Bộ hiệu chỉnh INT8: audio **train** tiếng Việt (VIVOS + FLEURS) vs tiếng Anh (LibriSpeech), 20 % trộn ồn DEMAND | `make_calib.py` | không | ✅ `work/calib/{vi,en}_{10,5}s.npy` |
| 4. Parse → optimize (INT8, model script của hailo-whisper) → kiểm tra drift trên emulator → compile HEF | `convert_encoder.py` | **có** | 🧑 cần DFC 3.x |
| 5. Kiểm tra trên Hailo-8L thật: cosine HEF vs ONNX, tỉ lệ transcript giống nhau | `bench/check_encoder_drift.py` | – (Pi) | 🧑 |

Kiểm tra đã làm trên laptop (không cần DFC): encoder ONNX đã patch + decoder CTranslate2 cho transcript trùng
7/8 câu VIVOS với PhoWhisper chạy cửa sổ 10 s trực tiếp — tức là phần export đúng, phần còn lại chỉ là lượng tử hoá.

```bash
# 🧑 tải DFC vào hailo_compile/wheels/ rồi
docker build -t vieedge-dfc hailo_compile
./hailo_compile/run_all.sh          # 6 HEF: tiny10s vi/en, base5s vi/en, tiny5s vi, base10s vi
```
Kết quả: `work/hef/<tên>/<tên>_<vi|en>_h8l.hef` (+ `report.json`: cosine FP-optimized/quantized vs ONNX, thời gian),
chép vào `models/stt/hef/` và `results/hailo_compile/`.

Nếu biên dịch PhoWhisper thất bại hoàn toàn (PLAN §13): giữ HEF Whisper gốc của Hailo trên NPU (S2) + PhoWhisper
INT8 trên CPU (S1) để so sánh, ghi nguyên nhân (log DFC trong `work/hef/*/`) vào báo cáo.

Số đo tham chiếu trên laptop (FP32, trước lượng tử hoá; `results/experiments.csv`, VIVOS+FLEURS 2×300 câu):
PhoWhisper-tiny cửa sổ 10 s WER ≈ 0,21; PhoWhisper-base cửa sổ 5 s ≈ 0,24; **base cửa sổ 10 s ≈ 0,16** (tốt nhất).
hailo-whisper ghi rằng base 10 s không biên dịch được cho Hailo-8; `run_all.sh` vẫn thử (job `base-encoder-10s`) — nếu
DFC biên dịch được cho Hailo-8L thì đây là cấu hình nên dùng (`stt.hybrid.hef/decoder` → base).

Ghi chú:
* Decoder chạy CPU (CTranslate2, có KV cache) — decoder HEF của Hailo không có KV cache (chuỗi cố định) nên chậm hơn nhiều;
  `export_phowhisper.py` vẫn xuất decoder ONNX để có thể thử nếu muốn.
* CTranslate2 nhận trực tiếp hidden states có độ dài 500 (10 s) hoặc 250 (5 s) khung từ encoder HEF.
