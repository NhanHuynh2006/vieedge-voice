SUMMARY = "Private Wi-Fi access point for the VieEdge dashboard (no internet needed)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://hostapd-vieedge.conf \
    file://dnsmasq-vieedge.conf \
    file://20-wlan0-ap.network \
    file://10-eth0.network \
    file://vieedge-hotspot.service \
"
S = "${WORKDIR}"

inherit systemd allarch

do_install() {
    install -d ${D}${sysconfdir}/vieedge ${D}${sysconfdir}/systemd/network ${D}${systemd_system_unitdir}
    install -m 0600 ${WORKDIR}/hostapd-vieedge.conf ${D}${sysconfdir}/vieedge/
    install -m 0644 ${WORKDIR}/dnsmasq-vieedge.conf ${D}${sysconfdir}/vieedge/
    install -m 0644 ${WORKDIR}/20-wlan0-ap.network ${WORKDIR}/10-eth0.network ${D}${sysconfdir}/systemd/network/
    install -m 0644 ${WORKDIR}/vieedge-hotspot.service ${D}${systemd_system_unitdir}/
}

SYSTEMD_SERVICE:${PN} = "vieedge-hotspot.service"
FILES:${PN} += "${systemd_system_unitdir}"
RDEPENDS:${PN} = "hostapd dnsmasq"
