SUMMARY = "llama.cpp - LLM inference in C/C++ (llama-server, llama-bench, llama-cli)"
HOMEPAGE = "https://github.com/ggml-org/llama.cpp"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://LICENSE;md5=223b26b3c1143120c87e2b13111d3e99"

# v0.5.0
SRC_URI = "git://github.com/ggml-org/llama.cpp.git;protocol=https;branch=master"
SRCREV = "7fe450e19305b828c199d602c23a8337aaa1f03b"
S = "${WORKDIR}/git"

inherit cmake pkgconfig

DEPENDS = ""

LLAMA_TARGETS = "llama-server llama-cli llama-bench llama-perplexity llama-speculative-simple llama-quantize"

EXTRA_OECMAKE = " \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_NATIVE=OFF \
    -DGGML_OPENMP=ON \
    -DLLAMA_OPENSSL=OFF \
    -DLLAMA_BUILD_TESTS=OFF \
    -DLLAMA_BUILD_EXAMPLES=ON \
    -DLLAMA_BUILD_SERVER=ON \
    -DGGML_BACKEND_DL=OFF \
"

do_compile() {
    cmake_runcmake_build --target ${LLAMA_TARGETS}
}

do_install() {
    install -d ${D}${LLAMA_PREFIX}/bin
    for t in ${LLAMA_TARGETS}; do
        install -m 0755 ${B}/bin/$t ${D}${LLAMA_PREFIX}/bin/$t
    done
}
