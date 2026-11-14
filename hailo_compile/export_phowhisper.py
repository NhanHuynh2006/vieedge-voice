#!/usr/bin/env python3
"""Export the (Pho)Whisper encoder (and the fixed-sequence decoder, for completeness) to ONNX with
hailo-whisper's Hailo-compatible PyTorch patch (Conv1d->Conv2d, fixed audio window, split logits).

Same procedure as hailo-whisper's export/export_whisper_model.py, but the weights come from an
openai-format checkpoint produced by hf_to_openai.py instead of the original OpenAI download.

  python hailo_compile/export_phowhisper.py --ckpt hailo_compile/work/phowhisper-tiny.pt --variant tiny --window 10
  -> hailo_compile/work/onnx/phowhisper-tiny-encoder-10s.onnx (+ decoder-10s-seq-32.onnx)
"""
from __future__ import annotations

import argparse
import importlib
import re
import sys
from pathlib import Path

import onnx
import torch

HERE = Path(__file__).resolve().parent
HW = HERE / "work" / "hailo-whisper"
MODEL_PY = HW / "third_party" / "whisper" / "whisper" / "model.py"

DEFAULTS = {"tiny": (10, 32, 384), "base": (5, 24, 512)}


def set_scaling_factor(f: int) -> None:
    src = MODEL_PY.read_text()
    MODEL_PY.write_text(re.sub(r"(self\.dims\.n_audio_ctx\s*//\s*)\d+", lambda m: f"{m.group(1)}{f}", src))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True, help="openai-format checkpoint (.pt) or an openai model name")
    ap.add_argument("--variant", choices=["tiny", "base"], required=True)
    ap.add_argument("--window", type=int, help="encoder input seconds (tiny 10, base 5 by default)")
    ap.add_argument("--seq", type=int, help="decoder sequence length")
    ap.add_argument("--name", help="output prefix, default phowhisper-<variant>")
    ap.add_argument("--outdir", type=Path, default=HERE / "work" / "onnx")
    ap.add_argument("--no-decoder", action="store_true")
    ap.add_argument("--opset", type=int, default=17)
    a = ap.parse_args()
    win, seq, hidden = DEFAULTS[a.variant]
    win, seq = a.window or win, a.seq or seq
    scaling = int(3000 / (win * 100))
    set_scaling_factor(scaling)
    sys.path.insert(0, str(HW / "third_party" / "whisper"))
    import whisper  # noqa: E402  (patched copy, imported after setting the window)

    importlib.reload(whisper.model)
    model = whisper.load_model(a.ckpt, device="cpu").eval()
    name = a.name or f"phowhisper-{a.variant}"
    a.outdir.mkdir(parents=True, exist_ok=True)
    frames = 3000 // scaling
    enc_path = a.outdir / f"{name}-encoder-{win}s.onnx"
    torch.onnx.export(model.encoder, torch.randn(1, 80, 1, frames), enc_path, input_names=["mel"],
                      output_names=["hidden"], opset_version=a.opset, dynamo=False)
    from onnxsim import simplify

    # constant folding only: onnxsim's fusion folds GELU's x*0.5 into the next conv, which breaks the
    # Erf-GELU pattern the Hailo parser recognises ("UnsupportedActivationLayerError ... /Erf")
    m, ok = simplify(onnx.load(enc_path), perform_optimization=False)
    onnx.save(m, enc_path)
    print(f"encoder -> {enc_path} (simplified={ok}, frames={frames})")
    if a.no_decoder:
        return
    enc_len = 1500 // scaling
    hs = torch.randn(1, enc_len, model.dims.n_text_state)
    ids = torch.cat([torch.tensor([[50258]]), torch.zeros((1, seq - 1), dtype=torch.int64)], dim=1)
    dec_path = a.outdir / f"{name}-decoder-{win}s-seq-{seq}.onnx"
    torch.onnx.export(model.decoder, (ids, hs), dec_path, opset_version=13, input_names=["decoder_input_ids", "encoder_hidden_states"],
                      output_names=["logits"], dynamo=False)
    m, ok = simplify(onnx.load(dec_path), overwrite_input_shapes={"decoder_input_ids": [1, seq],
                                                                  "encoder_hidden_states": [1, enc_len, hidden]})
    onnx.save(m, dec_path)
    print(f"decoder -> {dec_path} (simplified={ok})")


if __name__ == "__main__":
    main()
