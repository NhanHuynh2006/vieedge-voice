# VieEdge Voice cho Android

Hai chế độ trong một ứng dụng: **Kết nối Pi** (điện thoại là micro và loa của Pi, qua `ws://<ip>:8000`) và **Chạy trên máy** (STT, LLM, TTS chạy ngay trên điện thoại; LLM chạy trên NPU Hexagon, GPU Adreno hoặc CPU).

## Build
1. JDK 17, Android SDK (platform 34, build-tools 34.0.0), Gradle 8.9. `local.properties`: `sdk.dir=<đường dẫn SDK>`.
2. llama.cpp cho Snapdragon: `docs/backend/snapdragon` trong `third_party/llama.cpp` (Docker `ghcr.io/snapdragon-toolchain/arm64-android`), kết quả ở `pkg-android/llama.cpp`.
3. Chép thư viện vào `app/src/main/jniLibs/arm64-v8a` (libggml*, libllama*, libmtmd, libggml-htp-v79) và build lớp JNI: `native/build.sh` (chạy llama-server ngay trong tiến trình ứng dụng).
4. sherpa-onnx: `libsherpa-onnx-jni.so`, `libonnxruntime.so` (bản phát hành Android v1.13.8) và mã Kotlin API đã nằm trong `app/src/main/java/com/k2fsa/sherpa/onnx`.
5. Hai bản dựng (product flavor):
   * `snapdragon`: llama.cpp ARMv8.7 có NPU Hexagon và GPU Adreno (Galaxy Z Fold7). Thư viện ở `app/src/snapdragon/jniLibs`.
   * `generic`: llama.cpp ARMv8.0 chỉ dùng CPU, cho mọi điện thoại arm64 khác (đã thử TCL T506T, MediaTek Helio P22, Cortex-A53;
     bản snapdragon dừng ở lỗi SIGILL trên máy này). Thư viện ở `app/src/generic/jniLibs`, dựng bằng
     `cmake -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_OPENCL=OFF -DGGML_HEXAGON=OFF ...` (xem lịch sử lệnh trong `results/phone/tcl/TOM_TAT.md`).
     Bản này mặc định tắt tra cứu và không gửi lại các lượt trước, vì CPU yếu nạp prompt chỉ khoảng 9 token/s.
   `JAVA_HOME=<jdk17> gradle assembleSnapdragonDebug assembleGenericDebug` → `app/build/outputs/apk/<flavor>/debug/` (bản dựng sẵn:
   `../dist/VieEdgeVoice-snapdragon.apk`, `../dist/VieEdgeVoice-generic.apk`).

## Model trên điện thoại
```
adb push <thư mục models> /data/local/tmp/vm && adb shell chmod -R a+rX /data/local/tmp/vm
adb shell run-as vn.vieedge.voice sh -c 'mkdir -p files && cp -r /data/local/tmp/vm files/models'
```
Cấu trúc: `llm/*.gguf` (Q4_0 cho NPU), `stt/zipformer-vi/`, `vad/silero_vad.onnx`, `tts/vits-piper-vi_VN-vais1000-medium/` (gói của
sherpa-onnx: `github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-vi_VN-vais1000-medium.tar.bz2`), tuỳ chọn `rag/wiki_vi.sqlite`.
Máy có dưới 6 GB RAM mặc định dùng mô hình 0,8 tỉ.

## Vị trí và bản đồ ngoại tuyến
Nút định vị trên thanh trên cùng: trạng thái GPS (số vệ tinh, sai số), tọa độ để đọc cho 115, chép, nhắn tin vị trí, điểm đánh dấu
(khoảng cách và hướng quay lại), và tải bản đồ vùng 10, 25 hoặc 50 km khi còn mạng (MapLibre, dữ liệu OpenStreetMap qua OpenFreeMap;
tối đa 3.000 mảnh, 50 MB mỗi lần, 4 kết nối song song, theo điều khoản của OpenFreeMap). Máy chủ tile.openstreetmap.org cấm tải trước
nên không dùng.

## Thử bằng adb (không cần nói)
`adb shell am start -n vn.vieedge.voice/.MainActivity --es model qwen3.5-0.8b-vi-voice-Q4_0.gguf --es device HTP0 --es wavs <wav1>,<wav2>` rồi xem `adb logcat -s VieEdge` và `files/turns.jsonl`.
