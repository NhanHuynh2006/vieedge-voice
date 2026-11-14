# RUNBOOK — chạy toàn bộ thí nghiệm trên Pi 5 + Hailo-8L

Mỗi lệnh ghi một dòng vào `results/experiments.csv` (+ chi tiết `results/raw/`). Mục 🧑 là việc người làm.
Giao thức chung (PLAN §9): tản nhiệt bật, governor `performance` (trừ thí nghiệm năng lượng), script tự ghi
`get_throttled` và nhiệt độ trước/sau; mỗi cấu hình end-to-end ≥ 100 lượt × 3 phiên.

## 0. Chuẩn bị 🧑

1. Phần cứng: Pi 5 8 GB, AI Kit/AI HAT+ Hailo-8L, tản nhiệt chủ động, nguồn 27 W, mic USB, loa USB/3.5 mm,
   nút nhấn GPIO17↔GND, LED GPIO22 (nghe) / 23 (nghĩ) / 24 (nói) qua điện trở 330 Ω, đồng hồ USB-C có log hoặc INA226 (I2C-1, 0x40).
2. Tài khoản Hailo Developer Zone → tải DFC 3.x (+ HailoRT wheel tuỳ chọn) vào `hailo_compile/wheels/`.
3. Trên laptop:
   ```bash
   docker build -t vieedge-dfc hailo_compile && ./hailo_compile/run_all.sh     # HEF PhoWhisper vi/en (S3, S4)
   ./scripts/stage_models.sh
   ```

## 1. Hệ điều hành

| Cấu hình | Cách tạo |
|---|---|
| O0 | Thẻ nhớ Raspberry Pi OS Lite 64-bit (bản có `hailo-all`), `deploy/scripts/pios_setup.sh` |
| O1 | như O0 + `pios_setup.sh --o1` (governor performance, tắt dịch vụ thừa) |
| O2 | `./yocto/build.sh` → flash |
| O3 | `./yocto/build.sh rt` → flash → trên Pi: `vieedge-osmode o3 && reboot` |
| O4 | ảnh RT, mặc định (`isolcpus=3 nohz_full=3 rcu_nocbs=3 irqaffinity=0-2`, IRQ USB → lõi 3, audio SCHED_FIFO 80) |

Flash (laptop): `bzcat <image>.wic.bz2 | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync` hoặc `sudo bmaptool copy <image>.wic.bz2 /dev/sdX`.
SSH: `root@<ip>` mật khẩu `vieedge` (đổi bằng `passwd`). Sau đó từ laptop: `./scripts/deploy_models.sh <ip>`.

Kiểm tra Hailo: `hailortcli fw-control identify` (phải thấy HAILO8L). Nếu Hailo chưa chạy ổn định trên Yocto
sau 5 ngày làm việc → **cổng PLAN §7.3**: đo cấu hình có NPU trên Pi OS (+ `pios_setup.sh --rt-kernel` cho O3/O4-PiOS),
Yocto dùng cho cấu hình thuần CPU; ghi rõ trong báo cáo.

## 2. STT (S0–S5) — trên Pi, `cd /opt/vieedge/bench`

```bash
C=/etc/vieedge/config.yaml
python3 bench_stt.py -c $C --exp S0 --set stt.backend=ct2 --set stt.ct2.model=stt/ct2/phowhisper-tiny-float32 --set stt.ct2.compute_type=float32 --set stt.ct2.window_s=30 --snr 10
python3 bench_stt.py -c $C --exp S1 --set stt.backend=ct2 --set stt.ct2.window_s=30 --snr 10
python3 bench_stt.py -c $C --exp S1w --set stt.backend=ct2 --set stt.ct2.window_s=10 --snr 10
python3 bench_stt.py -c $C --exp S2 --set stt.hybrid.hef=stt/hef/whisper-tiny-encoder-10s_h8l.hef --set stt.hybrid.decoder=stt/ct2/whisper-tiny-int8 --snr 10
python3 check_encoder_drift.py -c $C --hef stt/hef/phowhisper-tiny-encoder-10s_vi_h8l.hef --onnx stt/onnx/phowhisper-tiny-encoder-10s.onnx
python3 bench_stt.py -c $C --exp S3 --calib-lang vi --snr 20 10 5
python3 bench_stt.py -c $C --exp S3-beam3 --calib-lang vi --beam 3
python3 bench_stt.py -c $C --exp S4 --calib-lang en --set stt.hybrid.hef=stt/hef/phowhisper-tiny-encoder-10s_en_h8l.hef --snr 10
# base: thay tiny→base, cửa sổ 5 s (…base-encoder-5s_vi_h8l.hef, phowhisper-base-int8)
python3 bench_e2e.py -c $C --exp S5-on  --turns 100 --sessions 3
python3 bench_e2e.py -c $C --exp S5-off --turns 100 --sessions 3 --set stt.incremental.enabled=false
```
Câu hỏi end-to-end: `make_e2e_audio.py` (giọng tổng hợp khác giọng trợ lý) hoặc 🧑 mỗi thành viên đọc 30 câu vào điện thoại
→ `data/e2e/human/<tên>/*.wav + questions.txt` → `make_e2e_audio.py --human data/e2e/human --name human`.

## 3. LLM (M0–M5)

Các GGUF cho thang lượng tử hoá cần được chép lên trước (thêm ~8 GB):
`EXTRA_GGUF="qwen2.5-1.5b-vi-voice-F16 qwen2.5-1.5b-vi-voice-Q8_0 qwen2.5-1.5b-vi-voice-Q6_K qwen2.5-1.5b-vi-voice-Q5_K_M qwen2.5-1.5b-vi-voice-Q3_K_M" ./scripts/stage_models.sh && ./scripts/deploy_models.sh <ip>`

```bash
G=llm/gguf/qwen2.5-1.5b-vi-voice
python3 bench_llm.py -c $C --exp M0 --models $G-F16.gguf --server-bin /opt/llama-generic/bin/llama-server
python3 bench_llm.py -c $C --exp M1 --models $G-Q8_0.gguf $G-Q6_K.gguf $G-Q5_K_M.gguf $G-Q4_K_M.gguf $G-Q3_K_M.gguf
python3 bench_llm.py -c $C --exp M3 --models $G-Q4_K_M.gguf --draft llm/gguf/qwen2.5-0.5b-vi-voice-Q8_0.gguf
python3 bench_llm.py -c $C --exp M4 --models $G-Q4_K_M.gguf --no-cache
python3 bench_llm.py -c $C --exp M5 --models $G-Q4_K_M.gguf --threads 2 3 4            # chạy ở O2 (không cô lập) và O4
python3 bench_llm.py -c $C --exp M5-generic --models $G-Q4_K_M.gguf --server-bin /opt/llama-generic/bin/llama-server
```
Chất lượng (không phụ thuộc phần cứng, chạy trên laptop cho nhanh, có gắn nhãn `laptop`):
```bash
python bench/bench_llm.py -c deploy/config/vieedge-laptop.yaml --exp M1q --gpu --speed 0 --quality 400 --models <các GGUF>
python bench/bench_llm.py -c deploy/config/vieedge-laptop.yaml --exp M2 --gpu --speed 0 --answers 0 --models <nhỏ+LoRA> <lớn không LoRA>
scripts/run_teacher.sh &  python bench/judge.py results/raw/answers_M2_*.jsonl
python review_app/app.py --mode qa --file results/raw/answers_M2_<model>.jsonl --n 100      # 🧑 ~45 phút
```

## 4. TTS (T0–T2)
```bash
python3 bench_tts.py -c $C                     # T0/T1 thời gian tổng hợp + WAV
python bench/bench_tts.py -c deploy/config/vieedge-laptop.yaml --t2   # T2 + đọc ngược bằng ASR (laptop)
python review_app/app.py --mode mos --dir results/audio/mos_vi_VN-vais1000-medium     # 🧑 nhóm chấm 1–5, 20 câu
python review_app/app.py --mode numbers --dir results/audio/t2_norm                   # 🧑 30 câu chứa số
```

## 5. Toàn hệ thống (P1–P3)
```bash
python3 bench_e2e.py -c $C --exp P3-npu
python3 bench_e2e.py -c $C --exp P3-cpu --set stt.backend=ct2
python3 bench_e2e.py -c $C --exp P1-stream
python3 bench_e2e.py -c $C --exp P1-full --set pipeline.stream_sentences=false
for e in 300 500 800; do python3 bench_e2e.py -c $C --exp P2-$e --set vad.endpoint_ms=$e; done
python3 bench_e2e.py -c $C --exp E2E-live --live --turns 30 --sessions 1     # 🧑 loa → mic thật, phòng ồn
```

## 6. Hệ điều hành (O0–O4)
Trên mỗi thẻ nhớ / chế độ: `OS_CFG=O4 ./os_bench.sh 5` (5 phút mỗi phép đo) rồi `bench_e2e.py --exp P3-npu-O4 …`
để có first-audio p95/p99 của cấu hình đó. Thời gian khởi động: tự đo từ `/run/vieedge-ready`.

### So sánh Pi OS ↔ Yocto (dùng khi báo cáo)
Chạy **đúng một lệnh** như nhau trên mỗi hệ điều hành, cùng model và cùng config (`llm.model` giống nhau):
```bash
sudo bench/compare_os.sh PIOS-O1 5        # hoặc YOCTO-RT-O4 5: tĩnh + jitter 5 phút (rảnh/tải nặng) + e2e (yên/nhiễu)
sudo bench/jitter_long.sh YOCTO-RT-O4 30  # jitter dài 30 phút dưới tải
```
Kết quả: `results/compare/<tag>-<ngày>/` và `results/experiments.csv`; bảng tổng hợp ở `results/compare/SUMMARY.md`.

### Điện thoại làm micro + loa (không cần cắm thiết bị âm thanh vào Pi)
Pi chạy như máy chủ; điện thoại cùng mạng Wi-Fi với Pi. `audio.backend: auto` (mặc định trong ảnh Yocto): có thẻ âm thanh USB thì dùng ALSA, không có thì dùng điện thoại.
* **Web (mọi điện thoại, kể cả iPhone):** mở `https://<ip-pi>:8443/phone`, bấm "Nâng cao → Tiếp tục" để chấp nhận chứng chỉ tự ký (trình duyệt chỉ cho dùng micro trên https), rồi bấm "Bật micro và loa". Thêm vào màn hình chính để chạy như ứng dụng.
* **Ứng dụng Android:** `dist/VieEdgeVoice-snapdragon.apk (Fold7) hoặc VieEdgeVoice-generic.apk (máy arm64 khác)` (mã nguồn `android/`; build: `JAVA_HOME=<jdk17> gradle assembleDebug`). Cài (cho phép nguồn không rõ), nhập IP của Pi, bấm bật. Dùng `ws://` thẳng, không có cảnh báo chứng chỉ; micro nguồn VOICE_COMMUNICATION (khử vọng phần cứng).
* **Chạy trọn vòng trên điện thoại (không cần Pi):** mở ứng dụng, chọn "Chạy trên máy", chọn model và bộ xử lý (NPU Hexagon / GPU Adreno / CPU). Model nằm trong bộ nhớ riêng của ứng dụng (`files/models/{llm,stt,vad,tts}`), đẩy bằng adb (xem `android/README.md`). Native: llama.cpp build cho Snapdragon (`docs/backend/snapdragon` của llama.cpp, `android/native/build.sh` cho lớp JNI), sherpa-onnx cho nhận giọng và đọc.
* Thử không cần điện thoại: `python bench/phone_client.py --url ws://<ip>:8000/audio data/e2e/cmd/q002.wav` (giả lập điện thoại, in thời gian đến âm thanh đầu tiên).
* Công tắc "Tra cứu" (Wikipedia offline) ở đầu trang `/phone`: bật thì chính xác hơn nhưng câu trả lời thật chậm thêm 1,4–2,8 s (`results/phone/pi_phone_path_20261021.md`).
* Độ trễ: thêm khoảng 0,15 s so với loa/mic nối trực tiếp (mạng + bộ đệm phát 60 ms của điện thoại); đo trên laptop 3 lõi: câu trả lời qua LLM 1,2–1,4 s, lệnh đường nhanh 0,7 s kể từ lúc nói xong.

### Đường nhanh và xác nhận tức thì
`fastpath.enabled: true` (dữ liệu: `models/fastpath/faq.jsonl`, `say_phrases.txt`; lần chạy đầu ghi cache âm thanh vào `results/fastpath_cache/`, nên lượt đầu sau flash có thể chậm).
`pipeline.ack.enabled: true` phát "Dạ." trong lúc LLM nghĩ. Đo: `bench_e2e.py --manifest e2e_cmd` (lệnh Go2, sinh bằng `make_e2e_audio.py --source <jsonl> --name cmd`);
`answer_audio_ms` là lúc câu trả lời *thật* bắt đầu, `first_audio_ms` tính cả tiếng xác nhận.

## 7. Năng lượng 🧑
Cắm đồng hồ USB-C có log giữa nguồn và Pi; bắt đầu log trước khi chạy `bench_e2e.py`; đo thêm 5 phút rảnh.
Xuất CSV (cột `time` unix giây, `power` W) → `python bench/make_tables.py --meter meter.csv --turns results/turns/*.jsonl`.
Nếu có INA226, `telemetry.power: auto` tự đọc và `bench_e2e.py` ghi `power_w`, `j_per_turn`.

## 8. Báo cáo
```bash
rsync -av root@<ip>:/opt/vieedge/results/ results/pi/ && cat results/pi/experiments.csv >> results/experiments.csv
python bench/make_tables.py && python bench/make_plots.py      # docs/report/tables.md + figures/
```
