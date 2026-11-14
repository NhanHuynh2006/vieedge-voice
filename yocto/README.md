# Yocto image cho VieEdge-Voice (PLAN §7)

* Poky **scarthgap 5.0 LTS** + meta-openembedded (oe, python, multimedia, networking) + **meta-raspberrypi** (`MACHINE = raspberrypi5`)
  + **meta-hailo nhánh `hailo8-scarthgap`** (HailoRT / PCIe driver / firmware **4.24.0** cho Hailo-8/8L; nhánh `scarthgap` thường là HailoRT 5.x chỉ cho Hailo-10H/15)
  + layer riêng `meta-vieedge`.
* Kernel `linux-raspberrypi 6.12` (`PREFERRED_VERSION_linux-raspberrypi = "6.12.%"`). PREEMPT_RT đã vào mainline từ 6.12 (arm64) nên không cần patch.
* `DEFAULTTUNE = "cortexa76"` → mọi recipe biên dịch với `-mcpu=cortex-a76` (ARMv8.2-A, dotprod, fp16).

## Build

```bash
./yocto/build.sh            # O2: kernel thường            -> yocto/build/
./yocto/build.sh rt         # O3/O4: PREEMPT_RT + isolcpus  -> yocto/build-rt/
./yocto/build.sh rt shell   # shell bitbake để debug
```
`build.sh` chạy trong `kas-container` (image Debian của kas, nên host Ubuntu 26.04 không cần cài gì thêm ngoài Docker + kas),
dùng chung `~/yocto-cache/{downloads,sstate}` cho cả hai bản (bản RT chỉ build lại kernel + module),
giới hạn container 7 GB RAM (`YOCTO_MEM=…` để đổi) và `BB_NUMBER_THREADS=4` vì laptop 14 GB RAM.
Lần đầu ~4–6 giờ; các lần sau vài phút nhờ sstate.

Ảnh: `images/{o2,rt}/vieedge-image-{o2,rt}.wic.bz2` (+ `.wic.bmap`).

## Flash

```bash
sudo bmaptool copy vieedge-image-raspberrypi5.rootfs.wic.bz2 /dev/sdX       # nhanh
# hoặc
bzcat vieedge-image-raspberrypi5.rootfs.wic.bz2 | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress
```
Cắm Ethernet (DHCP) hoặc kết nối Wi-Fi `VieEdge-Voice` / `vieedge2026` (Pi phát hotspot, IP 192.168.50.1).
SSH `root@<ip>`, mật khẩu `vieedge`. Rootfs có thêm 6 GB trống cho mô hình: từ laptop `./scripts/deploy_models.sh <ip>`.
Hoặc nướng sẵn mô hình vào ảnh: `VIEEDGE_BUNDLE_MODELS = "1"` trong `kas.yml` (mục `30-vieedge`) sau khi chạy `scripts/stage_models.sh`.

## Nội dung ảnh (`packagegroup-vieedge`)

| Nhóm | Gói |
|---|---|
| Ứng dụng | `vieedge-app` (Python package + `/etc/vieedge/config.yaml` + `vieedge.service`, `vieedge-tuning.service`, `vieedge-tune`, `vieedge-osmode`, `/opt/vieedge/bench`) |
| NPU | `hailo-pci` (kernel module), `hailo-firmware`, `libhailort`, `hailortcli`, `pyhailort` (4.24.0) |
| LLM | `llama-cpp` (armv8.2-a+dotprod+fp16, LTO → `/usr/bin/llama-server`…), `llama-cpp-generic` (armv8-a, `/opt/llama-generic`, cho M0/M5) |
| STT | `ctranslate2` + `python3-ctranslate2` (Ruy int8 + OpenBLAS CORTEXA76, LTO), `openblas` |
| TTS/VAD | `python3-onnxruntime` (wheel aarch64 chính thức, MLAS tự chọn nhân dotprod/fp16), `espeak-ng` |
| Web | `python3-fastapi`, `python3-starlette`, `python3-uvicorn`, `python3-websockets` |
| Đo đạc | `rt-tests` (cyclictest), `rtla` (build từ chính cây kernel), `stress-ng`, `htop`, `raspi-utils` (vcgencmd), `i2c-tools` |
| Mạng | `vieedge-hotspot` (hostapd + dnsmasq + systemd-networkd), `openssh` |

## Kernel

* `vieedge-common.cfg`: governor mặc định performance, `NO_HZ_FULL`, `RCU_NOCB_CPU`, cpusets, USB audio.
* `vieedge-tracing.cfg` (`VIEEDGE_TRACING = "1"`, bản đo latency): timerlat/osnoise/hwlat tracer cho `rtla`.
  `VIEEDGE_TRACING = "0"` → `vieedge-notrace.cfg` cho bản đo hiệu năng thuần.
* `preempt-rt.cfg` (`VIEEDGE_RT = "1"`, chỉ trong `kas-rt.yml`): `CONFIG_PREEMPT_RT=y`, HZ=1000, tắt debug làm hỏng latency.
* Cmdline bản RT: `isolcpus=3 nohz_full=3 rcu_nocbs=3 irqaffinity=0-2`; `vieedge-tune` ghim IRQ USB sang lõi 3,
  ứng dụng ghim LLM/decoder/TTS vào lõi 0–2 và luồng audio SCHED_FIFO 80 ở lõi 3. `vieedge-osmode o3|o4` để chuyển O3↔O4.

## Hailo trên Yocto — cổng 5 ngày

Phiên bản driver = firmware = HailoRT = 4.24.0 (cùng một commit meta-hailo). HEF phải được biên dịch bằng DFC tương thích
HailoRT 4.24 (xem `hailo_compile/wheels/README.md`). Nếu sau 5 ngày làm việc Hailo-8L chưa chạy ổn định trên Yocto,
dùng Raspberry Pi OS + `pios_setup.sh --rt-kernel` cho các cấu hình có NPU (PLAN §7.3) và ghi rõ trong báo cáo.
