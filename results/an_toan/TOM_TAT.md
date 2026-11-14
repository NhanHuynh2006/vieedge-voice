# Kịch bản an toàn khi mất sóng: thẻ sơ cứu và ứng phó thiên tai đã kiểm duyệt (04/11/2026)

## Bài toán
Bão lũ, sạt lở thường làm mất sóng và mất điện, đúng lúc người dân cần hỏi cách sơ cứu hoặc cách thoát hiểm. Trợ lý offline
trả lời được, nhưng mô hình nhỏ bịa 12% (2 tỉ tham số) đến 52% (0,8 tỉ, câu qua nhận dạng giọng nói) số câu trả lời, nên không
được để mô hình tự viết lời khuyên y tế. Giải pháp: câu hỏi khẩn cấp được trả lời bằng thẻ viết sẵn có nguồn; câu khẩn cấp
không có thẻ được trả lời cố định "chưa có hướng dẫn đã kiểm duyệt, gọi 115 hoặc 112"; câu khác đi đường cũ.

## Dữ liệu
* `data/an_toan/the_an_toan.json`: 42 thẻ (24 sơ cứu, 10 thiên tai, 8 sinh tồn), trung bình 75 từ (khoảng 25 s đọc).
  Mỗi thẻ ghi nguồn; nội dung viết lại bằng lời của nhóm, không chép nguyên văn; câu nào không có trong nguồn đã bị xoá
  (ví dụ: "dùng hai ngón tay" cho trẻ sơ sinh sửa theo nguồn thành "gốc một bàn tay").
* `data/an_toan/nguon.json`: 42 nguồn: 6 văn bản của cơ quan nhà nước Việt Nam (Cục Quản lý đê điều và PCTT, Bộ Y tế,
  Quyết định 2024/QĐ-TTg về số 112), 18 tài liệu chính phủ Hoa Kỳ thuộc phạm vi công cộng (Ready.gov bản tiếng Việt, CDC,
  NWS), 18 nguồn trích dẫn và viết lại (MedlinePlus, WHO, Hội Chữ Thập Đỏ Úc bản tiếng Việt, Vinmec).
* Lỗi phát hiện trong nguồn: bản dịch tiếng Việt Ready.gov ghi "40 độ C" cho ngưỡng bỏ thức ăn (bản gốc là 40 độ F, tức
  khoảng 4 độ C); thẻ không dùng con số này.
* Chưa có người có chuyên môn y tế duyệt các thẻ. Đây là việc phải làm trước khi đưa cho người dùng thật.

## Cách khớp (src/vieedge/safety, bản Kotlin android/.../SafetyCards.kt, cùng một tệp luật)
Khớp theo cụm từ có dấu (bỏ dấu thì "bất tỉnh" trùng "bật tính", "đuối nước" trùng "dưới nước"), cụm 3 âm tiết trở lên được
khớp cả khi không dấu; khớp tổ hợp từ ("rắn" + "cắn"); ưu tiên thẻ cụ thể; từ ngữ cảnh và từ chặn; câu hỏi kiến thức ("lũ quét
hình thành thế nào") để LLM trả lời trừ khi hỏi cách xử lý. 0,1 ms mỗi câu trên laptop. Bản Kotlin cho kết quả giống hệt bản
Python trên 918 câu (`SafetyCardsParityTest`).

## Kết quả (bench/eval_safety.py)
| Tập | Câu khẩn cấp có thẻ: đúng thẻ | sót / sai thẻ | Khẩn cấp không thẻ: trả "gọi 115" | Câu thường: kích hoạt nhầm |
|---|---|---|---|---|
| Phát triển (dùng để chỉnh luật) | 126/126 | 0 / 0 | 20/20 | 0/25 câu khó, 0/345 câu hỏi chung |
| Độc lập 1, luật cụm từ ban đầu | 50/84 (60%) | 29 / 5 | 12/20 | 1/30 |
| Độc lập 2, viết sau khi khoá luật (sha1 trong `khoa_truoc_doc_lap_v2.sha1`) | **79/84 (94%)** | 5 / 0 | 16/20 | 7/30 câu khó cố ý gài bẫy |
| Độc lập 2 qua giọng tổng hợp và Zipformer (WER 0,354) | 40/84 (48%) | 41 / 3 | 9/20 | 3/30 |

Ghi chú trung thực:
* Tập phát triển và tập độc lập 1 đã được dùng khi chỉnh luật, nên 100% và 98% (sau chỉnh) không phải số đo độc lập.
  Số độc lập là dòng "Độc lập 2": chạy một lần trên luật đã khoá, câu hỏi viết sau khi khoá.
* Các câu thử do nhóm viết (có hỗ trợ của AI), chưa phải câu của người dùng thật.
* Qua giọng tổng hợp chất lượng thấp, nhận dạng giọng nói sai 35% số từ nên chỉ còn 48% đúng thẻ: lỗi nằm ở khâu nghe, không ở
  khâu khớp. Với giọng người thật (VIVOS, WER 0,041) dự kiến tốt hơn nhiều nhưng chưa đo.
* Sau khi đo tập độc lập 2, nhóm sửa thêm các lỗi thấy được (chỉ để dùng thật, không tính là số độc lập): 83/84 đúng thẻ.

## Trên điện thoại (Galaxy Z Fold7, 05/11/2026)
* Bản Kotlin trên máy cho kết quả giống hệt bản Python trên 918 câu (`safety_eval` trong ứng dụng), 1,4 ms mỗi câu gồm đọc ghi tệp.
* 16 câu khẩn cấp đọc bằng giọng tổng hợp (chọn trong số câu mà Zipformer nghe đúng), chạy 2 lần, bật chế độ máy bay
  (Wi-Fi của máy vẫn bật; ứng dụng không dùng mạng): 32/32 lượt trả lời bằng đúng thẻ. Tiếng đầu tính từ lúc nói xong, gồm
  0,4 s chờ ngắt câu: lần đầu p50 0,83 s (p95 1,11 s) vì phải tổng hợp giọng; lần hai p50 0,50 s (p95 0,52 s) vì âm thanh đã
  nằm trong bộ nhớ đệm. Dữ liệu: `results/phone/raw/an_toan_may_bay_20261105.jsonl`.

## Kết quả âm
LLM làm bộ chọn thẻ (Qwen3.5 2 tỉ LoRA, đầu ra bị ràng buộc bằng ngữ pháp vào danh sách mã thẻ): chỉ 2/126 câu đúng thẻ trên tập
phát triển và kích hoạt nhầm 140/345 câu hỏi chung, nên không dùng (`router_dev.json`).

## Còn phải làm
* Đo thời lượng pin khi chạy bằng pin ở chế độ máy bay (cần rút cáp).
* Người có chuyên môn y tế duyệt 42 thẻ; thu câu hỏi của người dùng thật.
* Pi chưa được cập nhật (đang tắt); mã và tệp đã có trong `scripts/stage_models.sh` và recipe Yocto.

## Mở rộng 05/11/2026: 60 thẻ, ASR thiên vị từ khẩn cấp, bộ phân loại thứ hai

### Dữ liệu thêm
* 18 thẻ mới (tổng 60): hạ đường huyết, chảy máu cam, bong gân và trật khớp, mắt (dị vật, hóa chất, chấn thương), đứt lìa chi,
  ngộ độc thức ăn, ngộ độc rượu methanol, nấm độc, bọ cạp đốt, sốc do mất máu, sốt cao, lên cơn hen, hồi sức tim phổi cho trẻ
  từ 1 tuổi, hồi sức cho trẻ dưới 1 tuổi, động đất, sóng thần, lái xe hoặc lội qua nước lũ, bỏng hóa chất.
* 20 nguồn mới (tổng 62): 17 trang MedlinePlus, tờ hướng dẫn tiếng Việt về động đất của Cơ quan Quản lý khẩn cấp New Zealand,
  2 trang của National Weather Service. Mỗi câu trong thẻ đều có trong nguồn; câu nào không tìm thấy trong nguồn thì bỏ
  (ví dụ "không ngửa đầu ra sau" khi chảy máu cam: nguồn chỉ nói cúi người về trước). Thẻ dài tối đa 110 từ.
* Không làm thẻ sứa đốt: các nguồn mâu thuẫn nhau về giấm và nước nóng. Các trang Ready.gov tiếng Việt về động đất, sóng thần
  và cháy rừng trả lỗi 403 khi tải nên không dùng.
* Luật chuyển thẻ mới: câu có "sơ sinh", "N tháng" thì chuyển sang thẻ hồi sức cho trẻ dưới 1 tuổi; câu có "trẻ em", "bé",
  "cháu bé" thì chuyển sang thẻ hồi sức cho trẻ em. Bản Python và bản Kotlin dùng chung tệp luật.
* Tập phát triển thêm 72 câu cho thẻ mới và 15 câu thường. 10 câu cũ trước đây ghi "chưa có thẻ" nay có thẻ nên được đổi nhãn.

### Tập độc lập v3 (170 câu, khoá bằng sha1 trước khi viết khoá cho thẻ mới và trước khi huấn luyện)
`data/an_toan/cau_hoi_doc_lap_v3.jsonl`, sha1 trong `khoa_truoc_doc_lap_v3.sha1`. Gồm 114 câu khẩn cấp có thẻ (72 câu cho thẻ
mới, 42 câu cho thẻ cũ), 20 câu khẩn cấp chưa có thẻ, 36 câu thường cố ý gài từ dễ nhầm. Chạy một lần trên luật đã khoá.
Hạn chế: nhóm vẫn là người viết cả câu thử lẫn luật, nên tập này độc lập về thời điểm, không độc lập về người viết.

| Đầu vào (v3) | Đúng thẻ (khoảng tin cậy 95%) | Khẩn cấp chưa có thẻ: trả lời "gọi 115" | Câu thường: kích hoạt nhầm |
|---|---|---|---|
| Gõ chữ | 111/114 = 97,4% [92,5; 99,1] | 14/20 | 5/36 |
| Giọng tổng hợp rõ (vais1000, WER 0,154), giải mã cũ | 97/114 = 85,1% | 13/20 | 2/36 |
| Giọng rõ, có từ khoá thiên vị + bộ phân loại (bản đang chạy) | **102/114 = 89,5% [82,5; 93,9]** | 13/20 | 2/36 |
| Giọng tổng hợp kém (25hours, WER 0,399), giải mã cũ | 48/114 = 42,1% | 6/20 | 2/36 |
| Giọng kém, có từ khoá thiên vị + bộ phân loại | 55/114 = 48,2% [39,3; 57,3] | 7/20 | 4/36 |

So từng câu (kiểm định McNemar chính xác): giọng rõ sửa đúng 5 câu, làm sai 0 câu (p = 0,06); giọng kém sửa đúng 7, làm sai
0 (p = 0,016). Lỗi còn lại chủ yếu ở khâu nghe: "Trẻ sơ sinh sặc sữa" bị nghe thành "thẽ sợi sặc sừng".

### Từ khoá thiên vị cho nhận dạng giọng nói (`bench/eval_hotwords.py`)
Mô hình Zipformer có giấy phép CC BY-NC-ND (không được sửa đổi) nên không huấn luyện lại. Thay vào đó dùng tính năng
hotwords của sherpa-onnx: 974 cụm từ khoá của các thẻ (viết hoa, vì token BPE viết hoa) được cộng điểm khi giải mã beam 4 đường.
Hệ số 1,0 được chọn trên tập v2 (không phải v3). Trên giọng người thật VIVOS (300 câu), WER giữ nguyên 0,057 so với 0,059,
tốn thêm khoảng 7 ms mỗi câu. Đổi lại, trên 234 câu hỏi thường đọc bằng giọng tổng hợp có 2 câu bị nghe nhầm thành câu khẩn cấp
(0 câu khi không dùng). Nhóm chấp nhận đánh đổi này vì bỏ sót một câu khẩn cấp nguy hiểm hơn đọc nhầm một thẻ sơ cứu.

### Bộ phân loại thứ hai (`bench/train_safety_clf.py`, `data/an_toan/phan_loai.json`)
Hồi quy logistic nhiều lớp (61 lớp: 60 thẻ và "không phải khẩn cấp") trên từ đơn và cặp từ, có dấu và bỏ dấu; 11.472 đặc trưng.
Dữ liệu huấn luyện: 4.292 câu gõ (tập phát triển, tập độc lập v1, câu ghép từ khoá của thẻ, 1.500 câu hỏi thường) cộng 4.292
bản nghe lại qua giọng vivos (một nửa có trộn tiếng ồn 10 dB); giọng này khác giọng của tập thử. Chỉ dùng khi luật không tìm
ra thẻ, và không dùng cho câu hỏi kiến thức. Ngưỡng 0,95 được chọn trên v2 và 345 câu hỏi thường (gõ và nghe lại) với điều
kiện không thêm câu kích hoạt nhầm nào. Thử thêm đặc trưng ký tự 3-gram: chỉ hơn 2 câu trên tập kiểm định nên không dùng.
Kết quả: đóng góp nhỏ (thêm 1 đến 2 câu đúng trên v3), nhưng không gây kích hoạt nhầm. Bản Kotlin cho kết quả giống hệt bản
Python trên 1.852 câu, cả trên laptop (`SafetyCardsParityTest`) và trên điện thoại (`safety_eval`), 1,7 ms mỗi câu.

### Trên điện thoại (Galaxy Z Fold7, 05/11/2026)
* Câu trả lời của thẻ: câu đầu của cả 60 thẻ được tổng hợp sẵn khi mở trợ lý, phần còn lại tổng hợp trong lúc câu đầu đang phát.
* 24 câu chọn ngẫu nhiên trong v3 (giọng vais1000) phát vào toàn bộ chuỗi xử lý trên máy: 20/24 đúng thẻ. Tiếng đầu tính từ lúc
  nói xong, gồm 0,4 s chờ ngắt câu: p50 0,48 s, p95 0,50 s, chậm nhất 0,67 s, ngay cả ở lần hỏi đầu tiên (trước đây lần đầu
  p50 0,83 s). 4 câu sai đều do nghe nhầm: "suyễn" thành "diễn" (máy trả lời "gọi 115"), "axit" thành "rc", "bỏng" thành
  "bằng", "máu cam" thành "máu càng" (ra thẻ chảy máu). Dữ liệu: `results/phone/raw/an_toan_v3_giong_vais_20261105.jsonl`.
  Lần chạy này không bật chế độ máy bay.
* Sửa lỗi phát hiện khi chạy: phòng ồn (người nói chuyện, nhạc) làm ngưỡng ồn tăng, khiến 14/24 câu hỏi bị bỏ qua như tiếng
  ồn. Nay ngưỡng bị giới hạn, và câu nào khớp thẻ khẩn cấp thì không bao giờ bị bỏ qua.

### Còn phải làm
* Thu giọng người thật đọc câu khẩn cấp (giọng tổng hợp kém cho 48%, giọng tổng hợp rõ cho 89,5%: giọng thật chưa đo).
* Người có chuyên môn y tế duyệt 60 thẻ.

## Mở rộng 06/11/2026: 85 thẻ, thêm tình huống quốc tế

### Thẻ thêm
* Đợt 2 (16 thẻ): sứa đốt, nhện cắn, ve bám, dị vật vào tai, nuốt pin cúc áo, vết cắt và vết đâm nhỏ, gãy hoặc rơi răng, bị dòng
  chảy kéo ra xa bờ, lốc xoáy, ra máu khi mang thai, có người muốn tự tử, trẻ bị bạo hành (Tổng đài 111), rò rỉ gas, kẹt
  thang máy, ngạt khí dưới hầm hoặc giếng, các bước đầu tiên khi gặp người bị nạn.
* Đợt quốc tế (9 thẻ): sự cố phóng xạ hoặc hạt nhân, xả súng hoặc tấn công bằng vũ khí (chạy, trốn, báo), sinh con khẩn cấp
  và sảy thai, số khẩn cấp ở nước ngoài (112 châu Âu, 911, 999, 000, 111 New Zealand), tê cóng, kẹt xe trong bão tuyết, gặp
  gấu, bão cát khi lái xe, giẫm đạp trong đám đông.
* 20 nguồn mới (tổng 82): Hội Chữ Thập Đỏ Úc (bản tiếng Việt), MedlinePlus, CDC, National Weather Service, National Park
  Service, Cảnh sát chống khủng bố Anh, St John New Zealand, Ủy ban châu Âu, Bộ Công an, Cảnh sát PCCC TP.HCM, Tổng đài 111,
  Trung tâm Chống độc Bệnh viện Bạch Mai.
* Không làm thẻ khi không tải được nguồn: núi lửa (USGS trả lỗi 403), say độ cao và khói cháy rừng (CDC trả lỗi 404), lở
  tuyết, lạc trong rừng.
* Mở rộng danh sách từ khẩn cấp dùng cho câu trả lời "gọi 115" (sinh con, vỡ ối, rết, cá nóc, bị đè, đổ nát, ngạt, ngất…),
  để câu khẩn cấp chưa có thẻ không bị chuyển sang mô hình ngôn ngữ.

### Tập độc lập v4 (94 câu) và v5 (76 câu, tình huống quốc tế), mỗi tập khoá trước khi viết khoá cho đợt thẻ tương ứng
| Tập | Gõ chữ: đúng thẻ | Giọng tổng hợp rõ (vais1000) | Giọng tổng hợp kém (25hours) | Câu thường bị kích hoạt nhầm (gõ) |
|---|---|---|---|---|
| v4, 16 thẻ đợt 2 | 64/64 | 47/64 (WER 0,217) | 28/64 (WER 0,441) | 0/20 |
| v5, 9 thẻ quốc tế | 35/36 | 30/36 (WER 0,156) | 15/36 (WER 0,415) | 0/20 |

* Câu khẩn cấp chưa có thẻ trong v4: lần chạy đầu (danh sách từ khẩn cấp cũ) chỉ 3/10 được trả lời "gọi 115", 7/10 bị chuyển
  sang mô hình ngôn ngữ. Sau khi mở rộng danh sách từ: 6/10 (số đo lại, không còn độc lập). Với v5 (chạy sau khi mở rộng):
  14/20 câu được xử lý chấp nhận được (thẻ chấp nhận được ghi trước khi chạy, tệp `cau_hoi_doc_lap_v5_chap_nhan.jsonl`),
  2 câu vẫn rơi sang mô hình ngôn ngữ ("núi lửa phun trào", "nuốt nam châm"), 1 câu ra thẻ sai rõ ("đau đầu dữ dội như sét
  đánh" ra thẻ giông sét).
* Hồi quy trên v3 (đã dùng trước đó, không độc lập): gõ 118/121, giọng rõ 107/121.
* Bộ phân loại huấn luyện lại cho 86 lớp (10.832 câu): ngưỡng 0,90 chọn trên v2 và 345 câu hỏi thường với điều kiện không thêm
  kích hoạt nhầm; đóng góp vẫn nhỏ (thêm 0 đến 5 câu đúng tuỳ tập).
* Lỗi nghe đặc trưng của đợt này: từ mượn "gas" bị nghe thành "gà", "cát", "gặp"; "pin" thành "kinh", "tin", "tiếng".
* Bản Kotlin giống hệt bản Python trên 2.474 câu, cả trên laptop (`SafetyCardsParityTest`) và trên điện thoại (`safety_eval`,
  2,1 ms mỗi câu).

### Trên điện thoại với 85 thẻ (Galaxy Z Fold7, 06/11/2026)
* 24 câu chọn ngẫu nhiên trong v4 và v5 (giọng vais1000), phát vào toàn bộ chuỗi xử lý trên máy: 20/24 đúng thẻ. 4 câu sai đều do
  nghe nhầm ("pin" thành "tinh", "tai" thành "tại", "tê cóng" thành "từ cống", "đẻ rơi" thành "đè dơi").
* Lần đo đầu, câu khẩn cấp hỏi ngay sau khi mở trợ lý mất 1,73 s vì câu đầu của 85 thẻ chưa tổng hợp xong (máy cần khoảng
  90 s cho cả 85 câu). Sửa: âm thanh câu đầu của mỗi thẻ được lưu vào bộ nhớ máy (33 MB) ở lần chạy đầu tiên, các lần mở sau
  nạp lại ngay. Đo lại khi hỏi 1 s sau lúc mở: tiếng đầu p50 0,55 s, p95 0,56 s, chậm nhất 0,71 s (câu đầu tiên), gồm 0,4 s
  chờ ngắt câu. Riêng lần mở đầu tiên sau khi cài, trong khoảng 90 s đầu câu khẩn cấp có thể chậm tới khoảng 1,7 s.
  Dữ liệu: `results/phone/raw/an_toan_v45_giong_vais_hoi_ngay_20261106.jsonl`.

## Điện thoại phổ thông TCL T506T (07/11/2026)
Xem `results/phone/tcl/TOM_TAT.md`: cùng 24 câu nói đúng thẻ 20/24 như Fold7, tiếng đầu p50 1,43 s; bộ khớp giống hệt bản Python trên 2.474 câu.
