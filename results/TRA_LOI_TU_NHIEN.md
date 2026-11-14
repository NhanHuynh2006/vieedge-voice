# Câu trả lời nghe tự nhiên hơn: đã đo gì, đổi gì (05–06/11/2026)

## Vấn đề người dùng nghe thấy
* Câu nào cũng mở đầu "Mình không chắc lắm…": với lời nhắc cũ, 252/345 câu hỏi nói (qua Zipformer) và 177/345 câu gõ có câu
  trả lời bắt đầu bằng "Mình không chắc" (`bench/eval_answer_style.py`, `results/answer_style.json`).
* Đường nhanh trên điện thoại vẫn còn câu của dự án robot chó Go2 ("Mình là Gô, robot chó", "gâu", "Xoay trái 90 độ!").
* Câu đầu bị cắt sau 3 từ ("Thủ đô của" … ngắt … "Nhật Bản là Tokyo"); nói "Dạ." xong mô hình lại nói "Dạ, …".
* Bộ đệm loa chỉ 0,5 s: khi câu sau tổng hợp lâu hơn 0,5 s thì có khoảng lặng giữa hai câu.
* Không nhớ câu trước ("Còn Hàn Quốc thì sao" không hiểu).
* Có lần trả lời sai về Hoàng Sa, Trường Sa.

## Thử đổi lời nhắc: không dùng được
Cùng mô hình (Qwen3.5-2B LoRA, Q4_0 imatrix, đúng tệp trên điện thoại), cùng tra cứu Wikipedia, 345 câu hỏi kiểm tra; giám
khảo Qwen3.5-9B chấm 1–5 và đánh dấu câu bịa.

| Lời nhắc | Câu gõ: điểm / tỉ lệ bịa | Câu nói qua ASR: điểm / tỉ lệ bịa | Mở đầu "không chắc" (câu nói) |
|---|---|---|---|
| A: cũ (trung thực, "không liên quan thì nói không chắc") | 3,84 / **12,2%** | 3,06 / **21,2%** | 252/345 |
| B: "nói thẳng như người", phạt lặp từ 1,1 | 3,76 / 22,3% | 2,75 / 48,4% | 21/345 |
| C: lời nhắc cũ, bỏ câu "không liên quan thì nói không chắc" | 3,79 / 19,7% | chưa chấm | 159/345 |

Bỏ câu rào đón thì mô hình 2 tỉ tham số bịa gần gấp đôi. Với một ứng dụng dùng khi khẩn cấp, nhóm giữ lời nhắc A: nói "không
chắc" còn hơn nói sai.

## Thử mô hình lớn hơn: không dùng được trên điện thoại
Gemma-4-E2B (Q4_K_M, lời nhắc A): câu gõ 4,08 điểm, bịa 5,2%; câu nói 2,93 điểm, bịa 16,8%. Ít bịa hơn, nhưng trên Fold7 chỉ
8 token/s trên GPU (12 trên CPU); tiếng trả lời đầu tiên p50 6,2 s trên GPU (7,5 s trên CPU), so với 1,8 s của mô hình hiện
tại (đo 8 câu nói, không có "Dạ." đệm). Quá chậm nên không dùng; tệp đã xoá khỏi điện thoại.

## Đã đổi trong ứng dụng
* Bỏ toàn bộ luật và câu trả lời của robot Go2 khỏi đường nhanh trên điện thoại. Thay bằng: chào hỏi, cảm ơn, giới thiệu, thời
  tiết (nói thật là không xem được khi không có mạng), mỗi loại vài cách nói; giờ và ngày đọc từ đồng hồ máy; Hoàng Sa và
  Trường Sa là lãnh thổ Việt Nam.
* Câu đầu của câu trả lời kết thúc ở chỗ ngắt tự nhiên (dấu câu, hoặc tối đa 7 từ); bỏ "Dạ," ở đầu câu trả lời khi đã nói
  "Dạ.". Lời xác nhận chỉ còn "Dạ." và "Vâng." (bỏ "Ừm.").
* Bộ đệm loa 3 s: câu sau được tổng hợp trong lúc câu trước đang phát. Micro chỉ mở lại khi loa đã phát hết.
* Nhớ 2 lượt hỏi đáp gần nhất trong 3 phút; "Cuộc trò chuyện mới" xoá trí nhớ này.
* Đo trên điện thoại với bản cuối (câu gõ, có "Dạ." đệm): "Thủ đô của Nhật Bản là gì" → "Thủ đô chính của Nhật Bản là
  Tokyo…", "Dạ." sau 0,18 s, câu trả lời sau 0,92 s; "Hôm nay là thứ mấy" → "Hôm nay là thứ Sáu, ngày 6 tháng 11 năm 2026."
  sau 0,25 s. Còn yếu: "Còn Hàn Quốc thì sao" vẫn trả lời "Mình không chắc…" dù đã có câu trước trong ngữ cảnh; "Tại sao
  bầu trời có màu xanh" trả lời sai cơ chế (nói "hấp thụ ánh sáng đỏ", đúng ra là tán xạ ánh sáng xanh).

## Giới hạn còn lại
Mô hình 2 tỉ tham số trả lời được trong 1–2 s trên điện thoại nhưng hiểu kém khi câu hỏi bị nghe sai, và vẫn hay nói "không
chắc" (đó là cái giá để ít bịa). Giọng đọc Piper là giọng tổng hợp; nhóm chưa đo được giọng tiếng Việt chạy trên máy nào
tự nhiên hơn.
