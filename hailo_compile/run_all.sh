#!/usr/bin/env bash
# Full PhoWhisper -> HEF flow for Hailo-8L (S3 + S4 ablation). Run on the x86 laptop.
#   ./hailo_compile/run_all.sh            # uses the vieedge-dfc docker image (needs wheels/ filled)
#   ./hailo_compile/run_all.sh --native   # already inside a DFC venv
# Steps that do NOT need the DFC (checkpoint conversion, ONNX export, calibration sets) are done
# on the host first; compile steps run inside the container.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
PY="${PY:-.venv/bin/python}"
W=hailo_compile/work

# 0. hailo-whisper (patched OpenAI whisper code used for export)
if [[ ! -d $W/hailo-whisper ]]; then
  git clone https://github.com/hailocs/hailo-whisper.git $W/hailo-whisper
  (cd $W/hailo-whisper && git submodule update --init --depth 1 && cd third_party/whisper && git apply ../../hailo-compatibility-changes.patch)
fi

# 1. HF PhoWhisper -> openai checkpoint -> ONNX (fixed windows)
for v in tiny base; do
  [[ -f $W/phowhisper-$v.pt ]] || env -u PYTHONPATH $PY hailo_compile/hf_to_openai.py models/hf/vinai__PhoWhisper-$v $W/phowhisper-$v.pt
done
[[ -f $W/onnx/phowhisper-tiny-encoder-10s.onnx ]] || env -u PYTHONPATH $PY hailo_compile/export_phowhisper.py --ckpt $W/phowhisper-tiny.pt --variant tiny --window 10
[[ -f $W/onnx/phowhisper-tiny-encoder-5s.onnx  ]] || env -u PYTHONPATH $PY hailo_compile/export_phowhisper.py --ckpt $W/phowhisper-tiny.pt --variant tiny --window 5 --no-decoder
[[ -f $W/onnx/phowhisper-base-encoder-5s.onnx  ]] || env -u PYTHONPATH $PY hailo_compile/export_phowhisper.py --ckpt $W/phowhisper-base.pt --variant base --window 5
[[ -f $W/onnx/phowhisper-base-encoder-10s.onnx ]] || env -u PYTHONPATH $PY hailo_compile/export_phowhisper.py --ckpt $W/phowhisper-base.pt --variant base --window 10 --no-decoder

# 2. calibration sets: Vietnamese train audio vs English (S4)
for w in 10 5; do for l in vi en; do
  [[ -f $W/calib/${l}_${w}s.npy ]] || env -u PYTHONPATH $PY hailo_compile/make_calib.py --lang $l --window $w --n 1024 -o $W/calib/${l}_${w}s.npy
done; done

# 3. DFC: optimise (INT8) + emulator drift check + compile
JOBS=(
  "phowhisper-tiny-encoder-10s tiny vi_10s vi"
  "phowhisper-tiny-encoder-10s tiny en_10s en"
  "phowhisper-base-encoder-5s  base vi_5s  vi"
  "phowhisper-base-encoder-5s  base en_5s  en"
  "phowhisper-tiny-encoder-5s  tiny vi_5s  vi"
  "phowhisper-base-encoder-10s base vi_10s vi"
)
run_dfc() {
  if [[ "${1:-}" == "--native" ]]; then shift; python "$@"
  else docker run --rm --gpus all -v "$REPO:/repo" -w /repo vieedge-dfc python "$@" 2>/dev/null \
       || docker run --rm -v "$REPO:/repo" -w /repo vieedge-dfc python "$@"; fi
}
MODE="${1:-}"
for j in "${JOBS[@]}"; do
  read -r onnx v calib tag <<<"$j"
  if ls $W/hef/${onnx}_${tag}_h8l/*.hef >/dev/null 2>&1; then echo "have $onnx/$tag"; continue; fi
  echo "=== $onnx  calib=$calib"
  run_dfc $MODE hailo_compile/convert_encoder.py $W/onnx/$onnx.onnx --variant $v --calib $W/calib/$calib.npy --tag $tag \
    || echo "!! $onnx/$tag failed — see PLAN §13 fallback (keep Whisper HEF on NPU + PhoWhisper on CPU)"
done

# 4. stage HEFs for the device
mkdir -p models/stt/hef
for h in $W/hef/*/*.hef; do cp -v "$h" models/stt/hef/; done
echo "Done. Next: scripts/stage_models.sh && scripts/deploy_models.sh <pi-ip>"
