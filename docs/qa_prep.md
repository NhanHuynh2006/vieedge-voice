# Chuẩn bị phản biện (PLAN §14)

> Mỗi câu trả lời dẫn tới bảng/biểu đồ trong báo cáo (sinh từ `results/experiments.csv`). Chỗ ghi «[bảng X]»
> phải thay bằng số đo thật trước khi bảo vệ — không trả lời bằng số tham khảo trong PLAN.

**1. Sao không dùng cloud?**
Riêng tư (giọng nói không rời thiết bị), không cần mạng (hội trường, vùng sóng yếu), độ trễ ổn định (không phụ thuộc
mạng — xem phân bố p99 [fig_first_audio]), chi phí vận hành bằng 0 sau khi mua thiết bị.

**2. Sao LLM không chạy trên NPU?**
Hailo-8L là NPU dataflow cho mạng có hình dạng cố định; Hailo chỉ hỗ trợ GenAI/LLM trên Hailo-10H. Vì vậy chúng tôi
đặt NPU vào chỗ mạnh nhất của nó — encoder Whisper (tính toán dày, kích thước cố định, chạy lặp lại khi ASR tăng dần)
— để CPU rảnh cho LLM và TTS. Bằng chứng: tải CPU khi nghe ở cấu hình CPU-only vs NPU [P3, dashboard].

**3. Sao decoder STT không chạy trên NPU?**
HEF decoder của Hailo biên dịch với chuỗi cố định, không có KV cache: mỗi token phải tính lại toàn bộ chuỗi.
Trên CPU, CTranslate2 giữ KV cache và nhận trực tiếp hidden state từ NPU. Tham khảo cộng đồng (edge_whisper):
encoder Hailo + decoder CPU ~131 ms vs decoder trên Hailo ~1,3 s (tiny, 10 s). Số của nhóm: [bảng S2/S3, cột encoder/decoder ms].

**4. RT kernel có làm AI nhanh hơn không?**
Không, và chúng tôi không tuyên bố như vậy. PREEMPT_RT + cô lập lõi làm độ trễ **ổn định**: max cyclictest trên lõi audio
khi LLM chạy hết tải, số xrun/giờ, p99 thời gian tới âm thanh đầu tiên [bảng O0–O4]. tokens/s có thể giảm nhẹ và được
báo cáo trung thực ở cùng bảng.

**5. INT8 làm STT kém đi bao nhiêu?**
Bảng S1 (PhoWhisper INT8 CPU) vs S3 (encoder INT8 trên Hailo) vs S4 (hiệu chỉnh bằng tiếng Anh); kèm cosine similarity
HEF–ONNX trên tập test (check_encoder_drift). Một số lớp giữ 16-bit (a16_w16) theo model script của Hailo.

**6. Đo chất lượng câu trả lời thế nào?**
(a) Global-MMLU tiếng Việt (Apache-2.0) theo từng mức lượng tử; (b) 340 câu hỏi–đáp giữ lại (10 %) chấm bằng LLM lớn
làm giám khảo (đúng, ngắn, dễ nghe, bịa); (c) 🧑 duyệt nhanh 100 câu. Dữ liệu train đã qua lọc tự động + một lượt
kiểm tra sự thật bằng teacher.

**7. Vì sao chọn mô hình X?** Điểm Global-MMLU-vi + điểm giám khảo + tokens/s + TTFT trên Pi [bảng M1/M2]; đã thử cả các mô hình
nhỏ mới nhất (Qwen3.5-0.8B/2B, Gemma-4-E2B).

**8. Dữ liệu sinh bởi LLM có đáng tin?** Đã lọc (định dạng, độ dài, markdown, trùng lặp), chấm sự thật, chỉ dùng để học
*phong cách nói*; đánh giá kiến thức dùng benchmark độc lập. Hạn chế được ghi rõ.

**9. Ồn hội trường?** Push-to-talk + mic gần miệng; WER ở SNR 20/10/5 dB [bảng S, cột wer_noisy]; echo guard tắt mic khi loa phát.

**10. Câu hỏi dài hơn cửa sổ encoder (10 s / 5 s)?** Cắt tại khung 20 ms yên lặng nhất gần cuối cửa sổ, đoạn đã cắt được chốt,
chỉ giải mã lại phần đuôi (incremental.py). Câu hỏi thường < 10 s.

**11. ASR tăng dần giúp gì?** Bắt đầu giải mã "speculative final" ngay khi VAD thấy khung im lặng đầu tiên; khi endpoint
(500 ms im lặng) xác nhận thì văn bản đã sẵn sàng → độ trễ STT nằm trong thời gian chờ endpoint [S5-on vs S5-off].

**12. Năng lượng?** J/lượt = công suất đo bằng đồng hồ USB-C (🧑) × thời gian lượt; đo cả lúc rảnh [bảng P].

**13. Tại sao Yocto mà không chỉ Pi OS?** Ảnh tối giản: khởi động nhanh hơn tới "sẵn sàng nghe", ít dịch vụ nền,
kernel RT + tracer kiểm soát được, tái lập được (kas lock, sstate). Có cổng 5 ngày + phương án Pi OS nếu Hailo trên Yocto chưa ổn.
