"""Numpy-only resampling (no scipy on the Yocto image): windowed-sinc low-pass + linear interpolation."""
from __future__ import annotations

import numpy as np


def resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if sr_in == sr_out or len(x) == 0:
        return x
    if sr_out < sr_in:  # anti-alias before decimation
        cutoff = 0.45 * sr_out / sr_in
        taps = 63
        n = np.arange(taps) - (taps - 1) / 2
        h = np.sinc(2 * cutoff * n) * np.hamming(taps)
        h /= h.sum()
        x = np.convolve(x, h.astype(np.float32), mode="same")
    t_out = np.arange(int(round(len(x) * sr_out / sr_in))) * (sr_in / sr_out)
    return np.interp(t_out, np.arange(len(x)), x).astype(np.float32)
