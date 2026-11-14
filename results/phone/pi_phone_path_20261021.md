# Điện thoại làm micro + loa của Pi (Pi 5 Yocto-RT, ảnh 21/10) — đo qua mạng ISLAB bằng điện thoại giả (`bench/phone_client.py`)
Pi: 192.168.196.114, `audio.backend: auto` → không có thẻ âm thanh USB nên chọn `remote`; tiến trình âm thanh ở lõi 3 SCHED_FIFO, mlock; xrun 0/0 sau cả phiên thử. Zipformer, Qwen3.5-0.8B LoRA Q4_0, xác nhận tức thì bật.
| Tình huống | Điều người dùng nghe | Thời điểm (từ lúc nói xong) |
|---|---|---|
| Lệnh đường nhanh ("Xoay trái hai vòng nhé") | câu trả lời có sẵn | 0,42 s trong Pi, nghe thấy ≈ 0,59 s (gồm 0,15 s mạng và bộ đệm) |
| Câu hỏi qua LLM, tra cứu Wikipedia **tắt** | tiếng "Dạ." lúc 0,59 s, câu trả lời thật lúc | **1,6–1,8 s** |
| Câu hỏi qua LLM, tra cứu Wikipedia **bật** | tiếng "Dạ." lúc 0,59 s, câu trả lời thật lúc | 3,0–4,5 s |
Tra cứu bật cho câu trả lời chính xác hơn (tỉ lệ bịa 0,52 → 0,30) nhưng chậm thêm 1,4–2,8 s trên Pi: có công tắc "Tra cứu" ở đầu trang `/phone` và trên bảng điều khiển.
Nhiệt SoC 36 °C sau phiên thử. Số đo bằng giọng tổng hợp, chưa có giọng người hay micro điện thoại thật.

## Thử ứng dụng Android ở chế độ "Kết nối Pi" (Fold7 ↔ Pi, cùng mạng ISLAB, 21/10)
* Nhập IP, bấm bật: kết nối được (`Pi · .114`, trạng thái "Sẵn sàng"), hội thoại hiện đúng dạng bong bóng, chip "tiếng đầu 0,15–0,63 s".
* "Giữ nói": giữ 9 s → Pi nhận một câu 9,12 s (`utt_s`), chạy đủ đường ống. "Ngắt": bấm khi Pi đang nói → lượt bị huỷ (`cancelled: true`, tiếng dừng sau ≈ 0,8 s).
* Không nhận ra được tiếng nói phát từ loa laptop sang micro điện thoại (nói trong không khí, âm lượng thấp, bộ khử ồn của điện thoại): chưa kiểm chứng nhận giọng thật qua micro điện thoại; việc này cần người nói trực tiếp.
* Lỗi đã sửa trong đợt thử: hai điện thoại cùng gửi micro vào Pi làm lẫn tiếng (mọi câu bị từ chối) → Pi chỉ dùng micro của điện thoại kết nối sau cùng; trình duyệt/bàn phím thêm dấu phẩy sau IP → app lọc ký tự không hợp lệ; bàn phím che nút → giao diện co lên trên bàn phím.
