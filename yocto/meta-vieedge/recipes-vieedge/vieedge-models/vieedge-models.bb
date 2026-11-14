SUMMARY = "VieEdge-Voice models baked into the image (optional, VIEEDGE_BUNDLE_MODELS = 1)"
LICENSE = "CLOSED"

# Directory produced on the laptop by scripts/stage_models.sh (default: <repo>/models/deploy)
VIEEDGE_MODELS_DIR ?= "${VIEEDGE_REPO}/models/deploy"

do_configure[noexec] = "1"
do_compile[noexec] = "1"
do_install[nostamp] = "1"

do_install() {
    if [ ! -d "${VIEEDGE_MODELS_DIR}" ]; then
        bbfatal "VIEEDGE_MODELS_DIR=${VIEEDGE_MODELS_DIR} does not exist (run scripts/stage_models.sh first)"
    fi
    install -d ${D}/opt/vieedge/models
    cp -rL ${VIEEDGE_MODELS_DIR}/. ${D}/opt/vieedge/models/
    chown -R root:root ${D}/opt/vieedge/models
}

FILES:${PN} = "/opt/vieedge/models"
INSANE_SKIP:${PN} = "already-stripped arch file-rdeps"
EXCLUDE_FROM_SHLIBS = "1"
