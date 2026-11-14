"""Speaker (main process side): queue TTS audio, barge-in flush, first-sample timestamp."""
from __future__ import annotations

import time

import numpy as np

from .resample import resample
from .rt_engine import AudioEngine


class Speaker:
    def __init__(self, engine: AudioEngine):
        self.engine = engine
        self.rate = engine.pb_rate

    def begin_turn(self) -> None:
        """Arm the first-audio timestamp for a new answer."""
        self.engine.arm_first_audio()

    def first_audio_time(self) -> float | None:
        return self.engine.first_audio_time()

    def play(self, audio: np.ndarray, sr: int) -> None:
        """audio: float32 [-1,1] at `sr`."""
        if sr != self.rate:
            audio = resample(audio, sr, self.rate)
        pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
        self.engine.play(pcm)

    def silence(self, ms: int) -> None:
        self.engine.play(np.zeros(int(self.rate * ms / 1000), dtype=np.int16))

    def stop(self) -> None:
        self.engine.flush_playback()

    def wait_done(self, timeout: float = 60.0) -> None:
        t0 = time.monotonic()
        while self.engine.is_audible() and time.monotonic() - t0 < timeout:
            time.sleep(0.02)
