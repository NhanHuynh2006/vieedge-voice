#!/usr/bin/env bash
# Copy staged models (+ evaluation data) to the Pi over SSH. Works for the Yocto image and Pi OS.
#   ./scripts/deploy_models.sh <pi-ip> [dest=/opt/vieedge]      (Yocto: root / password "vieedge")
set -euo pipefail
cd "$(dirname "$0")/.."
PI=${1:?pi ip}; DEST=${2:-/opt/vieedge}; U=${PI_USER:-root}
ssh $U@$PI "mkdir -p $DEST/models $DEST/data/manifests $DEST/data/qa $DEST/data/llm_bench $DEST/data/noise"
rsync -avh --progress models/deploy/ $U@$PI:$DEST/models/
# evaluation sets used by bench_*.py on the device (test splits only + noise + QA test set)
rsync -avh --relative data/manifests/vivos_test.jsonl data/manifests/fleurs_vi_test.jsonl data/manifests/e2e_*.jsonl \
      data/asr_test/ data/e2e/ data/noise/demand/*/ch01.wav data/qa/test.jsonl data/llm_bench/global_mmlu_vi_test.parquet \
      $U@$PI:$DEST/ 2>/dev/null || true
# Python libs missing from the image (sherpa-onnx for the Zipformer STT) -> site-packages; config -> /etc/vieedge
ssh $U@$PI "[ -d $DEST/models/pylibs ] && cp -r $DEST/models/pylibs/* /usr/lib/python3*/site-packages/ ; mkdir -p /etc/vieedge"
scp deploy/config/vieedge-pi.yaml $U@$PI:/etc/vieedge/config.yaml
echo "done. On the Pi: systemctl restart vieedge ; journalctl -fu vieedge"
