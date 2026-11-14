#!/usr/bin/env python3
"""Download every model the project uses into models/ (laptop side).

Groups (default: all):
  stt     PhoWhisper tiny/base + Whisper tiny/base (HF) and Hailo's precompiled Whisper HEFs for hailo8l
  tts     Piper vi_VN voices
  vad     Silero VAD (ONNX)
  llm     candidate small LLMs (HF safetensors, for LoRA + GGUF conversion)
  teacher teacher/judge LLM (GGUF, runs on the laptop GPU via llama.cpp Vulkan)
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"

STT_HF = ["vinai/PhoWhisper-tiny", "vinai/PhoWhisper-base", "openai/whisper-tiny", "openai/whisper-base"]

# hailo-apps resources_config.yaml (whisper_h8 / hailo8l)
HAILO_HEF = {
    "whisper-tiny-encoder-10s_h8l.hef": "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper/h8l/tiny-whisper-encoder-10s_15dB_h8l.hef",
    "whisper-tiny-decoder-fixed-seq_h8l.hef": "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper/h8l/tiny-whisper-decoder-fixed-sequence-matmul-split_h8l.hef",
    "whisper-base-encoder-5s_h8l.hef": "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper/h8l/base-whisper-encoder-5s_h8l.hef",
    "whisper-base-decoder-fixed-seq_h8l.hef": "https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/whisper/h8l/base-whisper-decoder-fixed-sequence-matmul-split_h8l.hef",
}

PIPER_VOICES = {
    "vi_VN-vais1000-medium": "vi/vi_VN/vais1000/medium",
    "vi_VN-25hours_single-low": "vi/vi_VN/25hours_single/low",
    "vi_VN-vivos-x_low": "vi/vi_VN/vivos/x_low",
}

SILERO_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"

LLM_HF = [
    # candidates named in PLAN §5.2
    "Qwen/Qwen2.5-1.5B-Instruct",
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen3-1.7B",
    "Qwen/Qwen3-0.6B",
    # newest small multilingual models available at build time (2026-10)
    "Qwen/Qwen3.5-0.8B",
    "Qwen/Qwen3.5-2B",
    "google/gemma-4-E2B-it",
    "SeaLLMs/SeaLLMs-v3-1.5B-Chat",
]

TEACHER = ("unsloth/Qwen3.5-9B-GGUF", "Qwen3.5-9B-Q4_K_M.gguf")


def _url(url: str, dst: Path) -> None:
    if dst.exists() and dst.stat().st_size > 0:
        print(f"  have {dst.relative_to(ROOT)}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"  get  {url}")
    tmp = dst.with_suffix(dst.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.rename(dst)


def _snap(repo: str, sub: str, allow: list[str] | None = None) -> None:
    dst = MODELS / sub / repo.replace("/", "__")
    print(f"  hf   {repo} -> {dst.relative_to(ROOT)}")
    snapshot_download(repo, local_dir=dst, allow_patterns=allow)


def stt() -> None:
    for r in STT_HF:
        _snap(r, "hf", ["*.json", "*.safetensors", "pytorch_model.bin", "*.txt", "*.model", "merges.txt", "vocab.json"])
    for name, url in HAILO_HEF.items():
        _url(url, MODELS / "stt" / "hef" / name)
    for v in ("tiny", "base"):
        for a in ("token_embedding_weight", "onnx_add_input"):
            _url(f"https://hailo-csdata.s3.eu-west-2.amazonaws.com/resources/npy%20files/whisper/decoder_assets/{v}/decoder_tokenization/{a}_{v}.npy",
                 MODELS / "stt" / "hef" / f"{a}_{v}.npy")


def tts() -> None:
    for name, path in PIPER_VOICES.items():
        for ext in (".onnx", ".onnx.json"):
            f = hf_hub_download("rhasspy/piper-voices", f"{path}/{name}{ext}")
            dst = MODELS / "tts" / "piper" / f"{name}{ext}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                dst.symlink_to(f)
            print(f"  have {dst.relative_to(ROOT)}")


def vad() -> None:
    _url(SILERO_URL, MODELS / "vad" / "silero_vad.onnx")


def llm() -> None:
    for r in LLM_HF:
        try:
            _snap(r, "hf", ["*.json", "*.safetensors", "*.txt", "*.jinja", "tokenizer.model", "merges.txt", "vocab.json"])
        except Exception as e:  # gated / removed models must not stop the rest
            print(f"  !! {r}: {e}", file=sys.stderr)


def teacher() -> None:
    repo, fname = TEACHER
    f = hf_hub_download(repo, fname, local_dir=MODELS / "teacher")
    print(f"  have {f}")


GROUPS = {"stt": stt, "tts": tts, "vad": vad, "llm": llm, "teacher": teacher}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("groups", nargs="*", default=list(GROUPS))
    for g in ap.parse_args().groups:
        print(f"[{g}]")
        GROUPS[g]()
