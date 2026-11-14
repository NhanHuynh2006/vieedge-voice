# PLAN — VieEdge-Voice: Trợ lý hỏi đáp bằng giọng nói tiếng Việt, chạy hoàn toàn trên Raspberry Pi 5 + Hailo-8L (13 TOPS), hệ điều hành Yocto + PREEMPT_RT

> **Dành cho Claude Code:** Dự án MỚI, độc lập, không kế thừa code/kiến trúc của dự án nào trước đó. Làm lần lượt từng Phase; cuối mỗi Phase báo cáo ngắn (đã làm gì, file nào, số liệu, việc tồn) rồi **dừng chờ xác nhận**.
> Mục 🧑 là việc người phải làm (mua đồ, đăng ký tài khoản, cắm thiết bị, đo điện, nói thử). Không giả lập kết quả cho các mục này.
> **Không bịa số liệu.** Mọi con số trong báo cáo lấy từ log trong `results/`. Số liệu tham khảo trong file này chỉ để so sánh.

---

## 0. Tóm tắt

**Chức năng (chỉ vậy, không hơn):** người dùng nói câu hỏi tiếng Việt → thiết bị nghe → hiểu → suy nghĩ → **phát giọng nói trả lời**. Không điều khiển robot, không xuất lệnh hành động. 100% offline.

**Phần cứng:** Raspberry Pi 5 + Hailo-8L 13 TOPS (AI Kit / AI HAT+ 13 TOPS).

**Ràng buộc quan trọng quyết định kiến trúc:**
- Hailo-8L **không chạy được LLM** (các ứng dụng GenAI của Hailo chỉ dành cho Hailo-10H). → **LLM chạy trên CPU Pi 5.**
- Hailo-8L **chạy được Whisper**: ứng dụng speech recognition chính thức của Hailo hỗ trợ Whisper tiny/base trên Hailo-8, 8L và 10H, dùng encoder/decoder HEF tách riêng.
- Cách nhanh nhất đã được cộng đồng kiểm chứng: **encoder Whisper trên Hailo-8L, decoder trên CPU** (decoder chạy trên NPU rất chậm vì không có KV cache) — nhanh hơn ~8,4 lần so với FasterWhisper trên CPU (Whisper tiny, tiếng Anh).
- Whisper tiny/base gốc yếu với ngôn ngữ ngoài tiếng Anh → cần mô hình chuyên tiếng Việt.

**Ba đóng góp kỹ thuật:**
1. **Đưa STT chuyên tiếng Việt (PhoWhisper) lên Hailo-8L:** biên dịch encoder PhoWhisper tiny/base sang HEF bằng bộ công cụ chuyển đổi Whisper của Hailo, lượng tử hóa INT8 với dữ liệu hiệu chỉnh tiếng Việt; decoder chạy CPU. Đo WER + tốc độ so với chạy hoàn toàn trên CPU.
2. **Phân công dị thể NPU (nghe) ↔ CPU (suy nghĩ + nói) và ASR tăng dần:** encoder chạy liên tục trên NPU *trong lúc người dùng còn đang nói*, nên khi người dùng ngừng nói thì văn bản gần như đã sẵn sàng; CPU dành cho LLM + TTS. LLM được nén nhiều mức, giải mã suy đoán, KV-cache tiền tố.
3. **Tối ưu hệ điều hành:** Yocto tối giản + PREEMPT_RT + cô lập lõi cho luồng âm thanh → đo jitter, xrun âm thanh, độ trễ p95/p99, thời gian khởi động, so với Raspberry Pi OS.

**Thông điệp:** *"Hỏi gì đáp nấy bằng tiếng Việt, hoàn toàn offline trên thiết bị vài triệu đồng; NPU lo phần nghe, CPU lo phần nghĩ, hệ điều hành thời gian thực giữ cho cuộc nói chuyện mượt."*

---

## 1. Đối chiếu thể lệ

| Tiêu chí (25% mỗi mục) | Dự án đáp ứng |
|---|---|
| Hiệu năng mô hình trên thiết bị biên | WER tiếng Việt, chất lượng câu trả lời, tokens/s, TTFT, thời gian tới âm thanh đầu tiên p50/p95/p99, RAM, W, J/lượt hỏi đáp |
| Thiết kế HW–SW + giao diện | Pi 5 + Hailo-8L + mic/loa; pipeline streaming đa luồng; dashboard realtime (transcript, câu trả lời, thác nước độ trễ, tải CPU/NPU, nhiệt, công suất) |
| Tối ưu/tăng tốc trên phần cứng | PhoWhisper INT8 trên Hailo-8L, phân công NPU/CPU, nén LLM nhiều mức, speculative decoding, build tối ưu Cortex-A76, Yocto + RT + cô lập lõi |
| Báo cáo & trình bày | Bảng/biểu đồ từng thí nghiệm, demo hỏi đáp trực tiếp |

Đúng nhóm ứng dụng trong thể lệ (nhận dạng giọng nói; giao tiếp người–máy). Suy luận hoàn toàn trên thiết bị.

---

## 2. Cơ sở từ tài liệu

**Whisper trên Hailo:**
- Hailo cung cấp ứng dụng speech recognition chạy trên Hailo-8/8L/10H, hỗ trợ biến thể Whisper base và tiny trên Hailo-8L.
- Repo `hailocs/hailo-whisper`: công cụ export → convert → evaluate Whisper tiny/base cho Hailo; chạy trên Ubuntu 22 x86; **dùng Dataflow Compiler (DFC) v3.x cho Hailo-8/8L**.
- Hybrid encoder-NPU / decoder-CPU: dự án `ktomanek/edge_whisper` đo ~8,4× nhanh hơn FasterWhisper (tiny, tiếng Anh); với tiny/10 s: encoder Hailo + decoder CPU ~131 ms, còn decoder trên Hailo ~1,3 s.
- Ghi nhận cộng đồng: decoder NPU không có KV cache (Hailo biên dịch chuỗi cố định), nên decoder CPU vừa nhanh hơn vừa chính xác hơn; whisper base/tiny gốc cho kết quả kém với ngôn ngữ không phải tiếng Anh. HEF encoder có cửa sổ cố định (ví dụ tiny 10 s, base 5 s).

**Tiếng Việt:**
- Whisper (Radford et al., ICML 2023).
- **PhoWhisper** (Le, Nguyen & Nguyen — VinAI, ICLR 2024 Tiny Papers): fine-tune Whisper trên 844 giờ tiếng Việt nhiều giọng vùng miền; có bản tiny (39M) và base (74M) **cùng kiến trúc với Whisper tiny/base** → về nguyên tắc dùng được pipeline chuyển đổi của Hailo.
- TTS: VITS (Kim et al., ICML 2021); Piper (dựa trên VITS) có 3 giọng tiếng Việt: `vi_VN-vais1000-medium` (tốt nhất), `vi_VN-25hours_single-low`, `vi_VN-vivos-x_low`.

**LLM trên CPU:** GPTQ (ICLR 2023), SmoothQuant (ICML 2023), AWQ (MLSys 2024), LoRA (ICLR 2022), QLoRA (NeurIPS 2023), Speculative Decoding (Leviathan et al., ICML 2023), MELTing Point — đánh giá LLM trên thiết bị (MobiCom 2024). Tham khảo: review độc lập đo Qwen 2.5 1.5B trên CPU Pi 5 ~11,7 tokens/s.

**Độ trễ hội thoại:** khoảng lặng giữa lượt nói của người ~200 ms (Stivers et al., PNAS 2009) → tối ưu **thời gian tới âm thanh đầu tiên**, không chỉ tokens/s.

**Real-time Linux:** PREEMPT_RT vào mainline từ Linux 6.12 (có ARM64). Reghenzani et al., ACM Computing Surveys 2019; De Wit & Paolillo, đánh giá RT Linux trên Raspberry Pi 5, OSPERT 2024.

---

## 3. Phần cứng

| Thiết bị | Ghi chú |
|---|---|
| Raspberry Pi 5 **8GB** | LLM ~1–2B lượng tử hóa + decoder STT + TTS |
| Hailo-8L 13 TOPS (đã có) | Chạy encoder STT |
| Tản nhiệt chủ động | LLM tải liên tục → dễ throttle |
| Nguồn USB-C 27W chính hãng | |
| 🧑 Mic USB tốt (ưu tiên có khử ồn/khử vang) + loa | Hội trường chung kết ồn |
| 🧑 Nút nhấn GPIO (push-to-talk) + LED trạng thái | Phương án chắc chắn khi demo |
| 🧑 Đồng hồ đo USB-C có ghi log hoặc INA226 | Đo công suất |
| Laptop Ubuntu x86 + RTX 4060 | Chạy Hailo DFC v3.x (biên dịch HEF), fine-tune LoRA, lượng tử hóa LLM, build Yocto |
| 🧑 Tài khoản Hailo Developer Zone | Tải DFC + HailoRT |

---

## 4. Kiến trúc

```
 Mic ─► [Audio In, SCHED_FIFO, lõi 3 cô lập] ─► ring buffer 16 kHz
                 │
                 ├─► [VAD + endpointing]  ◄── nút push-to-talk (tùy chọn wake-word)
                 │
                 └─► [ASR tăng dần] cứ mỗi ~0,5–1 s trong lúc người nói:
                       log-mel (CPU) → ENCODER PhoWhisper INT8 trên HAILO-8L → DECODER trên CPU
                       → văn bản tạm (hiện lên dashboard)
                                │ người ngừng nói → lần giải mã cuối
                                ▼
                       [Chuẩn hóa văn bản hỏi]
                                ▼
                       [LLM trên CPU (llama.cpp), lõi 0–2]
                         system prompt cố định đã nạp sẵn KV-cache
                         phong cách nói: ngắn, không markdown, không liệt kê ký hiệu
                                │ streaming token
                                ▼
                       [Tách câu] ─► [Chuẩn hóa văn bản cho TTS tiếng Việt:
                                      số, ngày giờ, đơn vị, viết tắt → chữ]
                                ▼
                       [TTS Piper vi_VN trên CPU] ─► [Audio Out, SCHED_FIFO] ─► Loa
 [Telemetry: timestamp từng stage, CPU từng lõi, NPU, RAM, nhiệt, công suất] ─► Dashboard
```

Nguyên tắc:
- **Streaming toàn tuyến:** LLM sinh xong câu nào → TTS đọc câu đó ngay.
- **Mô hình nạp sẵn** khi khởi động, không nạp lại giữa các lượt.
- **Chống tự nghe chính mình:** tắt/giảm thu mic khi loa đang phát (hoặc khử vang nếu mic hỗ trợ); cho phép ngắt lời bằng nút.
- **Trả lời "không biết"** khi câu hỏi ngoài khả năng thay vì bịa (đưa vào system prompt + LoRA).
- Mọi stage ghi timestamp (monotonic) → biểu đồ thác nước độ trễ từng lượt.

---

## 5. Mô hình

### 5.1 STT
| Biến thể | Nơi chạy | Vai trò |
|---|---|---|
| PhoWhisper tiny / base, CTranslate2 INT8 | CPU | Baseline thuần CPU |
| Whisper tiny / base gốc (HEF có sẵn của Hailo) | Encoder Hailo-8L + decoder CPU | Baseline NPU (đa ngôn ngữ, chưa chuyên tiếng Việt) |
| **PhoWhisper tiny / base, HEF tự biên dịch** | **Encoder Hailo-8L + decoder CPU** | **Cấu hình đề xuất** |

Việc biên dịch (trên laptop x86, Ubuntu 22, DFC v3.x):
- [ ] Clone `hailocs/hailo-whisper`, chạy đúng quy trình với Whisper gốc trước để chắc môi trường đúng.
- [ ] Thay trọng số bằng `vinai/PhoWhisper-tiny` / `-base` (cùng kiến trúc), export encoder ONNX với cửa sổ cố định (thử 5 s và 10 s), convert sang HEF cho `hailo8l`.
- [ ] **Hiệu chỉnh lượng tử hóa INT8 bằng audio tiếng Việt** (vài trăm đoạn từ tập train của bộ dữ liệu tiếng Việt, không lấy từ tập test). Ablation: hiệu chỉnh bằng audio tiếng Anh vs tiếng Việt → ảnh hưởng tới WER.
- [ ] Kiểm tra độ lệch đầu ra encoder HEF so với ONNX (cosine similarity trên tập kiểm tra) trước khi đo WER — có ghi nhận cộng đồng về lỗi "im lặng" khi đầu ra encoder lệch nhiều.
- [ ] Decoder PhoWhisper chạy CPU (ONNX Runtime hoặc CTranslate2) với KV cache, beam 1 vs 3.
- [ ] Nếu biên dịch PhoWhisper thất bại hoàn toàn → giữ Whisper gốc trên NPU + PhoWhisper trên CPU để so sánh, và báo cáo nguyên nhân.

### 5.2 LLM (CPU, llama.cpp, GGUF)
- Ứng viên: **Qwen2.5-1.5B-Instruct, Qwen2.5-0.5B-Instruct, Qwen3-1.7B, Qwen3-0.6B** (dùng chế độ không suy luận dài để trả lời nhanh). Claude Code kiểm tra thêm các mô hình nhỏ đa ngôn ngữ mới nhất tại thời điểm làm và đưa vào nếu hỗ trợ tiếng Việt tốt.
- Chọn mô hình bằng: điểm trên benchmark tiếng Việt (mục 8) + tokens/s + TTFT trên Pi 5.
- **LoRA/QLoRA** (trên laptop) cho phong cách hỏi đáp bằng lời: câu trả lời ngắn 1–3 câu, tự nhiên khi đọc to, không markdown, biết nói "mình không chắc". Dữ liệu: Claude Code sinh ~3.000 cặp hỏi–đáp tiếng Việt đa chủ đề bằng một LLM lớn làm "thầy", lọc tự động; 10% làm tập test.

### 5.3 TTS
- Piper `vi_VN-vais1000-medium` (chất lượng) và `vi_VN-25hours_single-low` (nhanh), qua piper hoặc sherpa-onnx.
- **Chuẩn hóa văn bản tiếng Việt trước TTS** (bắt buộc, ảnh hưởng lớn tới chất lượng nghe): số → chữ ("2026" → "hai nghìn không trăm hai mươi sáu"), ngày giờ, %, đơn vị, viết tắt phổ biến, bỏ ký tự markdown. Viết unit test cho module này.

---

## 6. Ladder thí nghiệm (mỗi nấc có ID, đo trên Pi 5 thật)

**STT:**
| ID | Nội dung |
|---|---|
| S0 | PhoWhisper tiny/base FP32 trên CPU (baseline) |
| S1 | PhoWhisper tiny/base INT8 CTranslate2 trên CPU |
| S2 | Whisper gốc tiny/base: encoder Hailo-8L + decoder CPU |
| S3 | **PhoWhisper tiny/base: encoder HEF Hailo-8L + decoder CPU** |
| S4 | S3 + hiệu chỉnh INT8 bằng audio Việt vs Anh |
| S5 | ASR tăng dần trong lúc nói vs chỉ giải mã sau khi ngừng nói → độ trễ sau khi ngừng nói |

**LLM:**
| ID | Nội dung |
|---|---|
| M0 | Mô hình chọn, FP16 GGUF, build llama.cpp mặc định |
| M1 | Q8_0 / Q6_K / Q5_K_M / Q4_K_M / Q3_K_M → chất lượng vs tokens/s vs RAM |
| M2 | Mô hình nhỏ + LoRA vs mô hình lớn hơn không LoRA |
| M3 | Speculative decoding (bản nhỏ làm draft cho bản lớn) |
| M4 | KV-cache tiền tố cho system prompt → TTFT |
| M5 | Build tối ưu Cortex-A76 (dotprod, fp16), số thread 2/3/4 khi có/không cô lập lõi |

**TTS & hệ thống:**
| ID | Nội dung |
|---|---|
| T0–T1 | TTS medium vs low → thời gian tới mẫu âm thanh đầu tiên; 🧑 nhóm chấm điểm nghe 1–5 trên 20 câu |
| T2 | Có/không chuẩn hóa văn bản → tỉ lệ đọc sai số/ngày (🧑 nghe kiểm 30 câu chứa số) |
| P1 | Streaming theo câu vs chờ toàn bộ câu trả lời |
| P2 | VAD endpointing 300/500/800 ms → cắt lời vs độ trễ |
| P3 | Toàn hệ thống: thuần CPU vs NPU-nghe/CPU-nghĩ |

**Hệ điều hành:**
| ID | Nội dung |
|---|---|
| O0 | Raspberry Pi OS Lite mặc định (phiên bản hỗ trợ Hailo-8L chính thức — kiểm tra tài liệu Raspberry Pi hiện hành) |
| O1 | O0 + tinh chỉnh (governor performance, tắt dịch vụ thừa) |
| O2 | Yocto tối giản, kernel thường |
| O3 | Yocto + PREEMPT_RT |
| O4 | Yocto + PREEMPT_RT + cô lập lõi audio (isolcpus/nohz_full/rcu_nocbs) + IRQ affinity + SCHED_FIFO |

Đo O0–O4: thời gian khởi động tới "sẵn sàng nghe", RAM/CPU nền, cyclictest/`rtla timerlat` max latency **khi LLM đang chạy hết tải**, xrun âm thanh/giờ, thời gian tới âm thanh đầu tiên p95/p99, tokens/s (RT có thể giảm nhẹ throughput — báo cáo trung thực).

---

## 7. Yocto + PREEMPT_RT

### 7.1 Layer & image
- Poky (bản hỗ trợ Pi 5 trong `meta-raspberrypi`) + `meta-openembedded` (meta-oe, meta-python, meta-multimedia, meta-networking) + `meta-raspberrypi` (`MACHINE = "raspberrypi5"`) + layer riêng `meta-vieedge`.
- Image từ `core-image-minimal` + Python 3, ALSA (không PulseAudio/PipeWire nếu không cần), openssh, rt-tests, rtla, stress-ng.
- `DEFAULTTUNE` Cortex-A76; recipe build **llama.cpp**, **CTranslate2**, **onnxruntime**, **piper/sherpa-onnx** với cờ ARMv8.2 (dotprod, fp16) + LTO.

### 7.2 Kernel
- `linux-raspberrypi` ≥ 6.12, fragment `CONFIG_PREEMPT_RT=y`, `CONFIG_NO_HZ_FULL`, `CONFIG_RCU_NOCB_CPU`, governor performance mặc định; bật `CONFIG_TIMERLAT_TRACER` cho bản đo latency, tắt debug nặng cho bản đo hiệu năng.
- Cmdline: `isolcpus=3 nohz_full=3 rcu_nocbs=3`; IRQ USB audio → lõi 3; luồng audio `SCHED_FIFO` ưu tiên 80; LLM/decoder/TTS ghim lõi 0–2 (cpuset).

### 7.3 Hailo-8L trên Yocto
- Hailo cung cấp `meta-hailo` với recipe PCIe driver, firmware, HailoRT, pyHailoRT; các nhánh hỗ trợ (tính đến 04/2024): Dunfell, Kirkstone, Mickledore (chỉ HailoRT). Hailo-8L dùng chung dòng HailoRT 4.x với Hailo-8.
- Bản Yocto đủ mới để hỗ trợ Pi 5 có thể mới hơn các nhánh này → có thể phải sửa `LAYERSERIES_COMPAT` và recipe (đã có người làm tương tự khi tích hợp vào bản Yocto khác). **Phiên bản driver, firmware, HailoRT và phiên bản DFC dùng biên dịch HEF phải khớp nhau.**
- **Cổng kiểm soát 5 ngày làm việc:** nếu Hailo-8L chưa chạy ổn định trên Yocto → dùng Raspberry Pi OS Lite + kernel RT tự build + tinh chỉnh O1/O4 cho cấu hình có NPU; Yocto vẫn dùng để đo cấu hình thuần CPU. Ghi rõ trong báo cáo.

### 7.4 Việc Claude Code làm
- [ ] `yocto/kas.yml` + `meta-vieedge/` (image, kernel fragment, recipe ứng dụng, systemd unit tự chạy trợ lý khi khởi động).
- [ ] `build.sh`, hướng dẫn flash; dùng sstate-cache.
- [ ] `os_bench.sh`: boot time, RAM/CPU nền, cyclictest + rtla dưới `stress-ng` và dưới tải LLM thật, đếm xrun ALSA.
- [ ] 🧑 Flash, cắm Pi, chạy script (hoặc Claude Code chạy qua SSH nếu Pi có mạng).

---

## 8. Dữ liệu đánh giá

| Mục đích | Nguồn | Ghi chú |
|---|---|---|
| WER tiếng Việt | Tập test **VIVOS**, **Common Voice tiếng Việt** | Kiểm tra giấy phép khi tải |
| WER trong ồn | Tập test trên trộn nhiễu công khai (đám đông, quán cà phê) ở SNR 20/10/5 dB | Mô phỏng hội trường |
| Hiệu chỉnh INT8 encoder | Tập **train** của bộ dữ liệu tiếng Việt (không dùng tập test) | |
| Kiến thức LLM tiếng Việt | Benchmark trắc nghiệm tiếng Việt công khai (ví dụ VMLU) — Claude Code xác minh nguồn và giấy phép trước khi dùng | Đo mức tụt điểm theo từng mức lượng tử hóa |
| Chất lượng trả lời bằng lời | 10% tập hỏi–đáp tự sinh (≥ 200 câu); chấm bằng LLM lớn làm giám khảo trên laptop + 🧑 duyệt nhanh 100 câu (~45 phút) | Độ đúng, độ ngắn gọn, dễ nghe, tỉ lệ bịa |
| End-to-end giọng thật | 🧑 tùy chọn: mỗi thành viên đọc 30 câu hỏi vào điện thoại (~5 phút/người) | Nếu không có: phát audio test qua loa → mic, ghi rõ hạn chế |

---

## 9. Giao thức đo
- Tản nhiệt bật; governor `performance` (trừ thí nghiệm năng lượng); kiểm tra `vcgencmd get_throttled` trước/sau mỗi lần đo; ghi nhiệt độ.
- Mỗi cấu hình ≥ 100 lượt hỏi đáp tự động, lặp 3 phiên; báo mean ± std, p50/p95/p99.
- Timestamp: người ngừng nói (VAD) → văn bản cuối → token LLM đầu → câu đầu xong → **mẫu âm thanh đầu tiên phát ra** → hết câu trả lời.
- Năng lượng: 🧑 đồng hồ ngoài + ước lượng PMIC; J/lượt = W × thời gian lượt; đo cả nền khi rảnh.
- `results/experiments.csv`: `exp_id, date, os_cfg, stt_model, stt_where, stt_prec, calib_lang, llm_model, llm_quant, lora, spec_dec, threads, wer, wer_noisy, llm_bench_acc, answer_score, ttft_ms, tok_s, first_audio_p50, first_audio_p95, first_audio_p99, ram_mb, temp_max, power_w, j_per_turn, xruns_per_h, cyclictest_max_us, notes, git_commit`.

Mục tiêu tham khảo (điều chỉnh sau baseline, **không phải kết quả**): thời gian tới âm thanh đầu tiên p95 < 1,5 s; 0 xrun/giờ ở O4.

---

## 10. Dashboard & demo
- [ ] Web (FastAPI + WebSocket, mở trên điện thoại qua hotspot riêng): chữ hiện dần khi đang nói, câu trả lời, **thác nước độ trễ từng lượt**, CPU từng lõi, trạng thái NPU, RAM, nhiệt, công suất, xrun.
- [ ] Chế độ demo: push-to-talk, LED trạng thái (đang nghe / đang nghĩ / đang nói), lịch sử hỏi đáp.
- [ ] Chế độ so sánh trên sân khấu: thuần CPU vs NPU-nghe/CPU-nghĩ; Pi OS gốc vs Yocto RT (2 thẻ nhớ hoặc 2 Pi) khi chạy tải nặng.
- [ ] Không phụ thuộc internet.

---

## 11. Repo
```
vieedge-voice/
├── PLAN.md
├── yocto/            kas.yml, meta-vieedge/
├── hailo_compile/    scripts dùng hailo-whisper để export/convert PhoWhisper → HEF (chạy trên laptop x86)
├── src/vieedge/
│   ├── audio/        capture.py, playback.py, vad.py, echo_guard.py
│   ├── stt/          cpu_ct2.py, hailo_encoder.py, cpu_decoder.py, incremental.py  (chung interface)
│   ├── llm/          llamacpp_stream.py, prompts.py
│   ├── tts/          vi_normalize.py, piper_tts.py
│   ├── pipeline.py
│   ├── telemetry/    timeline.py, sysmon.py, power.py
│   └── web/
├── training/         gen_qa.py, lora_train.py, merge_quantize.py
├── data/             asr_test/, calib/, noise/, qa/
├── bench/            bench_stt.py, bench_llm.py, bench_tts.py, bench_e2e.py, os_bench.sh, judge.py, make_tables.py, make_plots.py
├── review_app/       công cụ duyệt nhanh
├── results/
└── docs/             proposal_round1.md, report/, poster/, qa_prep.md, REFERENCES.md
```

---

## 12. Lộ trình

| Phase | Nội dung | Thời lượng | Đầu ra |
|---|---|---|---|
| P0 | 🧑 Mic, loa, nút, đồng hồ đo; 🧑 đăng ký Hailo Developer Zone. Claude Code: repo, đề xuất vòng 1 | 3–5 ngày | Repo, `proposal_round1.md` |
| P1 | Pipeline thuần CPU trên Raspberry Pi OS: mic → PhoWhisper → LLM → Piper → loa | 1 tuần | Demo hỏi đáp đầu tiên; baseline S0/S1, M0, O0 |
| P2 | Whisper gốc trên Hailo-8L (S2); biên dịch PhoWhisper → HEF (S3, S4); ASR tăng dần (S5) | 1,5–2 tuần | Bảng STT |
| P3 | Sinh dữ liệu hỏi–đáp, LoRA, chọn LLM, ladder M0–M5; chuẩn hóa văn bản + T0–T2 | 1,5 tuần | Bảng LLM, TTS |
| P4 | Yocto → RT → cô lập lõi; Hailo-8L trên Yocto (cổng 5 ngày) | 2 tuần (song song P2–P3) | Ảnh Yocto, bảng O0–O4 |
| P5 | Dashboard, chế độ demo, chống tự nghe, chế độ so sánh | 1 tuần | Prototype vòng 2 |
| P6 | Đo toàn bộ theo mục 9, 🧑 duyệt nhanh, báo cáo, poster, luyện phản biện | 1 tuần | Hồ sơ chung kết |

---

## 13. Rủi ro & phương án
| Rủi ro | Phương án |
|---|---|
| PhoWhisper không biên dịch được sang HEF / WER tụt mạnh sau INT8 | Thử cửa sổ 5 s/10 s, hiệu chỉnh bằng audio Việt, thử các tùy chọn tối ưu của DFC; nếu vẫn thất bại → PhoWhisper INT8 trên CPU, báo cáo kết quả so sánh |
| Câu hỏi dài hơn cửa sổ encoder | Chia đoạn theo VAD; câu hỏi thường ngắn |
| LLM nhỏ trả lời tiếng Việt sai/bịa | LoRA, system prompt khuyến khích "không chắc", giới hạn độ dài; báo cáo tỉ lệ bịa trung thực |
| Hailo-8L trên Yocto không chạy | Cổng 5 ngày → Pi OS Lite + RT kernel cho cấu hình NPU |
| RT kernel giảm tokens/s | Báo cáo trung thực; nhấn mạnh p99 và xrun |
| Hội trường ồn, thiết bị tự nghe giọng mình | Mic gần miệng, push-to-talk, echo guard, thử SNR thấp trước |

---

## 14. Câu hỏi phản biện (Claude Code soạn `docs/qa_prep.md`)
- Sao không dùng cloud? → riêng tư, không cần mạng, độ trễ ổn định, chi phí vận hành 0.
- Sao LLM không chạy trên NPU? → Hailo-8L không hỗ trợ LLM; NPU được dùng đúng chỗ mạnh nhất (encoder STT), giải phóng CPU cho LLM.
- Sao decoder STT không chạy trên NPU? → không có KV cache trên NPU, số liệu cho thấy CPU nhanh hơn (dẫn nguồn + số đo của nhóm).
- RT kernel có làm AI nhanh hơn không? → Không; làm độ trễ **ổn định** (p99, xrun) — bảng O0–O4.
- INT8 làm STT kém đi bao nhiêu? → bảng S3/S4.
- Đo chất lượng câu trả lời thế nào? → benchmark tiếng Việt + tập hỏi đáp có người duyệt.

---

## 15. Tài liệu tham khảo
1. Radford et al., *Robust Speech Recognition via Large-Scale Weak Supervision* (Whisper), ICML 2023.
2. Le, Nguyen & Nguyen, *PhoWhisper: Automatic Speech Recognition for Vietnamese*, ICLR 2024 Tiny Papers, arXiv:2406.02555.
3. Kim, Kong & Son, *VITS*, ICML 2021.
4. Frantar et al., *GPTQ*, ICLR 2023.
5. Xiao et al., *SmoothQuant*, ICML 2023.
6. Lin et al., *AWQ*, MLSys 2024.
7. Hu et al., *LoRA*, ICLR 2022; Dettmers et al., *QLoRA*, NeurIPS 2023.
8. Leviathan, Kalman & Matias, *Fast Inference from Transformers via Speculative Decoding*, ICML 2023.
9. Laskaridis et al., *MELTing Point: Mobile Evaluation of Language Transformers*, MobiCom 2024.
10. Stivers et al., *Universals and cultural variation in turn-taking in conversation*, PNAS 2009.
11. Reghenzani, Massari & Fornaciari, *The Real-Time Linux Kernel: A Survey on PREEMPT_RT*, ACM Computing Surveys 2019.
12. De Wit & Paolillo, *A Preliminary Assessment of the Real-Time Capabilities of Real-Time Linux on Raspberry Pi 5*, OSPERT 2024.
13. Tài liệu kỹ thuật: hailo-apps speech_recognition (Hailo-8/8L/10H); hailocs/hailo-whisper; ktomanek/edge_whisper; meta-hailo; meta-raspberrypi; Piper voices vi_VN.

---

## 16. Quy ước cho Claude Code
- Python 3.11+, type hints, `ruff`; C/C++ qua CMake, ghi rõ cờ tối ưu.
- STT/LLM/TTS có interface chung; đổi CPU ↔ NPU bằng cấu hình, không sửa code.
- Không commit mô hình, dữ liệu, khóa; ghi `git_commit` vào mọi dòng thí nghiệm.
- Bước cần phần cứng/người (🧑): in hướng dẫn cụ thể rồi dừng.
