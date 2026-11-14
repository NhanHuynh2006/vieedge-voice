# Bộ hỏi–đáp bằng lời tiếng Việt (tự sinh)

Sinh bằng `training/gen_qa.py` với teacher **Qwen3.5-9B Q4_K_M** (llama.cpp Vulkan trên RTX 4060 laptop):
20 lĩnh vực × ~170 chủ đề con × 3 góc hỏi (cơ bản / tại sao–thế nào / đời sống) + ~8 % câu "không thể biết"
(thông tin thời gian thực, thông tin cá nhân, tương lai, tiền đề sai, chi tiết quá hiếm, y tế/pháp lý cụ thể).

Lọc tự động: độ dài, markdown/emoji, có dấu tiếng Việt, ≤ 4 câu, ≤ 75 từ, trùng lặp câu hỏi; bỏ câu chào mở đầu
lặp lại ("Chào bạn, …"). Sau đó một lượt **kiểm tra sự thật** bằng teacher (liệt kê từng chi tiết → điểm 1–5),
giữ điểm ≥ 4. Chia 90/10 phân tầng theo lĩnh vực.

| File | Nội dung |
|---|---|
| raw.jsonl | mọi cặp sinh ra (+ cờ `kept` của bộ lọc tự động) |
| verified.jsonl | cặp đã lọc + `fact_score` |
| train.jsonl / test.jsonl | tập huấn luyện LoRA / tập đánh giá (giám khảo + 🧑 duyệt) |
| stats_gen.json, stats_verify.json | thống kê lọc |

Số lượng thực tế: xem `stats_verify.json` (lần chạy 2026-10-04: 4 910 cặp sau lọc tự động → 3 464 qua kiểm tra
sự thật → train 3 119 / test 345). Hạn chế: teacher 9B vẫn có thể sai; dữ liệu chỉ dùng để học *phong cách nói*,
kiến thức được đánh giá bằng benchmark độc lập (Global-MMLU vi).
