SUMMARY = "Python bindings for CTranslate2"
HOMEPAGE = "https://github.com/OpenNMT/CTranslate2"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://../LICENSE;md5=d3fd51533b2da791cd8834be0c55459c"

SRC_URI = "git://github.com/OpenNMT/CTranslate2.git;protocol=https;nobranch=1"
SRCREV = "d44d2d069eb88c7b7804da864c10c201501cb4a9"
S = "${WORKDIR}/git/python"

inherit setuptools3

DEPENDS += "ctranslate2 python3-pybind11-native python3-pybind11"
export CTRANSLATE2_ROOT = "${STAGING_DIR_TARGET}${prefix}"

RDEPENDS:${PN} = "ctranslate2 python3-numpy python3-pyyaml python3-setuptools"
