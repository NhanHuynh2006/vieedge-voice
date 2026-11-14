SUMMARY = "VieEdge-Voice application (pipeline, dashboard, benchmarks, tuning)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=0074963ba92a78350646d7dd3ff4d832"

# Built straight from this repository (src/, deploy/, bench/)
inherit externalsrc systemd python3-dir
EXTERNALSRC = "${VIEEDGE_REPO}"
EXTERNALSRC_BUILD = "${WORKDIR}/build"
EXTERNALSRC_SYMLINKS = ""

do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    install -d ${D}${PYTHON_SITEPACKAGES_DIR}
    cp -r ${S}/src/vieedge ${D}${PYTHON_SITEPACKAGES_DIR}/
    find ${D}${PYTHON_SITEPACKAGES_DIR} -name "__pycache__" -prune -exec rm -rf {} \;

    install -d ${D}/opt/vieedge/bench ${D}/opt/vieedge/models ${D}/opt/vieedge/data ${D}/opt/vieedge/results
    cp -r ${S}/bench/. ${D}/opt/vieedge/bench/
    find ${D}/opt/vieedge -name "__pycache__" -prune -exec rm -rf {} \;

    install -d ${D}/opt/vieedge/models/fastpath
    install -m 0644 ${S}/data/fastpath/faq.jsonl ${S}/data/fastpath/say_phrases.txt ${D}/opt/vieedge/models/fastpath/
    install -d ${D}/opt/vieedge/models/an_toan
    install -m 0644 ${S}/data/an_toan/the_an_toan.json ${S}/data/an_toan/nguon.json ${D}/opt/vieedge/models/an_toan/

    install -d ${D}${sysconfdir}/vieedge
    install -m 0644 ${S}/deploy/config/vieedge-pi.yaml ${D}${sysconfdir}/vieedge/config.yaml

    install -d ${D}${sysconfdir}/vieedge/certs
    install -m 0644 ${S}/deploy/certs/vieedge.crt ${D}${sysconfdir}/vieedge/certs/
    install -m 0600 ${S}/deploy/certs/vieedge.key ${D}${sysconfdir}/vieedge/certs/

    install -d ${D}${systemd_system_unitdir}
    install -m 0644 ${S}/deploy/systemd/vieedge.service ${D}${systemd_system_unitdir}/
    install -m 0644 ${S}/deploy/systemd/vieedge-tuning.service ${D}${systemd_system_unitdir}/

    install -d ${D}${bindir}
    for f in ${S}/deploy/scripts/vieedge-*; do
        install -m 0755 $f ${D}${bindir}/
    done
    chown -R root:root ${D}
}

SYSTEMD_SERVICE:${PN} = "vieedge.service vieedge-tuning.service"
SYSTEMD_AUTO_ENABLE = "enable"

FILES:${PN} += "${PYTHON_SITEPACKAGES_DIR}/vieedge /opt/vieedge ${systemd_system_unitdir}"

RDEPENDS:${PN} = " \
    bash python3-core python3-modules python3-numpy python3-psutil python3-pyyaml python3-json python3-asyncio \
    python3-multiprocessing python3-threading python3-logging python3-ctypes python3-audio \
    python3-fastapi python3-uvicorn python3-websockets python3-pyalsaaudio python3-gpiod \
    python3-ctranslate2 python3-onnxruntime python3-sherpa-onnx espeak-ng llama-cpp util-linux-taskset \
"
RRECOMMENDS:${PN} = "pyhailort libhailort hailo-pci hailo-firmware"
