#!/usr/bin/env python3
"""Build the INT8 calibration set for the encoder (PLAN §5.1, experiment S4).

Mel spectrograms (NHWC, as the Hailo DFC expects: (N, 1, frames, 80)) of *training* audio only:
  --lang vi : VIVOS train + FLEURS vi train   (never the test splits)
  --lang en : LibriSpeech dev-clean            (what hailo-whisper uses -> ablation)
Each utterance is padded/trimmed to the encoder window like at inference time. A small fraction
of clips is mixed with DEMAND noise (SNR 5-20 dB) so activation ranges cover the noisy hall.

  python hailo_compile/make_calib.py --lang vi --window 10 --n 1024 -o hailo_compile/work/calib/vi_10s.npy
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vieedge.stt.mel import window_mel  # noqa: E402

MANIFESTS = {"vi": ["vivos_train", "fleurs_vi_train"], "en": ["librispeech_dev_clean"]}


def load(path: Path) -> np.ndarray:
    import soundfile as sf

    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    x = x.mean(1)
    if sr != 16000:
        from vieedge.audio.resample import resample

        x = resample(x, sr, 16000)
    return x


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["vi", "en"], default="vi")
    ap.add_argument("--window", type=float, default=10)
    ap.add_argument("--n", type=int, default=1024)
    ap.add_argument("--noise-frac", type=float, default=0.2)
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    rows = []
    for m in MANIFESTS[a.lang]:
        rows += [json.loads(l) for l in open(ROOT / "data" / "manifests" / f"{m}.jsonl", encoding="utf-8")]
    rnd.shuffle(rows)
    noises = sorted((ROOT / "data" / "noise").rglob("*.wav"))
    mels = []
    for r in rows[: a.n]:
        x = load(ROOT / r["audio"])[: int(a.window * 16000)]
        if noises and rnd.random() < a.noise_frac:
            n = load(rnd.choice(noises))
            st = rnd.randrange(max(1, len(n) - len(x)))
            n = n[st:st + len(x)]
            n = np.pad(n, (0, len(x) - len(n)))
            snr = rnd.uniform(5, 20)
            p_s, p_n = np.mean(x ** 2) + 1e-9, np.mean(n ** 2) + 1e-9
            x = x + n * np.sqrt(p_s / (p_n * 10 ** (snr / 10)))
        mel = window_mel(x, a.window)  # (80, frames)
        mels.append(mel.T[None, None])  # (1, 1, frames, 80) NHWC
    arr = np.concatenate(mels).astype(np.float32)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.save(a.out, arr)
    print(f"{a.out}: {arr.shape} from {a.lang} train audio")


if __name__ == "__main__":
    main()
