SUMMARY = "Starlette ASGI framework"
LICENSE = "BSD-3-Clause"
LIC_FILES_CHKSUM = "file://LICENSE.md;md5=11e8c8dbfd5fa373c703de492140ff7a"
SRC_URI[sha256sum] = "7f7361f34eed179294600af672f565727419830b54b7b084efe44bb82d2fccd5"
require python3-purepy.inc
RDEPENDS:${PN} = "python3-core python3-anyio python3-typing-extensions python3-json python3-asyncio"
