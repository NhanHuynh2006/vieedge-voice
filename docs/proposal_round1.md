# Đề xuất vòng 1 — VieEdge-Voice

**Trợ lý hỏi đáp bằng giọng nói tiếng Việt chạy hoàn toàn trên Raspberry Pi 5 + Hailo-8L, hệ điều hành Yocto thời gian thực**

## 1. Vấn đề và mục tiêu
Trợ lý giọng nói hiện nay phụ thuộc đám mây: cần mạng, lộ dữ liệu giọng nói, độ trễ dao động. Mục tiêu của đề tài là một
thiết bị giá vài triệu đồng **nghe – hiểu – suy nghĩ – trả lời bằng giọng nói tiếng Việt, 100 % offline**, với thời gian
từ lúc người dùng ngừng nói tới lúc nghe thấy âm thanh trả lời đầu tiên đủ ngắn để hội thoại tự nhiên
(khoảng lặng giữa lượt nói của người ~200 ms — Stivers et al., PNAS 2009). Chức năng giới hạn ở hỏi đáp, không điều khiển thiết bị.

## 2. Phần cứng
Raspberry Pi 5 8 GB (4× Cortex-A76) + Hailo-8L 13 TOPS (M.2/HAT+), mic USB, loa, nút push-to-talk + LED trạng thái, tản nhiệt chủ động.
Ràng buộc quyết định kiến trúc: Hailo-8L **không chạy LLM** (GenAI của Hailo chỉ dành cho Hailo-10H) nhưng chạy tốt
**encoder Whisper**; decoder trên NPU chậm vì không có KV cache.

## 3. Giải pháp — ba đóng góp kỹ thuật
1. **STT chuyên tiếng Việt trên NPU:** biên dịch encoder **PhoWhisper** (VinAI, fine-tune Whisper trên 844 giờ tiếng Việt)
   sang HEF Hailo-8L bằng quy trình hailo-whisper, lượng tử hoá INT8 với **dữ liệu hiệu chỉnh tiếng Việt**
   (so sánh với hiệu chỉnh tiếng Anh); decoder chạy CPU bằng CTranslate2 có KV cache. Kiểm tra độ lệch HEF–ONNX trước khi đo WER.
2. **Phân công dị thể NPU nghe ↔ CPU nghĩ + nói, ASR tăng dần:** encoder chạy liên tục trên NPU trong lúc người dùng nói;
   ngay khi có khoảng lặng đầu tiên, bản giải mã cuối "dự đoán" được chạy, nên khi VAD xác nhận ngừng nói thì văn bản gần như
   đã có. LLM (llama.cpp, GGUF nhiều mức lượng tử, LoRA phong cách nói, giải mã suy đoán, KV-cache system prompt) và
   TTS Piper chạy CPU, phát theo từng câu.
3. **Hệ điều hành thời gian thực tối giản:** Yocto scarthgap + PREEMPT_RT (mainline từ Linux 6.12) + cô lập lõi 3 cho
   tiến trình âm thanh (SCHED_FIFO, IRQ USB, mlockall) — đo jitter, xrun, p95/p99 độ trễ, thời gian khởi động so với Raspberry Pi OS.

## 4. Kiến trúc
Tiến trình âm thanh RT (lõi 3) ⇄ ring buffer bộ nhớ chia sẻ ⇄ VAD Silero → ASR tăng dần (log-mel CPU → encoder Hailo-8L →
decoder CPU) → chuẩn hoá câu hỏi → llama-server (lõi 0–2, streaming) → tách câu → chuẩn hoá văn bản tiếng Việt cho TTS
(số, ngày giờ, đơn vị, viết tắt) → Piper → loa. Mọi stage ghi timestamp → dashboard web realtime qua hotspot riêng
(chữ hiện dần, câu trả lời, thác nước độ trễ, CPU từng lõi, NPU, RAM, nhiệt, công suất, xrun).

## 5. Kế hoạch thí nghiệm và chỉ số (đo trên Pi 5 thật)
* STT S0–S5: WER VIVOS + FLEURS (sạch và trộn ồn 20/10/5 dB), độ trễ, CPU vs NPU, INT8 hiệu chỉnh Việt vs Anh, ASR tăng dần.
* LLM M0–M5: thang lượng tử Q8_0…Q3_K_M (Global-MMLU tiếng Việt, tokens/s, TTFT, RAM), LoRA, speculative decoding, KV-cache tiền tố, build tối ưu Cortex-A76.
* TTS T0–T2: giọng medium vs low, ảnh hưởng chuẩn hoá văn bản (đọc ngược bằng ASR + người nghe).
* Hệ thống P1–P3 và OS O0–O4: thời gian tới âm thanh đầu tiên p50/p95/p99, J/lượt, cyclictest/rtla, xrun/giờ.
* Mục tiêu tham khảo (không phải kết quả): p95 thời gian tới âm thanh đầu tiên < 1,5 s; 0 xrun/giờ ở O4.

## 6. Tiến độ hiện tại
Đã hoàn thành: toàn bộ phần mềm pipeline (chạy end-to-end trên laptop), export PhoWhisper sang ONNX tương thích Hailo và
kiểm tra đúng chức năng, bộ hiệu chỉnh INT8 Việt/Anh, tập ~3.400 cặp hỏi–đáp tiếng Việt tự sinh có lọc và kiểm tra sự thật,
LoRA + lượng tử GGUF, Yocto layer + recipe (PREEMPT_RT, Hailo 4.24, llama.cpp/CTranslate2/ONNX Runtime/espeak-ng),
dashboard, bộ script đo cho mọi thí nghiệm. Việc tiếp theo: biên dịch HEF bằng Hailo DFC, đo trên Pi 5, báo cáo.

## 7. Phù hợp thể lệ
Hiệu năng mô hình trên biên (WER, tokens/s, TTFT, độ trễ, RAM, W, J/lượt) · thiết kế HW–SW + giao diện (pipeline đa luồng,
dashboard) · tối ưu phần cứng (NPU/CPU, INT8, lượng tử LLM, speculative decoding, Cortex-A76, RT + cô lập lõi) ·
báo cáo bằng bảng/biểu đồ sinh tự động và demo trực tiếp. Nhóm ứng dụng: nhận dạng giọng nói, giao tiếp người–máy; suy luận 100 % trên thiết bị.
