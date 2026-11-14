#!/usr/bin/env bash
# Collect exactly the model files the device needs into models/deploy/ (dereferencing HF-cache symlinks).
# Layout mirrors /opt/vieedge/models on the Pi. ~1.6 GB with the default selection.
#   ./scripts/stage_models.sh            # default selection
#   EXTRA_GGUF="qwen2.5-1.5b-vi-voice-Q8_0 qwen3.5-2b-Q4_K_M" ./scripts/stage_models.sh
set -euo pipefail
cd "$(dirname "$0")/.."
D=models/deploy
mkdir -p $D/stt/ct2 $D/stt/hef $D/stt/onnx $D/tts/piper $D/vad $D/llm/gguf
cp -rL models/stt/ct2/phowhisper-tiny-int8 models/stt/ct2/phowhisper-base-int8 models/stt/ct2/phowhisper-tiny-float32 \
       models/stt/ct2/whisper-tiny-int8 models/stt/ct2/whisper-base-int8 $D/stt/ct2/
cp -L models/stt/hef/*.hef models/stt/hef/*.npy $D/stt/hef/ 2>/dev/null || true      # Hailo Whisper HEFs + our PhoWhisper HEFs
cp -L models/stt/onnx/*encoder*.onnx $D/stt/onnx/                                   # ONNX references for check_encoder_drift
cp -Lf models/tts/piper/*.onnx models/tts/piper/*.onnx.json $D/tts/piper/
cp -L models/vad/silero_vad.onnx $D/vad/
mkdir -p $D/fastpath $D/an_toan && cp data/fastpath/faq.jsonl data/fastpath/say_phrases.txt $D/fastpath/ && cp data/an_toan/the_an_toan.json data/an_toan/nguon.json $D/an_toan/
mkdir -p $D/rag && cp -L models/rag/wiki_vi.sqlite $D/rag/   # Vietnamese Wikipedia (CC BY-SA 3.0), 1.4 GB
mkdir -p $D/stt/zipformer-vi && cp -L models/stt/zipformer-vi/*.int8.onnx models/stt/zipformer-vi/tokens.txt models/stt/zipformer-vi/bpe.model $D/stt/zipformer-vi/   # CC BY-NC-ND 4.0
GGUF="qwen2.5-1.5b-vi-voice-Q4_K_M qwen2.5-0.5b-vi-voice-Q8_0 qwen3.5-2b-vi-voice-Q4_K_M qwen3.5-0.8b-vi-voice-Q4_K_M qwen3.5-0.8b-vi-voice-Q4_0 ${EXTRA_GGUF:-}"
for g in $GGUF; do
  f=models/llm/gguf/$g.gguf
  if [[ -f $f ]]; then cp -L "$f" $D/llm/gguf/; else echo "!! missing $f"; fi
done
# small evaluation data for on-device runs (manifests reference these paths relative to /opt/vieedge)
mkdir -p $D/../deploy_data
du -sh $D; find $D -type f | sort
