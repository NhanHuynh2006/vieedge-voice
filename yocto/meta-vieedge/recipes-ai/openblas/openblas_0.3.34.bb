SUMMARY = "OpenBLAS - optimised BLAS (SGEMM backend for CTranslate2 on ARM)"
HOMEPAGE = "https://www.openblas.net"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE;md5=5adf4792c949a00013ce25d476a2abc0"

SRC_URI = "https://github.com/OpenMathLib/OpenBLAS/releases/download/v${PV}/OpenBLAS-${PV}.tar.gz"
SRC_URI[sha256sum] = "cd7e129868320cc2d033afa920e31202dfe0b8066a5b66661900ccc0f197dfed"
S = "${WORKDIR}/OpenBLAS-${PV}"

# Cortex-A76 kernels, BLAS/CBLAS only (CTranslate2 needs SGEMM, not LAPACK), OpenMP threading.
OPENBLAS_TARGET ?= "CORTEXA76"
EXTRA_OEMAKE = " \
    TARGET=${OPENBLAS_TARGET} \
    HOSTCC='${BUILD_CC}' \
    CC='${CC}' \
    AR='${HOST_PREFIX}ar' \
    CROSS=1 \
    BINARY=64 \
    NOFORTRAN=1 \
    NO_LAPACK=1 \
    NO_LAPACKE=1 \
    NO_STATIC=1 \
    USE_OPENMP=1 \
    NUM_THREADS=8 \
    DYNAMIC_ARCH=0 \
    PREFIX=${prefix} \
    LIBDIR=${libdir} \
"

do_configure() {
    # a killed previous build can leave a truncated libopenblas_*.a behind
    oe_runmake clean || true
}

do_compile() {
    # default target builds the static archive then the shared lib (tests are skipped with CROSS=1)
    oe_runmake
}

do_install() {
    oe_runmake DESTDIR=${D} install
    rm -rf ${D}${libdir}/cmake/openblas/*.cmake.in
    rmdir --ignore-fail-on-non-empty ${D}${bindir} 2>/dev/null || true
}

FILES:${PN}-dev += "${libdir}/cmake"

# the real library is libopenblas_<target>-r<ver>.so (no version suffix); libopenblas.so.0 points to it
FILES_SOLIBSDEV = "${libdir}/libopenblas.so"
FILES:${PN} += "${libdir}/libopenblas_*.so"
INSANE_SKIP:${PN} += "dev-so"
