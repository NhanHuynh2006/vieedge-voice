# Chiến dịch đo trên Galaxy Z Fold7 (27/10/2026), ứng dụng chạy trọn vòng trên máy
12 câu hỏi tổng hợp (`data/e2e/synth`, giọng khác giọng trợ lý) phát qua hook adb; thời gian tính từ lúc nói xong (gồm 0,3–0,4 s chờ ngắt câu). Máy cắm sạc, màn hình sáng. Dữ liệu thô từng cấu hình: `raw/phone_*.json`.

| Cấu hình (model, bộ xử lý, giọng) | tiếng đầu nghe thấy p50 | câu trả lời thật p50 | token/s |
|---|---|---|---|
| 2B, NPU, giọng chuẩn | 1,49 s | 1,49 s | 26 |
| 2B, NPU, giọng chuẩn, **xác nhận "Dạ."** | **0,54 s** | 1,71 s | 26 |
| 2B, NPU, giọng nhanh (vivos x_low) | 1,27 s | 1,27 s | 26 |
| 2B, NPU, giọng nhanh, xác nhận, endpoint 300 ms | **0,42 s** | 1,28 s | 26 |
| 0,8B, NPU, giọng chuẩn | 1,16 s | 1,27 s | 27 |
| 0,8B, GPU Adreno, giọng chuẩn | 1,22 s | 1,22 s | 60 |
| 2B, GPU Adreno, giọng chuẩn | 1,31 s | 1,31 s | 36 |
(Pi 5, 0,8B: tiếng đầu 0,59 s với xác nhận, câu trả lời thật 1,6–1,8 s; 3,0–4,5 s khi bật tra cứu.)

Nhận xét:
* Với giọng chuẩn, 2B trên NPU trả lời thật sau ≈ 1,5 s; giọng nhanh bớt ≈ 0,2 s nhưng chất giọng thấp hơn. Xác nhận tức thì đưa tiếng đầu xuống ≈ 0,5 s (độ trễ cảm nhận), không làm câu trả lời thật đến sớm hơn.
* Decode nhanh nhất trên GPU Adreno (0,8B: 60 token/s; 2B: 36) nhưng nạp mô hình lâu hơn (14–24 s so với 6–8 s trên NPU) và câu trả lời thật gần như bằng nhau vì thời gian bị TTS và chờ ngắt câu chi phối.
* Nhận giọng: Zipformer trên điện thoại WER **0,257** trên 12 câu (laptop cùng 12 file: 0,250), tức bản sherpa-onnx Android không kém bản laptop (mẫu nhỏ).

## Chạy liên tục 7,5 phút (62 lượt, 2B NPU, có xác nhận)
* Nhiệt: CPU 52–58 °C, GPU 51–56 °C, NPU (HVX/HMX) lên tới 65 °C rồi hạ về 49 °C; không giảm xung nhịp: token/s quý đầu 25,3 và quý cuối 25,3.
* Câu trả lời thật p50: quý đầu 1,44 s, quý cuối 1,92 s (câu hỏi khác nhau, chưa rõ có do nhiệt hay do độ dài câu).
* Pin 88 → 90 % (đang cắm sạc nên không đo được công suất). Đo công suất thật cần rút sạc và dùng đồng hồ ngoài hoặc `dumpsys batterystats`: chưa làm.
