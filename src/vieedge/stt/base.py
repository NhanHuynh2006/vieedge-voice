"""Common STT interface. Every backend (CPU CTranslate2, Hailo-encoder + CPU-decoder, ONNX stand-in)
implements `transcribe`, so CPU <-> NPU is a config switch (PLAN §16)."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class STTResult:
    text: str
    t_start: float
    t_end: float
    timings: dict = field(default_factory=dict)  # mel_ms, encoder_ms, decoder_ms
    n_tokens: int = 0
    confidence: float | None = None  # mean token log-probability of the best hypothesis (closer to 0 = surer)

    @property
    def latency_ms(self) -> float:
        return (self.t_end - self.t_start) * 1000


class STT(ABC):
    name = "stt"
    window_s: float = 30.0  # longest audio one call can take

    @abstractmethod
    def transcribe(self, audio: np.ndarray, beam_size: int | None = None) -> STTResult:
        """audio: float32, 16 kHz, <= window_s seconds."""

    def warmup(self) -> None:
        self.transcribe(np.zeros(16000, dtype=np.float32))

    def info(self) -> dict:
        return {"name": self.name, "window_s": self.window_s}


def now() -> float:
    return time.monotonic()
