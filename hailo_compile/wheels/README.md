# Hailo wheels (not redistributable — download them yourself) 🧑

1. Log in at https://hailo.ai/developer-zone/ → Software Downloads.
2. Filter: *Hailo-8L*, *Linux*, *x86*, *Python 3.10*. Download
   - **Dataflow Compiler v3.x** (`hailo_dataflow_compiler-3.xx.x-py3-none-linux_x86_64.whl`) — DFC 3.x is the line for Hailo-8/8L (5.x is Hailo-10H only).
   - optional: **HailoRT** Python wheel `hailort-4.xx.x-cp310-cp310-linux_x86_64.whl` (only to test HEFs on a PC with a Hailo card).
3. Put them in this folder and run `docker build -t vieedge-dfc hailo_compile`.

**Version matching (PLAN §7.3):** the HEF must be compiled with a DFC that is compatible with the
HailoRT on the Pi. The Yocto image ships HailoRT/driver/firmware **4.24.0** (meta-hailo `hailo8-scarthgap`).
Raspberry Pi OS ships its own `hailo-all` version (check `hailortcli fw-control identify`).
Pick the DFC release that Hailo's compatibility table pairs with that HailoRT (Developer Zone →
"Hailo Software Suite" release notes). HEFs from an *older* DFC usually run on newer HailoRT 4.x, not vice versa.
