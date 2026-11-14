# Tối ưu độ chính xác và tốc độ: tài liệu → áp dụng → số đo

Không có hệ thống nào "không sai gì": mô hình nhỏ chạy trên Pi sẽ vẫn nghe nhầm và bịa. Mục tiêu của tài liệu này là
giảm lỗi tối đa **đo được bằng số**, và để hệ thống biết khi nào nó không chắc. Mọi số đo ở đây là trên laptop
(`os_cfg = laptop`) và nằm trong `results/experiments.csv`; số trên Pi phải đo lại theo `docs/RUNBOOK.md`.

| # | Vấn đề | Tài liệu | Áp dụng | Kết quả đo |
|---|---|---|---|---|
| 1 | STT tiếng Việt sai nhiều (PhoWhisper-tiny WER 0,158 trên VIVOS) | Zipformer-30M RNN-T, 6.000 giờ tiếng Việt (hynt/Zipformer-30M-RNNT-6000h): tác giả báo WER 8–12% trên VLSP, thấp hơn PhoWhisper-Large | Backend STT `zipformer` (sherpa-onnx, int8, CPU) | **VIVOS WER 0,041** (so với 0,158); ở nhiễu 5 dB 0,059 (so với 0,224); 29 ms mỗi câu, nhanh hơn 3,5 lần (exp S6) |
| 2 | LLM kém bền khi câu hỏi có lỗi nhận dạng | Mousavi et al. 2024 "Are LLMs Robust for Spoken Dialogues?" (arXiv 2401.02297); Sun et al. 2023 (arXiv 2311.07418): fine-tune trên dữ liệu có nhiễu ASR mô phỏng | LoRA trộn câu hỏi sạch + câu hỏi đã qua TTS→nhiễu→STT (`training/make_asr_noisy_qa.py`, `lora_train.py --asr-aug`) | Điểm giám khảo trên câu hỏi qua STT PhoWhisper: 2,24 → 2,38 (+0,14); trên câu sạch 3,64 → 3,48 (−0,16). **Lợi ích nhỏ, có cái giá** → không dùng làm mặc định (exp NOISY/CLEAN) |
| 3 | Trả lời bừa khi nghe không rõ | Ngưỡng avg_logprob của Whisper; Naderi et al., Interspeech 2024 (arXiv 2407.21414): dùng độ tin cậy ASR để chỉ xử lý câu không chắc | `stt.min_confidence`: dưới ngưỡng thì nói "bạn nói lại giúp mình" (`bench/bench_confidence.py`) | PhoWhisper: AUROC 0,87; ngưỡng −0,15 từ chối 11–17% câu có WER ≈ 0,5, câu được nhận WER 0,152→0,111. Zipformer: AUROC 0,84, ngưỡng −0,20 từ chối 4,7% |
| 4 | Độ trễ đến âm thanh đầu | Apple ChipChat (arXiv 2509.00078): TTS bắt đầu sau 5 từ; nạp trước (prefill) prompt; ngắt lời | Cắt câu TTS đầu sau 5 từ; KV-cache system prompt; barge-in có sẵn | Trên 3 lõi: 3,20 s → 2,52 s (chỉ riêng cắt câu), 1,70 s khi thêm mô hình 0,8B |
| 5 | LLM chậm trên CPU | Giải mã suy đoán (Leviathan et al. 2023) | Thử llama.cpp `-md` với bản 0,5B làm nháp | **Không nhanh hơn** (13,9 so với 14,3 token/s) → không dùng |
| 6 | Cửa sổ STT cố định tốn tính toán | Whisper được huấn luyện với cửa sổ 30 s | Thử cửa sổ thích ứng 3/5/8/10 s | **WER tăng gấp đôi** (0,158 → 0,354), bỏ |
| 7 | Mô hình nhỏ thiếu kiến thức, hay bịa | RAG giảm bịa trên thiết bị (Lancaster 2025, arXiv 2506.21568; benchmark CPU-only arXiv 2606.30062) | `src/vieedge/rag/`: Wikipedia tiếng Việt → SQLite FTS5 (BM25, không phân biệt dấu), tìm theo cụm tiêu đề rồi theo nội dung; chèn 240 ký tự vào lượt người dùng; công tắc bật/tắt trên dashboard | Tỉ lệ bịa 0,52 → 0,30 (câu qua STT), 0,30 → 0,18 (câu gõ); điểm 2,73 → 2,99; truy hồi 9 ms nhưng **thêm ~0,6 s** âm thanh đầu trên laptop (exp RAG*) |

## Các hướng đã cân nhắc nhưng chưa làm, kèm lý do
* **Chưng cất / nén thêm cho STT** (Distil-Whisper, arXiv 2311.00430): kết quả công bố cho tiếng Anh; Zipformer-vi đã nhỏ (30M) và chính xác hơn nên không cần.
* **Lượng tử thấp hơn cho LLM**: số đo của chúng tôi cho thấy Q3_K_M mất rõ (Qwen3.5-2B 0,485 → 0,37); phù hợp tài liệu rằng mô hình nhỏ chịu 4-bit kém hơn mô hình lớn. Giữ Q4_K_M trở lên.
* **LocalAgreement (Whisper-Streaming, Macháček et al. 2023)**: hữu ích khi hiển thị chữ ổn định và khởi động LLM sớm; với Zipformer (29 ms) lợi ích nhỏ.
* **Mô hình nói-nghe trực tiếp (LLaMA-Omni, Moshi)**: độ trễ thấp nhưng WER cao hơn và cần GPU; không phù hợp Pi 5.

## Điểm cần nói thẳng khi báo cáo
* Zipformer-vi có giấy phép **CC BY-NC-ND 4.0** (phi thương mại, không chỉnh sửa) — dùng cho nghiên cứu/cuộc thi, không dùng cho sản phẩm bán.
* Zipformer chạy trên **CPU**, nên không dùng NPU Hailo. Với RTF 0,008 thì NPU không còn cần cho tốc độ; đóng góp "PhoWhisper trên Hailo" vẫn là một so sánh nghiên cứu (cần HEF) chứ không còn là cấu hình tốt nhất. Hai đường cùng có trong mã, chọn bằng `stt.backend`.
* Ngưỡng tin cậy hiệu chỉnh trên đường CPU; đường encoder Hailo-INT8 phải hiệu chỉnh lại.
* VIVOS có thể trùng một phần nguồn với dữ liệu huấn luyện của Zipformer (tác giả không liệt kê VIVOS, nhưng không chắc); FLEURS chắc chắn có trong tập huấn luyện của nó nên không dùng để so sánh.

## Kết quả đo từ đầu đến cuối (345 câu hỏi test, giọng TTS khác giọng huấn luyện, LLM Qwen3.5-0.8B LoRA Q4_K_M)

| Đầu vào cho LLM | WER câu hỏi | Điểm giám khảo (1–5) | Tỉ lệ bịa |
|---|---|---|---|
| Câu hỏi gõ (sạch) | 0 | 3,64 | 0,30 |
| Qua STT PhoWhisper-tiny | 0,325 | 2,24 | 0,63 |
| Qua STT Zipformer-vi | 0,188 | **2,73** | 0,52 |
| Qua PhoWhisper + LoRA huấn luyện nhiễu | 0,325 | 2,38 | 0,54 |

Kết luận: lỗi nhận dạng giọng là nguồn mất chính xác lớn nhất (3,64 → 2,24); đổi sang Zipformer lấy lại gần một phần ba khoảng cách, và
phần còn lại phụ thuộc chất lượng giọng đọc của bộ test (giọng TTS khó hơn giọng người: Zipformer sai 19% trên giọng TTS nhưng chỉ 4% trên
giọng người thật VIVOS). Cần đo lại bằng giọng người thật ghi âm trên điện thoại (RUNBOOK §2) để có số cuối cùng.

Độ trễ (3 lõi, laptop, 16 lượt, tắt cổng tin cậy): STT PhoWhisper 1,10 s, Zipformer 1,15 s — bằng nhau vì STT bị giấu trong thời gian chờ ngắt câu
trên máy nhanh. Trên Pi, PhoWhisper-tiny mất 0,7–1,7 s cho STT nên lợi thế của Zipformer (RTF 0,008) dự kiến lớn hơn; **chưa đo trên Pi**.

## Biên dịch encoder PhoWhisper-tiny cho Hailo-8L (DFC 3.34, đo ngày 2026-10-13)
Độ lệch encoder lượng tử so với ONNX trên 100 câu VIVOS (cosine trung bình / thấp nhất), 1024 mẫu hiệu chỉnh tiếng Việt:

| Cấu hình | Cosine TB | Thấp nhất | Kết luận |
|---|---|---|---|
| INT8, không fine-tune (`no16-nofinetune`) | 0,842 | 0,789 | chưa dùng được |
| INT8 + fine-tune lượng tử (QAFT) 6 epoch trên GPU, batch 2 (`no16`) | 0,655 | 0,523 | **tệ hơn** |

Cả hai HEF đều biên dịch được (19–20 MB) nhưng chưa đạt ngưỡng 0,9, nên **không dùng cho đường STT mặc định** và chưa có WER trên Hailo thật. Nguyên nhân khả dĩ: các lớp a16 của hailo-whisper bị bỏ vì DFC 3.34 không hỗ trợ `precision_change`. Backend mặc định vẫn là Zipformer trên CPU.

## Chọn định dạng lượng tử cho llama.cpp trên Cortex-A76 (đo trên Pi 5, Pi OS, 3 luồng, 2026-10-13)
Pi 5 có dotprod nhưng không có i8mm; llama.cpp tự "repack" trọng số Q4_0/IQ4_NL sang bố cục 4x4 chạy bằng dotprod, còn Q4_K_M thì không.

| Định dạng | pp128 (token/s) | tg64 (token/s) | MCQ Global-MMLU-vi (n=400) |
|---|---|---|---|
| Q4_K_M | 87,9 | 16,2 | 0,333 |
| **Q4_0** | **125,3** | **18,2** | 0,308 |
| IQ4_NL | 96,0 | 17,6 | 0,340 |
| Q8_0 | – | – | 0,393 |

Sai số chuẩn của MCQ khoảng ±2,4 điểm phần trăm nên chênh lệch giữa ba định dạng 4-bit (Q4_0 thấp hơn Q4_K_M 2,5 điểm) **chưa có ý nghĩa thống kê**; Q8_0 hơn rõ nhưng gần gấp đôi dung lượng và chậm hơn. Tất cả làm từ cùng một F16 sau khi gộp LoRA (`training/merge_quantize.py`); tốc độ pp/tg ở bảng đo trên bản làm từ Q8_0 (cùng định dạng và kích thước), chưa đo lại trên bản từ F16. Nếu muốn chắc về độ chính xác thì dùng IQ4_NL (0,340, pp +9 %, tg +9 %). Đầu cuối (16 lượt, tắt RAG): TTFT 359 → 281 ms, 12,4 → 13,6 token/s, nhưng âm thanh đầu p50 1,91 → 2,08 s, tức **không cải thiện trong sai số đo** vì độ trễ này chủ yếu nằm ở chỗ khác (chờ ngắt câu, TTS).
Engine khác đã cân nhắc: T-MAC (Wei et al., EuroSys 2025) tăng tốc cho mô hình bit thấp (BitNet/2-3 bit) nên không áp dụng cho mô hình 4-bit; ik_llama.cpp chỉ có số liệu x86; KleidiAI cần i8mm/SME2 mà Pi 5 không có. llama.cpp vẫn là lựa chọn thực tế.

## Đường nhanh (fast path): câu có dữ liệu sẵn trả lời không qua LLM (đo 2026-10-13/14)
`src/vieedge/fastpath/`: luật phản xạ Go2 (port nguyên từ `Go2_assitant/reflex_matcher.py`, `combo_matcher.py`) + tập hỏi–đáp có sẵn (`data/fastpath/faq.jsonl`, 149 dòng lấy từ dataset Go2: chitchat/từ chối/hành động/dừng) → phát **âm thanh đã tổng hợp sẵn** (cache đĩa), hành động robot đẩy ra sự kiện `reflex` và `results/reflex_actions.jsonl`. Câu không khớp đi tiếp RAG + LLM.
* Độ phủ trên 300 lệnh test Go2: 255/300 (85 %) giải không cần LLM. Hiện tượng "cướp câu": 0/345 câu hỏi kiến thức trong tập test QA (có chốt chặn: dấu hiệu câu hỏi, đuôi "...không?").
* Độ trễ trên Pi Yocto-RT (âm đầu tiên sau khi nói xong): **0,52 s** khi trúng đường nhanh (≈ thời gian chờ ngắt câu 0,42 s + 0,1 s) so với 2,1–3,6 s qua LLM. Câu "bạn nói lại giúp mình" cũng lấy từ cache: 1,15 → 0,53 s.
* Lần chạy đầu sau khi flash: luồng nền tổng hợp ~66 câu và ghi cache nên lượt đầu có thể chậm (đo được 10,7 s); các lần sau đọc cache.
* Hạn chế: STT sai một từ trong lệnh là rơi về LLM; chưa thử bằng giọng người thật.

## Điện thoại (Galaxy Z Fold7, Snapdragon 8 Elite): kết quả tối ưu đo ngày 27/10
* **NPU Hexagon chạy LLM** (llama.cpp, backend Hexagon): 0,8B Q4_0 nạp prompt 2.012 / sinh 63 token/s (Pi 5: 126 / 18); 2B Q4_0 1.409 / 33. Sinh token nhanh nhất ở GPU Adreno (0,8B: 60 token/s trong ứng dụng).
* **Tra cứu Wikipedia offline** cổng sang Kotlin (SQLite FTS5, bản `requery` vì SQLite hệ thống không có FTS5): 96 ms p50, prompt 25 → 107 token, câu trả lời thật chỉ chậm thêm ≈ 0,06 s. Trên Pi cùng tính năng chậm thêm 1,4–2,8 s: NPU nạp prompt nhanh gấp ≈ 11 lần Pi nên điện thoại "trả tiền" RAG gần như không đáng kể.
* **Cắt câu đầu sau 3 từ + 4 luồng TTS**: câu trả lời thật 2,03 → 1,53 s (p50, 2B, NPU, có RAG).
* **Xác nhận tức thì**: tiếng đầu 0,54 s (độ trễ cảm nhận), không đổi câu trả lời thật.
* **Lượng tử 2B làm từ F16 có imatrix**: MCQ Global-MMLU-vi (n=400) Q4_0 mới 0,4475, Q4_0 cũ (qua Q8_0) 0,450, Q4_K_M 0,445, Q8_0 **0,4825** — imatrix không cải thiện đo được; Q8_0 hơn ≈ 3,5 điểm (≈ 1,4 sai số chuẩn: chưa có ý nghĩa thống kê) nhưng chậm hơn (18 so với 26 token/s, câu trả lời thật 1,81 so với 1,53 s). Mặc định giữ Q4_0; Q8_0 có sẵn trong danh sách model của ứng dụng.
* Nhận giọng Zipformer trên Android: WER 0,257 (laptop 0,250, cùng 12 câu).
* Chạy liên tục 7,5 phút (62 lượt): NPU tối đa 65 °C, tốc độ không giảm.
* Đo công suất khi rút sạc: xem `results/phone/` (nếu đã có `power_*`).
