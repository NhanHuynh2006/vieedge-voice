# Optimised build for Cortex-A76 (experiment M5): ARMv8.2-A + dotprod + fp16 kernels, LTO.
require llama-cpp.inc

LLAMA_PREFIX = "${prefix}"
EXTRA_OECMAKE += " \
    -DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16 \
    -DGGML_LTO=ON \
"

