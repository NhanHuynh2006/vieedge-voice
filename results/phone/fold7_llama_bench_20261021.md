# Galaxy Z Fold7 (SM-F966B, Snapdragon 8 Elite SM8750, Hexagon v79, 11 GB RAM, Android 16) — 2026-10-21
llama.cpp 7fe450e19 (cùng commit với Pi), build `arm64-android-snapdragon-release` (CPU + OpenCL Adreno + Hexagon NPU), model Qwen3.5-0.8B LoRA **Q4_0** (cùng file với Pi), llama-bench -p 128 -n 64 -r 2, 6 luồng CPU.
| Thiết bị | nạp prompt pp128 (token/s) | sinh tg64 (token/s) |
|---|---|---|
| Pi 5 CPU (3 luồng, Pi OS) | 125,7 | 18,1 |
| Fold7 CPU (6 luồng) | 634,9 | 90,7 |
| Fold7 GPU Adreno (OpenCL) | 1 008,9 | 70,0 |
| Fold7 NPU Hexagon (HTP0) | **2 011,7** | 63,2 |
Nhận xét: NPU nhanh nhất khi nạp prompt (16 lần Pi, hợp cho RAG/prompt dài); sinh token thì CPU nhanh nhất (5 lần Pi). Nhiệt độ/pin/công suất chưa đo.
