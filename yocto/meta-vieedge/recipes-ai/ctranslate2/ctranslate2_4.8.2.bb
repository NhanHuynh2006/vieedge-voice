SUMMARY = "CTranslate2 - fast Transformer inference (Whisper/PhoWhisper decoder on CPU)"
HOMEPAGE = "https://github.com/OpenNMT/CTranslate2"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=d3fd51533b2da791cd8834be0c55459c"

# Only the submodules needed for an ARM CPU build (no CUDA/cutlass/thrust/tests/CLI).
SRC_URI = " \
    git://github.com/OpenNMT/CTranslate2.git;protocol=https;nobranch=1;name=ct2 \
    git://github.com/gabime/spdlog.git;protocol=https;nobranch=1;name=spdlog;destsuffix=git/third_party/spdlog \
    git://github.com/google/ruy.git;protocol=https;nobranch=1;name=ruy;destsuffix=git/third_party/ruy \
    git://github.com/pytorch/cpuinfo.git;protocol=https;nobranch=1;name=cpuinfo;destsuffix=git/third_party/ruy/third_party/cpuinfo \
"
SRCREV_ct2 = "d44d2d069eb88c7b7804da864c10c201501cb4a9"
SRCREV_spdlog = "76fb40d95455f249bd70824ecfcae7a8f0930fa3"
SRCREV_ruy = "363f252289fb7a1fba1703d99196524698cb884d"
SRCREV_cpuinfo = "082deffc80ce517f81dc2f3aebe6ba671fcd09c9"
SRCREV_FORMAT = "ct2"
S = "${WORKDIR}/git"

inherit cmake

DEPENDS = "openblas"

# Ruy = int8 GEMM (ARM dotprod kernels), OpenBLAS = float GEMM; -mcpu=cortex-a76 comes from the tune.
EXTRA_OECMAKE = " \
    -DCMAKE_BUILD_TYPE=Release \
    -DWITH_MKL=OFF \
    -DWITH_DNNL=OFF \
    -DWITH_RUY=ON \
    -DWITH_OPENBLAS=ON \
    -DOPENMP_RUNTIME=COMP \
    -DENABLE_CPU_DISPATCH=OFF \
    -DBUILD_CLI=OFF \
    -DBUILD_TESTS=OFF \
    -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON \
    -DOPENBLAS_INCLUDE_DIR=${STAGING_INCDIR} \
    -DOPENBLAS_LIBRARY=${STAGING_LIBDIR}/libopenblas.so \
"

FILES:${PN}-dev += "${libdir}/cmake"
