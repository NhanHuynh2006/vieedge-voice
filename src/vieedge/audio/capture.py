"""Microphone stream (main process side): fixed-size frames with capture timestamps, echo-guarded."""
from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from .echo_guard import EchoGuard
from .rt_engine import AudioEngine


@dataclass
class Frame:
    pcm: np.ndarray  # float32 [-1, 1]
    t_end: float  # monotonic time of the last sample
    idx: int  # absolute index of the first sample
    muted: bool


class MicStream:
    def __init__(self, engine: AudioEngine, frame_samples: int = 512, guard: EchoGuard | None = None):
        self.engine = engine
        self.n = frame_samples
        self.guard = guard or EchoGuard("off")
        self._buf = np.zeros(0, dtype=np.int16)
        self._buf_idx = 0
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def frames(self) -> Iterator[Frame]:
        sr = self.engine.cap_rate
        while not self._stop:
            x, idx = self.engine.read()
            if len(x) == 0:
                time.sleep(0.005)
                continue
            if len(self._buf) == 0:
                self._buf_idx = idx
            self._buf = np.concatenate([self._buf, x])
            while len(self._buf) >= self.n:
                chunk, self._buf = self._buf[: self.n], self._buf[self.n:]
                first = self._buf_idx
                self._buf_idx += self.n
                t_end = self.engine.sample_time(first + self.n)
                pcm = chunk.astype(np.float32) / 32768.0
                pcm, muted = self.guard.filter(pcm, t_end, self.engine.pb.audible_end,
                                               self.engine.pb.available() > 0)
                yield Frame(pcm, t_end, first, muted)
            _ = sr
