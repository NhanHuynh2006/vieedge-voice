SUMMARY = "FastAPI web framework (dashboard backend)"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=95792ff3fe8e11aa49ceb247e66e4810"
SRC_URI[sha256sum] = "1e2c2a2646905f9e83d32f04a3f86aff4a286669c6c950ca95b5fd68c2602681"
require python3-purepy.inc
RDEPENDS:${PN} = "python3-core python3-json python3-starlette python3-pydantic python3-typing-extensions python3-email"
