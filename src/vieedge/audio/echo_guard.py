"""Echo guard: stop the assistant from hearing (and answering) itself.

mode "mute": microphone frames captured while the speaker is audible, plus `tail_ms` after the
last audible sample (room reverberation + device latency), are replaced by silence before VAD.
mode "off": rely on a mic with hardware AEC. Barge-in is done with the push-to-talk button.
"""
from __future__ import annotations

import numpy as np


class EchoGuard:
    def __init__(self, mode: str = "mute", tail_ms: int = 300):
        self.mode = mode
        self.tail = tail_ms / 1000.0
        self.muted_frames = 0

    def filter(self, frame: np.ndarray, t_frame_end: float, audible_end: float, playing: bool) -> tuple[np.ndarray, bool]:
        """Return (frame_to_use, was_muted)."""
        if self.mode != "mute":
            return frame, False
        if playing or t_frame_end < audible_end + self.tail:
            self.muted_frames += 1
            return np.zeros_like(frame), True
        return frame, False
