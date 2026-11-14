#!/usr/bin/env python3
"""Spoken test questions for end-to-end runs (PLAN §8 last row).

Preferred: 🧑 each team member records 30 questions on a phone (data/e2e/human/<name>/*.wav + questions.txt).
Without recordings: QA test-set questions are synthesised with a *different* Piper voice than the
assistant's (and optionally mixed with hall noise) — a documented limitation in the report.
Writes data/e2e/<set>/qNNN.wav and data/manifests/e2e_<set>.jsonl.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np

from common import ROOT, load_audio, mix_snr
from vieedge.audio.resample import resample
from vieedge.config import load_config
from vieedge.tts.piper_tts import PiperTTS


def write_wav16(path: Path, x: np.ndarray) -> None:
    import wave

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config")
    ap.add_argument("--voice", default="vi_VN-25hours_single-low")
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--source", type=Path, help="jsonl with q (or user) per line instead of the QA test set")
    ap.add_argument("--snr", type=float, help="mix DEMAND noise at this SNR")
    ap.add_argument("--name", default="synth")
    ap.add_argument("--human", type=Path, help="folder of phone recordings with questions.txt (one per line, same order)")
    a = ap.parse_args()
    out = ROOT / "data" / "e2e" / a.name
    rows = []
    if a.human:
        for spk in sorted(p for p in a.human.iterdir() if p.is_dir()):
            qs = (spk / "questions.txt").read_text(encoding="utf-8").splitlines()
            for i, (wav, q) in enumerate(zip(sorted(spk.glob("*.wav")) + sorted(spk.glob("*.m4a")), qs)):
                x = load_audio(str(wav))
                p = out / f"{spk.name}_{i:03d}.wav"
                write_wav16(p, np.concatenate([np.zeros(8000), x, np.zeros(16000)]).astype(np.float32))
                rows.append({"id": p.stem, "audio": str(p.relative_to(ROOT)), "text": q, "speaker": spk.name})
    else:
        cfg = load_config(a.config)
        tts = PiperTTS(cfg.model_path(f"tts/piper/{a.voice}.onnx"), 2)
        qa = [json.loads(l) for l in open(a.source or ROOT / "data" / "qa" / "test.jsonl", encoding="utf-8")]
        qa = [{**r, "q": r.get("q") or r["user"], "a": r.get("a", "")} for r in qa]
        rnd = random.Random(1)
        rnd.shuffle(qa)
        noises = sorted((ROOT / "data" / "noise").rglob("ch01.wav"))
        for i, q in enumerate(qa[: a.n]):
            r = tts.synthesize(q["q"])
            x = resample(r.audio, r.sample_rate, 16000) * 0.7
            x = np.concatenate([np.zeros(8000), x, np.zeros(16000)]).astype(np.float32)
            if a.snr is not None and noises:
                x = mix_snr(x, load_audio(str(rnd.choice(noises))), a.snr, rnd)
            p = out / f"q{i:03d}.wav"
            write_wav16(p, x)
            rows.append({"id": p.stem, "audio": str(p.relative_to(ROOT)), "text": q["q"], "ref_answer": q["a"], "kind": q.get("kind")})
    man = ROOT / "data" / "manifests" / f"e2e_{a.name}.jsonl"
    with open(man, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} questions -> {man}")


if __name__ == "__main__":
    main()
