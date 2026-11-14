#!/usr/bin/env python3
"""Merge a LoRA adapter into its base model and produce the GGUF quantisation ladder for M0/M1.

  # base model only (no LoRA), all quants
  python training/merge_quantize.py --base models/hf/Qwen__Qwen2.5-1.5B-Instruct --name qwen2.5-1.5b
  # LoRA merged
  python training/merge_quantize.py --base models/hf/Qwen__Qwen2.5-1.5B-Instruct \
      --lora training/runs/qwen2.5-1.5b-lora/adapter --name qwen2.5-1.5b-vi-voice

Outputs models/llm/gguf/<name>-{F16,Q8_0,Q6_K,Q5_K_M,Q4_K_M,Q3_K_M}.gguf
Optional --imatrix: importance matrix from the Q&A train set (improves Q3/Q4 quality).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LLAMA = ROOT / "third_party" / "llama.cpp"
BIN = LLAMA / "build" / "bin"
QUANTS = ["Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_M"]


def run(cmd: list[str]) -> None:
    print("+", " ".join(map(str, cmd)), flush=True)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    subprocess.run(list(map(str, cmd)), check=True, env=env)


def merge(base: Path, lora: Path, out: Path) -> Path:
    os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")  # merge on CPU: the GPU may be busy training
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    out.mkdir(parents=True, exist_ok=True)
    model = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16, device_map="cpu")
    model = PeftModel.from_pretrained(model, lora).merge_and_unload()
    model.save_pretrained(out, safe_serialization=True)
    AutoTokenizer.from_pretrained(lora if (lora / "tokenizer_config.json").exists() else base).save_pretrained(out)
    for f in ("chat_template.jinja", "generation_config.json"):
        if (base / f).exists() and not (out / f).exists():
            (out / f).write_bytes((base / f).read_bytes())
    copy_mtp(base, out)
    return out


def copy_mtp(base: Path, out: Path) -> None:
    """Qwen3.5 checkpoints carry a multi-token-prediction block (`mtp.*`) that the HF CausalLM class does not
    load, so it is missing after merge_and_unload. llama.cpp expects it (extra nextn layer; also usable as an
    MTP draft for speculative decoding), and LoRA never touched it -> copy it verbatim from the base."""
    from safetensors import safe_open
    from safetensors.torch import save_file

    tensors = {}
    for f in sorted(base.glob("*.safetensors")):
        with safe_open(f, "pt") as sf:
            for k in sf.keys():
                if k.startswith("mtp."):
                    tensors[k] = sf.get_tensor(k)
    if tensors:
        save_file(tensors, out / "model-mtp.safetensors")
        idx = out / "model.safetensors.index.json"
        if idx.exists():
            j = json.loads(idx.read_text())
            j["weight_map"].update({k: "model-mtp.safetensors" for k in tensors})
            idx.write_text(json.dumps(j, indent=1))
        print(f"copied {len(tensors)} MTP tensors from the base model")


def imatrix_text(path: Path, n: int = 600) -> Path:
    """Calibration text for llama-imatrix: questions + answers from the Q&A train split."""
    out = ROOT / "models" / "llm" / "imatrix_calib.txt"
    rows = [json.loads(l) for l in open(path, encoding="utf-8")][:n]
    out.write_text("\n\n".join(f"{r['q']}\n{r['a']}" for r in rows), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--lora", type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--quants", nargs="*", default=QUANTS)
    ap.add_argument("--outdir", type=Path, default=ROOT / "models" / "llm" / "gguf")
    ap.add_argument("--imatrix", action="store_true")
    ap.add_argument("--keep-f16", action="store_true", default=True)
    a = ap.parse_args()
    a.outdir.mkdir(parents=True, exist_ok=True)
    src = a.base
    if a.lora:
        src = merge(a.base, a.lora, ROOT / "models" / "llm" / "merged" / a.name)
    f16 = a.outdir / f"{a.name}-F16.gguf"
    if not f16.exists():
        run([sys.executable, LLAMA / "convert_hf_to_gguf.py", src, "--outtype", "f16", "--outfile", f16])
    imat = []
    if a.imatrix:
        calib = imatrix_text(ROOT / "data" / "qa" / "train.jsonl")
        dat = a.outdir / f"{a.name}.imatrix.gguf"
        if not dat.exists():
            run([BIN / "llama-imatrix", "-m", f16, "-f", calib, "-o", dat, "-c", "512", "-ngl", "99"])
        imat = ["--imatrix", dat]
    for q in a.quants:
        out = a.outdir / f"{a.name}-{q}.gguf"
        if not out.exists():
            run([BIN / "llama-quantize", *imat, f16, out, q])
    for p in sorted(a.outdir.glob(f"{a.name}-*.gguf")):
        print(f"{p.name}\t{p.stat().st_size / 2**20:.0f} MiB")


if __name__ == "__main__":
    main()
