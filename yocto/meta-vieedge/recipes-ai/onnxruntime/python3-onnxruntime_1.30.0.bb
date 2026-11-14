SUMMARY = "ONNX Runtime (Python) for Piper VITS TTS and Silero VAD"
DESCRIPTION = "Installs the official manylinux aarch64 wheel. Its MLAS kernels dispatch at runtime \
to ARMv8.2 dotprod/fp16 paths on Cortex-A76, which is what a from-source -mcpu=cortex-a76 build \
would give, without cross-compiling protobuf/abseil/onnx inside bitbake."
HOMEPAGE = "https://onnxruntime.ai"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://onnxruntime/LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d"

PYV_TAG = "cp312"
SRC_URI = "https://files.pythonhosted.org/packages/16/bd/cbc5b8f91963689fdd622f463508c01d0aa95d3f944747b1e0b1eb2160b8/onnxruntime-${PV}-${PYV_TAG}-${PYV_TAG}-manylinux_2_28_aarch64.whl;downloadfilename=onnxruntime-${PV}-${PYV_TAG}-aarch64.zip;subdir=wheel"
SRC_URI[sha256sum] = "6c32a000d5139a38ba9349030b0032e3331acb559d596b22738d9d2b343a2b83"
S = "${WORKDIR}/wheel"

inherit python3-dir

COMPATIBLE_HOST = "aarch64.*-linux"
do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    install -d ${D}${PYTHON_SITEPACKAGES_DIR}
    cp -r ${S}/onnxruntime ${S}/onnxruntime-${PV}.dist-info ${D}${PYTHON_SITEPACKAGES_DIR}/
    find ${D}${PYTHON_SITEPACKAGES_DIR} -name "__pycache__" -prune -exec rm -rf {} \;
}

FILES:${PN} = "${PYTHON_SITEPACKAGES_DIR}"
RDEPENDS:${PN} = "python3-core python3-numpy python3-packaging python3-protobuf python3-flatbuffers python3-sympy python3-coloredlogs"
INSANE_SKIP:${PN} = "already-stripped ldflags textrel file-rdeps"
