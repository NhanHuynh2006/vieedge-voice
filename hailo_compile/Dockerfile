# Hailo Dataflow Compiler environment (x86-64, Ubuntu 22.04, Python 3.10) — PLAN §5.1.
# The DFC and HailoRT wheels require a (free) Hailo Developer Zone account, so they are NOT downloaded
# here: put them in hailo_compile/wheels/ first (see wheels/README.md), then
#   docker build -t vieedge-dfc hailo_compile
#   ./hailo_compile/run_all.sh            # runs inside this image
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.10 python3.10-venv python3.10-dev python3-pip git ffmpeg libportaudio2 graphviz graphviz-dev \
      build-essential libgl1 libglib2.0-0 curl ca-certificates && rm -rf /var/lib/apt/lists/*
RUN python3.10 -m venv /opt/dfc && /opt/dfc/bin/pip install --upgrade pip wheel
COPY wheels/ /tmp/wheels/
RUN set -e; DFC=$(ls /tmp/wheels/hailo_dataflow_compiler-3.*-py3-none-linux_x86_64.whl | head -1); \
    /opt/dfc/bin/pip install "$DFC"; \
    if ls /tmp/wheels/hailort-4.*-cp310-*.whl >/dev/null 2>&1; then /opt/dfc/bin/pip install /tmp/wheels/hailort-4.*-cp310-*.whl; fi
# hailo-whisper's export/eval deps + ours (numpy/onnx versions stay those pinned by the DFC wheel)
RUN /opt/dfc/bin/pip install "transformers>=4.50,<5" onnx onnxsim onnxruntime soundfile tiktoken more-itertools numba jiwer pyyaml ctranslate2
ENV PATH=/opt/dfc/bin:$PATH
WORKDIR /repo
