SUMMARY = "rtla - Real-Time Linux Analysis (timerlat / osnoise / hwnoise)"
DESCRIPTION = "Built from the running kernel's tools/tracing/rtla so it always matches the tracers in the kernel."
LICENSE = "GPL-2.0-only"
LIC_FILES_CHKSUM = "file://COPYING;md5=6bc538ed5bd9a7fc9398086aedcd7e46"

inherit kernelsrc pkgconfig

DEPENDS = "libtraceevent libtracefs"
PACKAGE_ARCH = "${MACHINE_ARCH}"

B = "${WORKDIR}/build"
do_configure[noexec] = "1"

EXTRA_OEMAKE = "-C ${S}/tools/tracing/rtla O=${B} CC='${CC}' AR='${AR}' PKG_CONFIG=pkg-config V=1"

do_compile() {
    mkdir -p ${B}
    oe_runmake LDFLAGS="${LDFLAGS}"
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${B}/rtla ${D}${bindir}/rtla
    for t in osnoise hwnoise timerlat; do
        ln -sf rtla ${D}${bindir}/$t
    done
}

RDEPENDS:${PN} = "libtraceevent libtracefs"
