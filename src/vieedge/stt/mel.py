"""Whisper-compatible log-mel spectrogram in pure numpy (no torch on the device).

Matches openai-whisper `log_mel_spectrogram`: 400-pt periodic Hann, hop 160, reflect-padded
centred STFT, power spectrum, 80 (or 128) mel filters, log10, dynamic range 8, (x+4)/4.
Hailo encoders take a fixed window (tiny 10 s / base 5 s): audio is zero-padded to the window first.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
N_FFT = 400
HOP = 160


@lru_cache(maxsize=2)
def mel_filters(n_mels: int = 80) -> np.ndarray:
    with np.load(Path(__file__).parent / "assets" / "mel_filters.npz") as f:
        return f[f"mel_{n_mels}"].astype(np.float32)


@lru_cache(maxsize=1)
def _window() -> np.ndarray:
    return (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(N_FFT) / N_FFT)).astype(np.float32)


def pad_or_trim(audio: np.ndarray, n_samples: int) -> np.ndarray:
    if len(audio) >= n_samples:
        return audio[:n_samples]
    return np.pad(audio, (0, n_samples - len(audio)))


def log_mel(audio: np.ndarray, n_mels: int = 80) -> np.ndarray:
    """audio float32 16 kHz -> (n_mels, len(audio)//160)."""
    audio = np.asarray(audio, dtype=np.float32)
    x = np.pad(audio, (N_FFT // 2, N_FFT // 2), mode="reflect")
    n_frames = 1 + (len(x) - N_FFT) // HOP
    frames = np.lib.stride_tricks.as_strided(x, shape=(n_frames, N_FFT), strides=(x.strides[0] * HOP, x.strides[0]))
    spec = np.fft.rfft(frames * _window(), axis=1)
    power = (spec.real ** 2 + spec.imag ** 2)[:-1].astype(np.float32)  # drop last frame like whisper
    mel = mel_filters(n_mels) @ power.T
    log_spec = np.log10(np.maximum(mel, 1e-10))
    log_spec = np.maximum(log_spec, log_spec.max() - 8.0)
    return ((log_spec + 4.0) / 4.0).astype(np.float32)


def window_mel(audio: np.ndarray, window_s: float, n_mels: int = 80) -> np.ndarray:
    """Pad/trim to the encoder window, then (n_mels, window_s*100)."""
    return log_mel(pad_or_trim(audio, int(window_s * SAMPLE_RATE)), n_mels)
