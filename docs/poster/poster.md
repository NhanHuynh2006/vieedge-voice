# Poster (A0 dọc) — bố cục

**Tiêu đề:** VieEdge-Voice — Hỏi gì đáp nấy bằng tiếng Việt, 100 % offline trên Raspberry Pi 5 + Hailo-8L
**Thông điệp:** NPU lo phần nghe, CPU lo phần nghĩ, hệ điều hành thời gian thực giữ cho cuộc nói chuyện mượt.

| Khối | Nội dung | Nguồn hình/số |
|---|---|---|
| 1. Vấn đề | đám mây: mạng, riêng tư, độ trễ dao động; mục tiêu < 1,5 s tới âm thanh đầu tiên (tham khảo) | – |
| 2. Phần cứng | ảnh thiết bị + sơ đồ khối Pi5/Hailo/mic/loa/nút/LED | 🧑 chụp ảnh |
| 3. Pipeline | sơ đồ README (NPU/CPU/lõi RT, màu theo phần cứng) | README |
| 4. Đóng góp 1 | PhoWhisper INT8 trên Hailo-8L: WER Việt vs Whisper gốc; hiệu chỉnh Việt vs Anh | fig_stt_ladder |
| 5. Đóng góp 2 | thác nước độ trễ; speculative ASR; streaming theo câu | fig_waterfall, fig_first_audio |
| 6. LLM | thang lượng tử: tokens/s vs độ chính xác; LoRA | fig_quant_ladder, fig_training |
| 7. Đóng góp 3 | cyclictest O0–O4 khi LLM hết tải; xrun/giờ; boot time | fig_cyclictest, bảng O |
| 8. Demo | QR tới dashboard (hotspot), ảnh dashboard | screenshot |
| 9. Kết luận | 3 gạch đầu dòng với số đo thật | tables.md |
