"""Voice activity detection + endpointing.

SileroVAD: Silero VAD (ONNX, MIT) on 32 ms frames, CPU ~0.1 ms/frame.
EnergyVAD: fallback when the ONNX model is missing.
Endpointer: turns per-frame speech probabilities into utterance events:

  start        speech began (pre-roll of `pre_roll_ms` is included in the utterance audio)
  pause        first silent frame after speech  -> IncrementalASR starts the speculative final decode
  resume       speech came back before the endpoint
  end          `endpoint_ms` of silence -> utterance finished (t_speech_end = end of last voiced frame)

P2 sweeps endpoint_ms 300/500/800 (cut-off words vs latency).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

FRAME = 512  # 32 ms at 16 kHz (Silero's native frame)


class SileroVAD:
    def __init__(self, model_path: str, threads: int = 1):
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.sess = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
        names = {i.name for i in self.sess.get_inputs()}
        self.stateful = "state" in names
        self.reset()

    def reset(self) -> None:
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.h = np.zeros((2, 1, 64), dtype=np.float32)
        self.c = np.zeros((2, 1, 64), dtype=np.float32)
        self.ctx = np.zeros((1, 64), dtype=np.float32)

    def __call__(self, frame: np.ndarray) -> float:
        x = frame.astype(np.float32).reshape(1, -1)
        if self.stateful:  # v5 / v6
            inp = np.concatenate([self.ctx, x], axis=1)
            out, self.state = self.sess.run(None, {"input": inp, "state": self.state, "sr": np.array(16000, dtype=np.int64)})
            self.ctx = inp[:, -64:]
        else:  # v4
            out, self.h, self.c = self.sess.run(None, {"input": x, "h": self.h, "c": self.c, "sr": np.array(16000, dtype=np.int64)})
        return float(np.asarray(out).ravel()[0])


class EnergyVAD:
    def __init__(self, threshold_db: float = -42.0):
        self.thr = threshold_db

    def reset(self) -> None: ...

    def __call__(self, frame: np.ndarray) -> float:
        rms = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)) + 1e-9)
        db = 20 * np.log10(rms)
        return float(1 / (1 + np.exp(-(db - self.thr) / 2.0)))


def make_vad(cfg, model_path: str | None):
    if cfg["engine"] == "silero" and model_path:
        try:
            return SileroVAD(model_path)
        except Exception:  # missing model / onnxruntime
            pass
    return EnergyVAD(cfg.get("energy_db", -42.0))


@dataclass
class VadEvent:
    kind: str  # start | pause | resume | end | abort
    t: float  # monotonic time of the event's reference sample
    audio: np.ndarray | None = None  # utterance audio so far (float32 16 kHz) for start/pause/end
    t_speech_end: float | None = None


@dataclass
class Endpointer:
    threshold: float = 0.5
    endpoint_ms: int = 500
    min_speech_ms: int = 200
    pre_roll_ms: int = 300
    max_utterance_s: float = 20.0
    forced: bool = False  # push-to-talk held: never end on silence
    state: str = "idle"
    _pre: deque = field(default_factory=lambda: deque(maxlen=16))
    _utt: list = field(default_factory=list)
    _speech_frames: int = 0
    _silence_frames: int = 0
    _t_last_voice: float = 0.0

    def __post_init__(self) -> None:
        self._pre = deque(maxlen=max(1, int(self.pre_roll_ms / 32)))

    @property
    def frame_ms(self) -> float:
        return FRAME / 16.0

    def audio(self) -> np.ndarray:
        return np.concatenate(self._utt) if self._utt else np.zeros(0, dtype=np.float32)

    def reset(self) -> None:
        self.state = "idle"
        self._utt = []
        self._speech_frames = self._silence_frames = 0
        self._pre.clear()

    def force_start(self, t: float) -> VadEvent:
        """Push-to-talk pressed."""
        self.forced = True
        self.state = "speech"
        self._utt = list(self._pre)
        self._speech_frames = self._silence_frames = 0
        self._t_last_voice = t
        return VadEvent("start", t)

    def force_end(self, t: float) -> VadEvent | None:
        """Push-to-talk released."""
        self.forced = False
        if self.state == "idle":
            return None
        ev = VadEvent("end", t, self.audio(), t_speech_end=t)
        self.reset()
        return ev

    def push(self, frame: np.ndarray, prob: float, t_end: float) -> list[VadEvent]:
        voiced = prob >= self.threshold
        ev: list[VadEvent] = []
        if self.state == "idle":
            self._pre.append(frame)
            self._speech_frames = self._speech_frames + 1 if voiced else 0
            if self._speech_frames * self.frame_ms >= self.min_speech_ms:
                self.state = "speech"
                self._utt = list(self._pre)
                self._silence_frames = 0
                self._t_last_voice = t_end
                ev.append(VadEvent("start", t_end - len(self._utt) * self.frame_ms / 1000))
            return ev

        self._utt.append(frame)
        if voiced:
            if self.state == "pause":
                ev.append(VadEvent("resume", t_end))
            self.state = "speech"
            self._silence_frames = 0
            self._t_last_voice = t_end
        else:
            self._silence_frames += 1
            if self.state == "speech":
                self.state = "pause"
                ev.append(VadEvent("pause", t_end, self.audio(), t_speech_end=self._t_last_voice))
            if not self.forced and self._silence_frames * self.frame_ms >= self.endpoint_ms:
                ev.append(VadEvent("end", t_end, self.audio(), t_speech_end=self._t_last_voice))
                self.reset()
                return ev
        if len(self._utt) * self.frame_ms / 1000 >= self.max_utterance_s:
            ev.append(VadEvent("end", t_end, self.audio(), t_speech_end=self._t_last_voice))
            self.reset()
        return ev
