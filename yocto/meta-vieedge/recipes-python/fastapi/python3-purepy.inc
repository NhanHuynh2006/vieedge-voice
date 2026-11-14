# Pure-Python packages whose build backends (pdm-backend, recent hatchling) are not in scarthgap:
# install the package directory straight from the sdist.
inherit pypi python3-dir

PYPI_PACKAGE ?= "${@d.getVar('BPN').replace('python3-', '')}"
PUREPY_MODULE ?= "${PYPI_PACKAGE}"

do_configure[noexec] = "1"
do_compile[noexec] = "1"

do_install() {
    install -d ${D}${PYTHON_SITEPACKAGES_DIR}
    cp -r ${S}/${PUREPY_MODULE} ${D}${PYTHON_SITEPACKAGES_DIR}/
    find ${D}${PYTHON_SITEPACKAGES_DIR} -name "__pycache__" -prune -exec rm -rf {} \;
    chown -R root:root ${D}${PYTHON_SITEPACKAGES_DIR}
}

FILES:${PN} = "${PYTHON_SITEPACKAGES_DIR}"
BBCLASSEXTEND = "native"
