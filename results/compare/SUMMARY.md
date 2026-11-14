# Pi OS (O1) vs Yocto PREEMPT_RT (O4) — Raspberry Pi 5 8 GB, 2026-10-13

Cùng board, cùng bộ test `bench/compare_os.sh`, Zipformer + Qwen3.5-0.8B LoRA, endpoint 400 ms, cắt câu đầu 5 từ, tắt RAG.
Pi OS: Debian 12, kernel 6.12.93+rpt (PREEMPT, không cô lập lõi), llama.cpp build native.
Yocto: scarthgap, kernel 6.12.93-rt (PREEMPT_RT), `isolcpus=3 nohz_full=3 rcu_nocbs=3 irqaffinity=0-2`, llama.cpp recipe armv8.2-a+dotprod+fp16.

| Chỉ số | Pi OS | Yocto-RT | Ghi chú |
|---|---|---|---|
| Jitter lõi 3, rảnh, 5 phút (max / p99.999) | 18 / 15 µs | 16 / 12 µs | 300 000 mẫu |
| Jitter lõi 3, tải nặng, 5 phút (max) | 125 µs | **87 µs** (−30 %) | stress-ng 0-2 + LLM + spinner 40 % ở lõi 3 |
| Jitter tải nặng (p99 / p99.99 / p99.999) | 44 / 72 / 90 µs | 44 / 70 / 80 µs | gần như bằng nhau |
| Âm thanh đầu, yên (p50 / p95) | 1,91 / 3,24 s (Q4_K_M) ; 2,08 / 3,82 s (Q4_0) | 2,08 / 3,20 s (Q4_0) | 16 lượt; Q4_0 là cặp so sánh đúng |
| Âm thanh đầu, nhiễu 4 lõi (p50 / p95) | 10,0 / 22,9 s (Q4_K_M) | 6,8 / 16,4 s (Q4_0) | **khác model, chưa so được thẳng**; chủ yếu là tranh CPU |
| RAM dùng sau boot | 442–538 MB | 285 MB | |
| Tiến trình | 183 | 217 | Yocto nhiều hơn |
| Ảnh hệ điều hành (nén) | – | 229 MB (.wic.bz2) | Pi OS thẻ có 27 GB dữ liệu dự án khác, không so được |

Kết luận trung thực: Yocto-RT cải thiện đuôi jitter tải nặng ~30 % ở giá trị max và dùng ít RAM hơn ~35–45 %, còn p99–p99.999 và độ trễ pipeline khi yên **không khác trong sai số đo**.
Còn thiếu: Pi OS chạy lại với Q4_0 ở chế độ nhiễu; jitter dài (30–60 phút) để thấy đuôi; thời gian boot Yocto (`systemd-analyze` không có trong ảnh).

## Jitter 30 phút, tải nặng (Yocto-RT-O4, cyclictest lõi 3, 1 800 000 mẫu)
max 92 µs, p99 43 µs, p99.99 69 µs, p99.999 80 µs (5 phút trước đó: max 87 µs) → đuôi ổn định, không có đột biến theo thời gian. Pi OS chưa chạy 30 phút (5 phút: max 125 µs).

## Độ trễ trả lời trên Yocto-RT (12 lượt, tắt RAG, Q4_0, Zipformer)
| Cấu hình | Âm đầu tiên nghe thấy p50/p95 | Câu trả lời thật bắt đầu p50/p95 |
|---|---|---|
| Mặc định | 2,45 / 4,52 s | 2,36 / 4,43 s |
| + xác nhận tức thì ("Dạ.") | **0,53 / 1,15 s** | 2,44 / 3,95 s |
| + endpoint 300 ms + câu đầu 3 từ | **0,43 / 1,07 s** | **1,95 / 4,02 s** |
Xác nhận tức thì chỉ giảm độ trễ *cảm nhận*, không làm câu trả lời thật đến sớm hơn. Endpoint 300 ms chưa thử với giọng người thật (nguy cơ cắt ngang câu).

## Yocto-RT-O4, ảnh mới (14/10) trên thẻ 128 GB, Pi vào mạng ISLAB_C102_5G (đo 21/10), LLM Q4_0
| Chỉ số | Kết quả |
|---|---|
| Jitter lõi 3 rảnh, 5 phút (max / p99.999) | 13 / 9 µs |
| Jitter lõi 3 tải nặng, 5 phút (max / p99 / p99.99 / p99.999) | **85** / 49 / 69 / 80 µs (lần trước 87 µs) |
| Câu trả lời thật bắt đầu, yên, 16 lượt (p50 / p95) | 2,02 / 3,78 s |
| Câu trả lời thật bắt đầu, nhiễu 4 lõi (p50 / p95) | 6,5 / 17,8 s |
| Bộ 12 câu lệnh Go2, đường nhanh: tiếng đầu tiên (p50 / p95) | **0,52 / 2,29 s**; 9/12 câu trúng đường nhanh (≈0,52 s), 3/12 rơi về LLM (2 câu hỏi thường, 1 câu ASR nghe sai "xây" thay "xoay") |
Ghi chú: hai dòng `CMP-YOCTO-RT-O4-v2-*` trong experiments.csv chạy khi xác nhận tức thì còn bật nên `first_audio` là tiếng "Dạ.", dùng `CMP2-YOCTO-*` (đã tắt xác nhận và đường nhanh, so được với Pi OS).
Sửa trong đợt này: bỏ dấu câu trước khi khớp luật (STT thêm "." làm hụt lệnh), `compare_os.sh` dùng đúng file GGUF và tắt đường nhanh/xác nhận cho phép đo so sánh.

## Pi OS nguyên bản (O0: có màn hình desktop, governor `ondemand`), chỉ stress-ng, không cài thêm gì (21/10)
cyclictest lõi 3, SCHED_FIFO 80, 1 kHz, 5 phút, 300 000 mẫu; tải = stress-ng lõi 0–2 (cpu, vm, io) + spinner 40 % ở lõi 3. Không có LLM (không cài llama.cpp lên thẻ này).
| | max | p99 | p99.99 | p99.999 |
|---|---|---|---|---|
| rảnh | **114 µs** | 4 | 13 | 27 µs |
| tải stress-ng | 13 µs | 3 | 10 | 12 µs |
Khi rảnh, đỉnh jitter của Pi OS nguyên bản (114 µs) cao hơn Yocto-RT (13–16 µs); khi bị tải CPU luôn ở xung nhịp cao nên đỉnh thấp (13 µs). Đây **không cùng bài đo** với phép đo Yocto "tải nặng" (có LLM + hdd), nên không trừ trực tiếp được; cần chạy lại cùng script `/tmp/jit_stress.sh` trên Yocto khi cắm lại thẻ Yocto.
Script: không lưu trong repo trên thẻ; bản sao ở `bench/jit_stress.sh`.

## Pi OS nguyên bản (O0, `ondemand`, desktop) với cùng bài đo và cùng Q4_0 như Yocto-RT (21/10) — phép so sánh chính
Cài tạm trong `~/vieedge`, đo xong đã gỡ sạch (thẻ về lại 24 GB). llama.cpp cùng commit `7fe450e19`, build native trên Pi OS; Yocto dùng recipe `armv8.2-a+dotprod+fp16`.
| Chỉ số | Pi OS O0 | Yocto-RT O4 | Chênh |
|---|---|---|---|
| llama-bench Q4_0, nạp prompt / sinh (token/s) | 125,7 / 18,11 | chưa đo trên Yocto | – |
| Jitter lõi 3 rảnh, 5 phút (max / p99.999) | 33 / 15 µs | 13 / 9 µs | Yocto thấp hơn |
| Jitter lõi 3 tải nặng, 5 phút (max / p99.99 / p99.999) | 105 / 77 / 97 µs | **85** / 69 / 80 µs | Yocto thấp hơn ≈ 19 % ở max |
| Jitter lõi 3 tải nặng, 30 phút, 1,8 triệu mẫu (max / p99.999) | 127 / 99 µs | 92 / 80 µs (đo 13/10, Q4_K_M) | Yocto thấp hơn ≈ 28 % ở max |
| Câu trả lời thật bắt đầu, yên (p50 / p95) | **1,60 / 3,62 s** | 2,02 / 3,78 s | **Pi OS nhanh hơn ≈ 0,4 s** |
| Câu trả lời thật bắt đầu, nhiễu 4 lõi (p50 / p95) | 9,3 / 20,7 s | 6,5 / 17,8 s | Yocto nhanh hơn |
| LLM token đầu (TTFT, yên, p50) | 266 ms | chưa trích | – |
| Lệnh Go2 đường nhanh (p50) | 0,53 s | 0,52 s | bằng nhau (cùng mã) |

Kết luận trung thực: Yocto-RT chỉ thắng ở **đỉnh jitter của lõi âm thanh** (thấp hơn 19–28 %) và RAM; **độ trễ trả lời khi yên Pi OS nhanh hơn ≈ 0,4 s** trong lần đo này (n=16), cần tìm nguyên nhân (nghi: cách build llama.cpp, governor, Python 3.12 so với 3.11) bằng `llama-bench` trên Yocto. Không được viết "Yocto nhanh hơn" khi báo cáo.

## Galaxy Z Fold7 (Snapdragon 8 Elite) cùng model Q4_0, cùng llama.cpp (21/10) — xem `results/phone/fold7_llama_bench_20261021.md`
Pi 5 CPU 125,7 / 18,1 token/s (nạp prompt / sinh) → Fold7 CPU 634,9 / 90,7, GPU Adreno 1 008,9 / 70,0, **NPU Hexagon 2 011,7 / 63,2**.
Thời gian Python "dán" giữa các bước (từ lúc ngắt câu đến lúc gửi yêu cầu LLM): trung vị 12–13 ms trên mỗi lượt (Yocto 12,4 ms, Pi OS 13,3 ms) trong ≈ 2 000 ms, tức < 1 %.

## Ứng dụng Android chạy trọn vòng trên Fold7 (xem `results/phone/fold7_app_pipeline_20261021.md`)
Câu hỏi qua LLM, tiếng đầu tiên: 0,8B NPU 1,73–1,94 s, 0,8B GPU 1,59–1,81 s, **2B NPU 1,23–1,40 s** (Pi 5, 0,8B: ≈ 2,0 s). Lệnh đường nhanh 0,74–0,81 s. Bốn câu hỏi tổng hợp, chưa có giọng người.

## Chiến dịch điện thoại 27/10 (xem `results/phone/fold7_campaign_20261027.md`)
Tốt nhất để demo: 2B + NPU + giọng chuẩn + xác nhận tức thì: nghe tiếng đầu lúc 0,54 s, câu trả lời thật lúc ≈ 1,5–1,7 s; giọng nhanh và endpoint 300 ms hạ câu trả lời thật còn 1,28 s và tiếng đầu 0,42 s. Chạy liên tục 7,5 phút (62 lượt): NPU tối đa 65 °C, tốc độ không giảm. Nhận giọng trên máy WER 0,257 (laptop 0,250 trên cùng 12 câu).
