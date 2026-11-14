#!/usr/bin/env python3
"""Simulate what the LLM really receives on the device: questions that went through speech and the deployed STT.

Literature (Mousavi et al. 2024 "Are LLMs Robust for Spoken Dialogues?"; Sun et al. 2023 slot filling with noisy ASR):
LLMs fine-tuned only on clean text degrade on ASR transcripts, and fine-tuning on (simulated) ASR-noisy inputs recovers
most of it. Here each question is synthesised with Piper (different voices for train and test), partly mixed with DEMAND
noise (SNR 5-20 dB), and transcribed with the same PhoWhisper-tiny INT8 / 10 s window the assistant uses.

  train rows: voices vais1000-medium + vivos-x_low        -> data/qa/train_asr.jsonl
  test rows : voice 25hours_single-low (never in train)   -> data/qa/test_asr.jsonl
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "bench"))

VOICES = {"train": ["vi_VN-vais1000-medium", "vi_VN-vivos-x_low"], "test": ["vi_VN-25hours_single-low"]}
_G: dict = {}


def init(threads: int, stt_kind: str = "ct2") -> None:
    from common import load_audio
    from vieedge.stt.cpu_ct2 import CT2Whisper
    from vieedge.tts.piper_tts import PiperTTS

    if stt_kind == "zipformer":
        from vieedge.stt.zipformer import ZipformerVi

        _G["stt"] = ZipformerVi(str(ROOT / "models/stt/zipformer-vi"), threads)
    else:
        _G["stt"] = CT2Whisper(str(ROOT / "models/stt/ct2/phowhisper-tiny-int8"), "int8", threads, window_s=10)
    _G["tts"] = {v: PiperTTS(str(ROOT / f"models/tts/piper/{v}.onnx"), 1) for v in sum(VOICES.values(), [])}
    _G["noise"] = [load_audio(str(p)) for p in sorted((ROOT / "data/noise").rglob("ch01.wav"))]


def work(job: tuple) -> dict:
    from common import mix_snr
    from vieedge.audio.resample import resample

    i, split, row, seed = job
    rnd = random.Random(seed * 100003 + i)
    voice = rnd.choice(VOICES[split])
    r = _G["tts"][voice].synthesize(row["q"])
    x = resample(r.audio, r.sample_rate, 16000) * rnd.uniform(0.4, 0.9)
    x = np.concatenate([np.zeros(4000), x, np.zeros(8000)]).astype(np.float32)
    snr = None
    if rnd.random() < 0.4:
        snr = rnd.uniform(5, 20)
        x = mix_snr(x, rnd.choice(_G["noise"]), snr, rnd)
    res = _G["stt"].transcribe(x[: 10 * 16000])
    from vieedge.textproc import normalize_question

    return {**row, "q_clean": row["q"], "q": normalize_question(res.text) or row["q"], "voice": voice,
            "snr": None if snr is None else round(snr, 1), "stt_raw": res.text}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--stt", default="ct2", choices=["ct2", "zipformer"])
    ap.add_argument("--splits", nargs="+", default=["test", "train"])
    a = ap.parse_args()
    suffix = "" if a.stt == "ct2" else "_zip"
    for split in a.splits:
        rows = [json.loads(l) for l in open(ROOT / "data/qa" / f"{split}.jsonl", encoding="utf-8")]
        if a.limit:
            rows = rows[: a.limit]
        jobs = [(i, split, r, 7) for i, r in enumerate(rows)]
        with mp.get_context("spawn").Pool(a.workers, initializer=init, initargs=(a.threads, a.stt)) as pool:
            out = []
            for k, o in enumerate(pool.imap(work, jobs, chunksize=8)):
                out.append(o)
                if k % 200 == 0:
                    print(split, k, len(rows), flush=True)
        dst = ROOT / "data/qa" / f"{split}_asr{suffix}.jsonl"
        with open(dst, "w", encoding="utf-8") as f:
            for o in out:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
        from common import wer

        w = wer([o["q_clean"] for o in out], [o["q"] for o in out])
        print(f"{split}: {len(out)} rows -> {dst}; question WER after TTS->noise->STT = {w:.3f}", flush=True)


if __name__ == "__main__":
    main()
