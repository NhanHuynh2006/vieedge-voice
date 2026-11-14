SUMMARY = "Uvicorn ASGI server"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE.md;md5=5c778842f66a649636561c423c0eec2e"
SRC_URI[sha256sum] = "35919a9a979d7a59334b6b10e05d77c1d0d574c50e0fc98b8b1a0f165708b55a"
require python3-purepy.inc
RDEPENDS:${PN} = "python3-core python3-click python3-h11 python3-websockets python3-httptools python3-asyncio python3-logging"
