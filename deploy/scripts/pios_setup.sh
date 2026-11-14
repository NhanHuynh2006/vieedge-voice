#!/usr/bin/env bash
# Raspberry Pi OS (64-bit, Bookworm/Trixie Lite) setup for configurations O0/O1, and the fallback
# path of PLAN §7.3 (Hailo-8L on Pi OS + self-built RT kernel if Yocto+Hailo is not stable in time).
# Run ON THE PI as the normal user (uses sudo):
#   ./pios_setup.sh            # O0: stock OS + hailo-all + VieEdge
#   ./pios_setup.sh --o1       # O1: + performance governor, unneeded services off
#   ./pios_setup.sh --rt-kernel  # build & install a PREEMPT_RT kernel (rpi-6.12.y) for O3/O4-on-PiOS
set -euo pipefail
O1=0; RT=0
for a in "$@"; do case $a in --o1) O1=1;; --rt-kernel) RT=1;; esac; done
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
HOME_V=$HOME/vieedge

echo "== packages"
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev python3-numpy python3-yaml python3-psutil python3-alsaaudio python3-libgpiod \
  libespeak-ng1 espeak-ng-data alsa-utils rt-tests stress-ng git cmake build-essential libgomp1 rsync
# Hailo runtime + driver + firmware (official Raspberry Pi packages, versions matched to each other)
sudo apt-get install -y hailo-all || echo "!! hailo-all not available: see https://www.raspberrypi.com/documentation/computers/ai.html"

echo "== python env"
python3 -m venv --system-site-packages $HOME_V/venv
$HOME_V/venv/bin/pip install --upgrade pip
$HOME_V/venv/bin/pip install ctranslate2 onnxruntime fastapi "uvicorn[standard]" soundfile
$HOME_V/venv/bin/pip install -e "$REPO" --no-deps

echo "== llama.cpp (native build: GGML_NATIVE picks up dotprod/fp16 on Cortex-A76)"
if [[ ! -d $HOME/llama.cpp ]]; then
  git clone https://github.com/ggml-org/llama.cpp $HOME/llama.cpp
  git -C $HOME/llama.cpp checkout 7fe450e19305b828c199d602c23a8337aaa1f03b
fi
cmake -S $HOME/llama.cpp -B $HOME/llama.cpp/build -DCMAKE_BUILD_TYPE=Release -DLLAMA_OPENSSL=OFF -DGGML_LTO=ON
cmake --build $HOME/llama.cpp/build -j4 --target llama-server llama-bench llama-cli llama-speculative-simple

echo "== config + service"
sudo mkdir -p /etc/vieedge
sudo cp "$REPO/deploy/config/vieedge-pi.yaml" /etc/vieedge/config.yaml
sudo sed -i "s#/opt/vieedge/models#$HOME_V/models#; s#/opt/vieedge/results#$HOME_V/results#; s#/usr/bin/llama-server#$HOME/llama.cpp/build/bin/llama-server#" /etc/vieedge/config.yaml
sudo install -m 0755 "$REPO"/deploy/scripts/vieedge-tune "$REPO"/deploy/scripts/vieedge-osmode /usr/local/bin/
sudo ln -sf /usr/local/bin/vieedge-tune /usr/bin/vieedge-tune
sed "s#/usr/bin/python3 -m vieedge#$HOME_V/venv/bin/python -m vieedge#; s#^Type=simple#Type=simple\nUser=root#" \
  "$REPO/deploy/systemd/vieedge.service" | sudo tee /etc/systemd/system/vieedge.service > /dev/null
sudo cp "$REPO/deploy/systemd/vieedge-tuning.service" /etc/systemd/system/
if [[ $O1 == 1 ]]; then
  echo "VIEEDGE_OS_CFG=O1" | sudo tee /etc/vieedge/env
  for s in bluetooth cups avahi-daemon ModemManager triggerhappy packagekit rpi-connect; do sudo systemctl disable --now $s 2>/dev/null || true; done
else
  echo "VIEEDGE_OS_CFG=O0" | sudo tee /etc/vieedge/env
fi
sudo systemctl daemon-reload
sudo systemctl enable vieedge-tuning vieedge
mkdir -p $HOME_V/models $HOME_V/results
grep -q pciex1_gen /boot/firmware/config.txt || echo "dtparam=pciex1_gen=3" | sudo tee -a /boot/firmware/config.txt

if [[ $RT == 1 ]]; then
  echo "== PREEMPT_RT kernel for Pi OS (rpi-6.12.y, bcm2712, ~1 h on the Pi)"
  sudo apt-get install -y bc bison flex libssl-dev make libncurses-dev
  [[ -d $HOME/linux ]] || git clone --depth=1 --branch rpi-6.12.y https://github.com/raspberrypi/linux $HOME/linux
  cd $HOME/linux
  make bcm2712_defconfig
  ./scripts/config -e EXPERT -e PREEMPT_RT -d PREEMPT -d PREEMPT_VOLUNTARY -e NO_HZ_FULL -e RCU_NOCB_CPU \
    -e CPU_FREQ_DEFAULT_GOV_PERFORMANCE -e TIMERLAT_TRACER -e OSNOISE_TRACER --set-str LOCALVERSION "-v8-16k-rt"
  make olddefconfig
  make -j4 Image.gz modules dtbs
  sudo make modules_install
  sudo cp arch/arm64/boot/Image.gz /boot/firmware/kernel_2712_rt.img
  echo "kernel=kernel_2712_rt.img" | sudo tee -a /boot/firmware/config.txt
  echo "!! re-install the Hailo PCIe driver for the new kernel: sudo apt-get install --reinstall hailo-dkms (or build hailort-drivers)"
fi
echo "== done. Copy models with scripts/deploy_models.sh <pi> $HOME_V from the laptop, then: sudo systemctl start vieedge"
