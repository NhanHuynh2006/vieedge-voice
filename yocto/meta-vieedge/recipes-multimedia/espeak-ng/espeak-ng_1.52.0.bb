SUMMARY = "eSpeak NG speech synthesizer (used as the phonemizer for Piper vi_VN voices)"
HOMEPAGE = "https://github.com/espeak-ng/espeak-ng"
LICENSE = "GPL-3.0-or-later & BSD-2-Clause & Apache-2.0"
LIC_FILES_CHKSUM = "file://COPYING;md5=d32239bcb673463ab874e80d47fae504"

# libsonic is pulled with CMake FetchContent upstream; bitbake fetches it instead (no network in do_configure)
SRC_URI = " \
    https://github.com/espeak-ng/espeak-ng/archive/refs/tags/${PV}.tar.gz;downloadfilename=espeak-ng-${PV}.tar.gz \
    git://github.com/waywardgeek/sonic.git;protocol=https;nobranch=1;name=sonic;destsuffix=sonic \
"
SRC_URI[sha256sum] = "bb4338102ff3b49a81423da8a1a158b420124b055b60fa76cfb4b18677130a23"
SRCREV_sonic = "fbf75c3d6d846bad3bb3d456cbc5d07d9fd8c104"
S = "${WORKDIR}/espeak-ng-${PV}"

inherit cmake

EXTRA_OECMAKE = " \
    -DBUILD_SHARED_LIBS=ON \
    -DUSE_MBROLA=OFF \
    -DUSE_LIBSONIC=OFF \
    -DUSE_LIBPCAUDIO=OFF \
    -DUSE_ASYNC=OFF \
    -DESPEAK_BUILD_MANPAGES=OFF \
    -DBUILD_TESTING=OFF \
    -DFETCHCONTENT_SOURCE_DIR_SONIC-GIT=${WORKDIR}/sonic \
"

# The phoneme/dictionary data is compiled by running espeak-ng itself, which cannot run when
# cross-compiling. The data is architecture independent, so the target build only compiles the
# library + CLI and takes espeak-ng-data from espeak-ng-native.
DEPENDS:append:class-target = " espeak-ng-native"

do_compile:class-target() {
    cmake_runcmake_build --target espeak-ng-bin
}

do_install:class-target() {
    install -d ${D}${bindir} ${D}${libdir} ${D}${includedir} ${D}${datadir}
    install -m 0755 ${B}/src/espeak-ng ${D}${bindir}/espeak-ng
    cp -P ${B}/src/libespeak-ng/libespeak-ng.so* ${D}${libdir}/
    cp -r ${S}/src/include/espeak ${S}/src/include/espeak-ng ${D}${includedir}/
    cp -r ${STAGING_DATADIR_NATIVE}/espeak-ng-data ${D}${datadir}/
}

FILES:${PN} += "${datadir}/espeak-ng-data"
BBCLASSEXTEND = "native"
