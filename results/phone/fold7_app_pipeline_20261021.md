# Ứng dụng Android chạy trọn vòng trên Galaxy Z Fold7 (21/10/2026)
Đường ống trong ứng dụng: Silero VAD (ngắt câu 400 ms) → Zipformer-vi (sherpa-onnx) → [đường nhanh | llama.cpp trên NPU/GPU/CPU] → cắt câu (5 từ) → chuẩn hoá → Piper vais1000-medium (sherpa-onnx) → loa.
Số đo bằng 4 câu hỏi tổng hợp phát qua hook adb (không phải giọng người), tính từ lúc nói xong (gồm 400 ms chờ ngắt câu). llama.cpp commit 7fe450e19, model LoRA Q4_0.

| Model / thiết bị | token/s trong ứng dụng | tiếng đầu tiên, câu hỏi qua LLM | lệnh đường nhanh |
|---|---|---|---|
| 0,8B NPU Hexagon | 40–43 | 1,73–1,94 s | 0,76 s |
| 0,8B GPU Adreno | 57–68 | 1,59–1,81 s | 0,79 s |
| 0,8B CPU | 12–34 (không ổn định) | 1,79–2,56 s | 0,81 s |
| **2B NPU Hexagon** | 26–27 | **1,23–1,40 s** | 0,74 s |
| 2B CPU | 10–17 | 2,56–3,23 s | 0,80 s |

Nhận xét: model 2B trên NPU cho tiếng đầu tiên sớm nhất, và đúng là model có điểm giám khảo cao hơn (4,17 so với 3,63 của 0,8B, `README`). Pi 5 làm việc tương tự mất ≈ 2,0 s với model 0,8B. Phần lớn thời gian còn lại là chờ ngắt câu (0,4 s) và Piper đọc câu đầu (≈ 0,5–0,6 s), không phải LLM.
Hạn chế: số tok/s trong ứng dụng thấp hơn `llama-bench` (NPU 0,8B: 40–43 so với 63) vì LLM, STT và TTS cùng chạy; điện thoại có thể giảm xung nhịp khi nóng; chưa đo pin, nhiệt, công suất; chưa thử bằng micro và giọng người thật.
