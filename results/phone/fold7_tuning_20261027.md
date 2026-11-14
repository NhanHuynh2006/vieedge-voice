# Tinh chỉnh trên Fold7 (27/10/2026): tra cứu Wikipedia offline, cắt câu đầu, luồng TTS
Cấu hình nền: Qwen3.5-2B LoRA Q4_0 (làm từ F16 có imatrix), NPU Hexagon, giọng Piper chuẩn, xác nhận "Dạ." bật. 12 câu hỏi tổng hợp, từ lúc nói xong.

## Tra cứu Wikipedia offline trên điện thoại
Cổng sang Kotlin từ `src/vieedge/rag` (cùng file SQLite FTS5 1,4 GB với Pi; SQLite hệ thống của Android không có FTS5 nên dùng bản `requery/sqlite-android`).
| | không tra cứu | có tra cứu |
|---|---|---|
| Thời gian tra cứu (p50 / max) | – | **96 / 134 ms** |
| Số token nạp prompt (p50) | 25 | 107 |
| Tiếng đầu nghe thấy p50 | 0,56 s | 0,66 s |
| Câu trả lời thật p50 | 1,69 s | 1,75 s |
| Lượt có dùng đoạn trích | 0 / 12 | 12 / 12 |
Trên Pi, tra cứu thêm 1,4–2,8 s; trên Fold7 chỉ thêm ≈ 0,06–0,1 s vì NPU nạp prompt ≈ 1.400 token/s. Vì vậy tra cứu bật mặc định trên điện thoại. (Tác dụng lên độ chính xác: tỉ lệ bịa 0,52 → 0,30 đo trên laptop, `docs/OPTIMIZATION_NOTES.md`.)

## Cắt câu đầu và luồng TTS
| first_chunk_words / luồng TTS / endpoint | câu trả lời thật p50 |
|---|---|
| 5 từ / 3 / 400 ms | 2,03 s (một lượt tới 5,0 s) |
| 3 từ / 3 / 400 ms | 1,60 s |
| **3 từ / 4 / 400 ms** | **1,53 s** |
| 3 từ / 4 / 300 ms | 1,55 s (không khác; tiếng đầu 0,57 s) |
Mặc định mới: 3 từ, 4 luồng TTS, endpoint 400 ms (300 ms không lợi rõ và có nguy cơ cắt ngang người nói chậm).

## Công suất khi chạy bằng pin (rút sạc, màn hình sáng, 9,4 phút, 78 lượt, 2B NPU + tra cứu + "Dạ.")
Dữ liệu thô: `raw/power_20261027.csv` (dòng/giây), `raw/power_turns_20261027.jsonl`. Dòng điện `current_now` nhiễu nên báo cả trung vị và trung bình đã cắt 5 %.
| | trung vị | trung bình cắt 5 % |
|---|---|---|
| Chờ (màn hình sáng, chưa nạp model) | 1,97 W | 3,39 W |
| Đang chạy trợ lý (liên tục) | 2,09 W | 3,12 W |
Kiểm tra chéo bằng mức pin (thô, mức pin tính nguyên %): 100 → 98 % trong 9,4 phút ≈ 0,34 Wh ≈ 2,2 W. Hai cách đo cho 2,2 W (mức pin) và 3,1 W (dòng điện, cắt 5 %): báo cáo là **2,2–3,3 W cho cả máy kể cả màn hình**. Cùng một lượt, máy chỉ tiêu thêm rất ít so với lúc chờ; Pi 5 đo được 3,2–3,3 W (chỉ riêng bo mạch, chưa tính loa/micro). Điện năng mỗi lượt ≈ 2,2 W × 9,4 phút / 78 lượt ≈ 16 J (gồm cả màn hình).
Hạn chế: số đo là cả điện thoại, gồm màn hình; không tách riêng NPU.

## Tai nghe nhiễu: ASR "tự chế" câu khi không ai nói
Hiện tượng: để yên, trợ lý vẫn trả lời. Đo lại ngay trên máy: trong 60 s phòng yên có 1–2 đoạn tiếng ồn qua VAD; một đoạn (1,3 s, RMS 0,003) bị Zipformer chép thành "đang có một chút" — một câu có nghĩa từ tiếng ồn, nếu không chặn sẽ được trả lời.
Cách xử lý (đã làm trên điện thoại và trên Pi):
1. Tắt tự động chỉnh âm lượng (AGC) của micro: nó nâng nền tiếng ồn khi yên và làm VAD kích hoạt.
2. Cổng RMS: đoạn có mức âm nhỏ hơn max(0,008; 2,5 lần nền tiếng ồn đo liên tục) bị bỏ qua, không trả lời, không nói "bạn nói lại". Tiếng nói qua không khí ở ≈ 1 m có RMS ≈ 0,02.
3. Câu chỉ một từ ("ừ", "alo") bị bỏ qua trừ khi là lệnh có sẵn ("dừng", "chào"); VAD cần nói tối thiểu 0,3 s.
Trên Pi: `vad.min_rms: 0.012`, `vad.min_words: 2` trong `config.py` (mã đã sửa, có test; Pi đang tắt nên chưa chép lên). `bench/phone_listen.py` để tái hiện (nghe phòng N giây, in số đoạn tới bộ nhận giọng).
