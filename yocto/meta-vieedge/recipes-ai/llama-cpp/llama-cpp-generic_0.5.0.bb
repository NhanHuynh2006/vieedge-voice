# "Default" build for experiment M0: generic ARMv8-A, no dotprod/fp16, no LTO.
# Installed under /opt/llama-generic so it can coexist with the optimised build.
require llama-cpp.inc

LLAMA_PREFIX = "/opt/llama-generic"
TUNE_CCARGS:remove = "-mcpu=cortex-a76"
TUNE_CCARGS:append = " -march=armv8-a"
EXTRA_OECMAKE += " -DGGML_CPU_ARM_ARCH=armv8-a -DGGML_LTO=OFF"

FILES:${PN} = "/opt/llama-generic"

