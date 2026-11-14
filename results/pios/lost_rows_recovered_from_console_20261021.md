# Số đo mà dòng gốc trong experiments.csv không còn (chép lại từ đầu ra màn hình lúc đo)
Lý do: các dòng này nằm trong `~/vieedge-src/results/experiments.csv` trên thẻ Pi OS (đã gỡ sạch theo yêu cầu) hoặc trên thẻ Yocto cũ (đã flash lại) trước khi kéo về. Chỉ có các con số bên dưới; không có file thô.

## Pi OS (O1), 13/10, 16 lượt, e2e_synth, tắt RAG, endpoint 400 ms, đường ống đầy đủ
| exp_id | model | WER câu hỏi | TTFT p50 (ms) | token/s | âm thanh đầu p50 / p95 / p99 (ms) | RAM (MB) |
|---|---|---|---|---|---|---|
| PIOS-O1-Q4_K_M | qwen3.5-0.8b Q4_K_M | 0,2957 | 359,2 | 12,40 | 1906 / 3865 / 3973 | 2445 |
| PIOS-O1-Q4_0 | qwen3.5-0.8b Q4_0 | 0,3441 | 281,1 | 13,62 | 2082 / 3820 / 4041 | 2375 |
(WER khác nhau giữa hai lần chạy cùng STT do thời điểm phát lẫn VAD/speculative; không phải do LLM.)

## Yocto-RT, Pi 192.168.196.96 (thẻ cũ), 12 lượt `e2e_cmd` giọng vais1000, đường nhanh bật/tắt, `first_audio_ms` từng lượt
* YO-CMD-llm2 (đường nhanh tắt): 2516, 3572, 2796, 1156 (bị từ chối), 2444, 3108, 3084, 2132, 2348, 1152 (bị từ chối), 1904, 3392
* YO-CMD-fast2 (đường nhanh bật; lượt đầu là khởi động nguội ghi cache âm thanh): 10764, 2092, 516, 528, 516, 2028, 524, 2324, 528, 528, 516, 524
