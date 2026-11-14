SUMMARY = "Everything VieEdge-Voice needs on the device"
LICENSE = "MIT"
PACKAGE_ARCH = "${MACHINE_ARCH}"
inherit packagegroup

RDEPENDS:${PN} = " \
    vieedge-app \
    vieedge-hotspot \
    llama-cpp \
    llama-cpp-generic \
    python3-ctranslate2 \
    python3-onnxruntime \
    python3-sherpa-onnx \
    espeak-ng \
    hailo-pci \
    hailo-firmware \
    libhailort \
    hailortcli \
    pyhailort \
    kernel-modules \
    alsa-utils \
    alsa-lib \
    rt-tests \
    rtla \
    stress-ng \
    htop \
    procps \
    util-linux \
    bash \
    coreutils \
    tzdata \
    iw \
    wpa-supplicant \
    linux-firmware-rpidistro-bcm43455 \
    i2c-tools \
    libgpiod-tools \
    rsync \
    raspi-utils \
"
