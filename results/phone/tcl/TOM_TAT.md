# Điện thoại phổ thông TCL T506T (07/11/2026)

Máy: TCL T506T, MediaTek Helio P22 (MT6762V), 8 lõi Cortex-A53 (4 x 2,0 GHz + 4 x 1,5 GHz), 4 GB RAM (khoảng 1,6 GB trống),
GPU PowerVR GE8320, Android 13. Không có NPU dùng được, chỉ chạy LLM trên CPU.

## Bản dựng riêng
Bản llama.cpp của Fold7 dựng với `-march=armv8.7a+fp16+dotprod+i8mm`; trên Cortex-A53 (ARMv8.0) ứng dụng dừng ngay khi nạp
`libllama-common.so` với lỗi SIGILL. Ứng dụng có thêm bản dựng `generic` (product flavor):
```
cmake -S third_party/llama.cpp -B build-android-generic -G Ninja -DCMAKE_TOOLCHAIN_FILE=$NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-26 -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON -DGGML_NATIVE=OFF \
  -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_OPENMP=OFF -DGGML_LLAMAFILE=OFF -DGGML_OPENCL=OFF -DGGML_HEXAGON=OFF -DLLAMA_OPENSSL=OFF \
  -DLLAMA_CURL=OFF -DCMAKE_C_FLAGS="-march=armv8-a -D_GNU_SOURCE" -DCMAKE_CXX_FLAGS="-march=armv8-a -D_GNU_SOURCE"
cmake --build build-android-generic --target llama-server-impl -j 4
```
(chạy trong ảnh `ghcr.io/snapdragon-toolchain/arm64-android:v0.7`). APK: `dist/VieEdgeVoice-generic.apk`.

## Kết quả (tệp gốc trong thư mục này; `docs/submission/make_tcl.py` đọc chúng để sinh số cho báo cáo)
| Phép đo | TCL T506T | Fold7 (để so) |
|---|---|---|
| Bộ khớp Kotlin giống Python, 2.474 câu | 2.474/2.474, 30 ms mỗi câu | 2.474/2.474, 2,1 ms |
| 24 câu nói, thẻ mới (v4, v5): đúng thẻ | 20/24 | 20/24 |
| 24 câu nói, thẻ đợt 1 (v3): đúng thẻ | 20/24 | 20/24 |
| Thẻ: tiếng đầu p50 / p95 / chậm nhất | 1,43 / 1,67 / 1,75 s | 0,55 / 0,56 / 0,71 s |
| Trong đó chờ ngắt câu + nhận dạng, p50 | 1,33 s | khoảng 0,48 s |
| Nhận dạng 4 luồng (thay 3) | 1,53 s, 20/24 | |
| 4 luồng, không thiên vị từ khoá | 1,33 s, nhưng 19/24 | |
| Nạp LLM 0,8 tỉ / 2 tỉ | 68 s / 100 s | 6 đến 8 s |
| Sinh token 0,8 tỉ / 2 tỉ | 3,1 / 1,8 token/s | 27 / 26 token/s |
| Câu trả lời thật, 0,8 tỉ, tắt tra cứu, p50 (8 câu) | 12,6 s | 1,19 s |
| Câu trả lời thật, 0,8 tỉ, bật tra cứu | 31,8 s (token đầu 22,9 s, 206 token prompt) | |
| Câu trả lời thật, 0,8 tỉ, 8 luồng LLM | 72,5 s (1,2 token/s: tranh CPU với TTS, STT) | |
| Câu trả lời thật, 2 tỉ, tắt tra cứu | 22,5 s | 1,53 s (có tra cứu) |
| Bộ nhớ ứng dụng lúc cao nhất (0,8 tỉ / 2 tỉ) | 1,3 / 2,0 GB | |
| Nhiệt độ pin sau bài thử | 35,5 đến 36,5 °C | |

* Hai máy sai đúng các câu giống nhau (lỗi nghe như "pin" thành "tinh", "suyễn" thành "diễn"), nên độ chính xác thẻ không phụ
  thuộc máy; máy yếu chỉ chậm hơn.
* Khâu chậm nhất của hỏi đáp tự do là nạp prompt: khoảng 9 token prompt mỗi giây. Vì vậy bản `generic` mặc định tắt tra cứu và
  không gửi lại các lượt trước. Câu khẩn cấp không qua LLM nên vẫn có tiếng sau khoảng 1,4 s.
* Lần chạy LLM 2 tỉ đầu tiên dừng do lỗi của móc thử (đoạn âm đầu bị lọc như tiếng ồn, không có lượt nào được ghi); đã sửa móc
  thử và chạy lại.

## Vị trí và bản đồ
* Trong nhà không bắt được GPS; máy dùng vị trí gần đúng từ mạng Wi-Fi (sai số khoảng 100 m) và ghi rõ "chưa bắt được GPS".
* Bản đồ vùng 25 x 25 km: 224 mảnh, 30,8 MB, khoảng 45 s qua Wi-Fi. Tắt Wi-Fi, mở lại ứng dụng và kéo bản đồ sang khu vực
  chưa từng xem: bản đồ vẫn hiện từ dữ liệu đã tải. (Không ghi tọa độ thật vào tài liệu.)
* Hỏi "tôi đang ở đâu": trợ lý đọc vĩ độ, kinh độ, sai số; lần đầu sau khi nạp mô hình 2,5 s, lần sau 0,13 s.

## Hai máy, cùng đầu vào (Fold7 đo lại 07/11/2026 bằng `results/phone/fold7/run_all.sh`)
Bảng trên ghi số Fold7 cũ để so nhanh. Bảng này là bản đúng để so: cùng tệp mô hình, cùng 24 câu khẩn cấp, 8 câu hỏi, cùng móc
`stagebench`; LLM đo bằng `llama-bench` CPU 4 luồng. Số sinh bởi `docs/submission/make_hai_may.py` → `so_lieu_hai_may.tex`,
hình `hai_may_latency.pdf`, `stages_v2.pdf`, `platform_v2.pdf`.

| Khâu | Fold7 | TCL T506T |
|---|---|---|
| STT một câu (ms, RTF) | 65 (0,022) | 889 (0,305) |
| TTS một câu (ms, RTF) | 270 (0,087) | 2 274 (0,722) |
| Khớp thẻ một câu (ms) | 3,0 | 27,1 |
| LLM 0,8 tỉ nạp / sinh (token/s) | 454 / 79,5 | 10,8 / 4,6 |
| LLM 2 tỉ nạp / sinh (token/s) | 196 / 28,2 | 4,3 / 2,2 |
| Nạp mô hình 0,8 tỉ (s) | 5 | 68 |
| Hỏi đáp 0,8 tỉ CPU: "Dạ." / câu thật (s) | 0,59 / 1,4 | 1,99 / 12,6 |
| Thẻ: đúng / tiếng đầu p50 (s) | 20/24 / 0,48 | 20/24 / 1,43 |

Ảnh chụp ứng dụng chạy trên hai máy (minh chứng phần cứng): `docs/submission/figures/anh_may.jpg` (tọa độ che, bản đồ làm mờ
bằng `figures/anh_may/redact.py`; ảnh gốc chưa che ở `figures/anh_may/raw`, không đưa vào tài liệu).
