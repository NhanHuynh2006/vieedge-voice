SUMMARY = "sherpa-onnx (Python) - runs the Vietnamese Zipformer RNN-T speech recogniser on the CPU"
DESCRIPTION = "Official manylinux aarch64 wheels (+ the sherpa-onnx-core shared libraries, which bundle onnxruntime)."
HOMEPAGE = "https://github.com/k2-fsa/sherpa-onnx"
LICENSE = "Apache-2.0"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/Apache-2.0;md5=89aea4e17d99a7cacdbeed46a0096b10"

PYV_TAG = "cp312"
SRC_URI = " \
    https://files.pythonhosted.org/packages/1f/5f/22e1571146b2c0b581657562d5919b69da13ed93dc70049f42d45fe9e84c/sherpa_onnx-${PV}-${PYV_TAG}-${PYV_TAG}-manylinux2014_aarch64.manylinux_2_17_aarch64.whl;downloadfilename=sherpa_onnx-${PV}.zip;name=py;subdir=whl \
    https://files.pythonhosted.org/packages/9c/72/02227b14cd3fb3d504a8814ad144ed321a53331948c893821e02f4abb1d7/sherpa_onnx_core-${PV}-py3-none-manylinux2014_aarch64.whl;downloadfilename=sherpa_onnx_core-${PV}.zip;name=core;subdir=whl \
"
SRC_URI[py.sha256sum] = "2520b1e7b779a29a493a8cec893612218dfad7304786bf3f64df2ff7ac6c3302"
SRC_URI[core.sha256sum] = "a51a03d55c376c32e15dd63ea852236042ba91a5cd73e253bbf7cf21f6582ba9"
S = "${WORKDIR}/whl"

inherit python3-dir

COMPATIBLE_HOST = "aarch64.*-linux"
do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    install -d ${D}${PYTHON_SITEPACKAGES_DIR}
    cp -r ${S}/sherpa_onnx ${S}/sherpa_onnx.libs ${D}${PYTHON_SITEPACKAGES_DIR}/
    cp -r ${S}/sherpa_onnx-${PV}.dist-info ${S}/sherpa_onnx_core-${PV}.dist-info ${D}${PYTHON_SITEPACKAGES_DIR}/
    find ${D}${PYTHON_SITEPACKAGES_DIR} -name "__pycache__" -prune -exec rm -rf {} \;
}

FILES:${PN} = "${PYTHON_SITEPACKAGES_DIR}"
RDEPENDS:${PN} = "python3-core python3-numpy"
INSANE_SKIP:${PN} = "already-stripped ldflags textrel file-rdeps dev-so libdir"
