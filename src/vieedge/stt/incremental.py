"""Incremental ASR (contribution 2, experiment S5).

While the user is still talking, the current utterance is re-transcribed every `interval_ms`
(encoder on the NPU, so it is cheap) -> partial text on the dashboard. The moment VAD sees the
first silent frame ("pause"), a *speculative final* decode starts on the audio so far. If the
speaker does not resume before the endpoint (endpoint_ms of silence), that result is already
done (or nearly) when the endpoint fires, so the latency "user stops talking -> final text" is
hidden inside the endpointing wait instead of being added after it.

Utterances longer than the encoder window (tiny 10 s / base 5 s) are cut at the quietest
20 ms frame near the window end; finished segments are committed and only the tail is re-decoded.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from .base import STT

log = logging.getLogger(__name__)
SR = 16000


@dataclass
class FinalResult:
    text: str
    t_ready: float
    speculative_hit: bool
    decode_ms: float
    n_segments: int
    confidence: float | None = None


class _Job:
    def __init__(self, kind: str, audio: np.ndarray, gen: int, beam: int | None):
        self.kind, self.audio, self.gen, self.beam = kind, audio, gen, beam
        self.done = threading.Event()
        self.text = ""
        self.conf: float | None = None
        self.t_done = 0.0
        self.ms = 0.0


class IncrementalASR:
    def __init__(self, stt: STT, interval_ms: int = 750, speculative_final: bool = True,
                 final_beam: int | None = None, enabled: bool = True,
                 on_partial: Callable[[str], None] | None = None):
        self.stt = stt
        self.interval = interval_ms / 1000
        self.speculative = speculative_final
        self.final_beam = final_beam
        self.enabled = enabled
        self.on_partial = on_partial or (lambda s: None)
        self._gen = 0
        self._lock = threading.Lock()
        self._pending: _Job | None = None
        self._cv = threading.Condition(self._lock)
        self._spec: _Job | None = None
        self._last_partial_t = 0.0
        self._committed_text = ""
        self._committed = 0
        self._segments = 0
        self._seg_confs: list = []
        self._last_conf: float | None = None
        self._stop = False
        self._th = threading.Thread(target=self._worker, daemon=True, name="asr")
        self._th.start()

    # ---------------------------------------------------------------- worker
    def _worker(self) -> None:
        while not self._stop:
            with self._cv:
                while self._pending is None and not self._stop:
                    self._cv.wait(0.1)
                job, self._pending = self._pending, None
            if job is None:
                continue
            if job.gen != self._gen:
                job.done.set()
                continue
            t0 = time.monotonic()
            try:
                job.text = self._transcribe_tail(job.audio, job.beam)
                job.conf = self._last_conf
            except Exception as e:  # never kill the worker
                log.exception("ASR failed: %s", e)
                job.text = ""
            job.t_done = time.monotonic()
            job.ms = (job.t_done - t0) * 1e3
            job.done.set()
            if job.kind == "partial" and job.gen == self._gen and job.text:
                self.on_partial(job.text)

    def _transcribe_tail(self, audio: np.ndarray, beam: int | None) -> str:
        win = int(self.stt.window_s * SR)
        tail = audio[self._committed:]
        committed_text = self._committed_text
        # cut over-long audio into window-sized segments at quiet points
        while len(tail) > win - int(0.5 * SR):
            cut = _quiet_cut(tail, lo=max(SR, win - int(2.5 * SR)), hi=win - int(0.5 * SR))
            seg = self.stt.transcribe(tail[:cut], beam_size=self.final_beam)
            seg_text = seg.text
            self._seg_confs.append(seg.confidence)
            committed_text = (committed_text + " " + seg_text).strip()
            # a cut segment is final whichever job produced it
            self._committed_text = committed_text
            self._committed += cut
            self._segments += 1
            tail = tail[cut:]
        if len(tail) < int(0.2 * SR):
            self._last_conf = _worst(self._seg_confs)
            return committed_text
        res = self.stt.transcribe(tail, beam_size=beam)
        self._last_conf = _worst([*self._seg_confs, res.confidence])
        return (committed_text + " " + res.text).strip()

    def _submit(self, kind: str, audio: np.ndarray, beam: int | None) -> _Job:
        job = _Job(kind, audio, self._gen, beam)
        with self._cv:
            if self._pending is not None:
                self._pending.done.set()  # superseded
            self._pending = job
            self._cv.notify()
        return job

    # ---------------------------------------------------------------- events
    def start(self) -> None:
        self._gen += 1
        self._spec = None
        self._committed_text = ""
        self._committed = 0
        self._segments = 0
        self._seg_confs = []
        self._last_partial_t = time.monotonic()

    def update(self, audio: np.ndarray) -> None:
        """Called with the utterance audio so far (every VAD frame); throttled to interval_ms."""
        if not self.enabled:
            return
        t = time.monotonic()
        if t - self._last_partial_t >= self.interval and len(audio) > int(0.5 * SR):
            self._last_partial_t = t
            with self._lock:
                busy = self._pending is not None
            if not busy:
                self._submit("partial", audio.copy(), None)

    def pause(self, audio: np.ndarray) -> None:
        if self.enabled and self.speculative:
            self._spec = self._submit("spec", audio.copy(), self.final_beam)

    def resume(self) -> None:
        self._spec = None  # speculative result no longer valid

    def cancel(self) -> None:
        self._gen += 1
        self._spec = None

    def finish(self, audio: np.ndarray) -> FinalResult:
        spec = self._spec
        t0 = time.monotonic()
        if spec is not None and spec.gen == self._gen:
            spec.done.wait()
            if spec.text or len(audio) < SR // 2:
                self._gen += 1
                return FinalResult(spec.text, spec.t_done, True, spec.ms, self._segments + 1, spec.conf)
        job = self._submit("final", audio.copy(), self.final_beam)
        job.done.wait()
        self._gen += 1
        return FinalResult(job.text, job.t_done, False, (time.monotonic() - t0) * 1e3, self._segments + 1, job.conf)

    def close(self) -> None:
        self._stop = True


def _quiet_cut(x: np.ndarray, lo: int, hi: int, frame: int = 320) -> int:
    """Index of the lowest-energy 20 ms frame in x[lo:hi]."""
    hi = min(hi, len(x))
    if hi - lo < frame:
        return hi
    seg = x[lo:hi]
    n = len(seg) // frame
    e = (seg[: n * frame].reshape(n, frame) ** 2).mean(axis=1)
    return lo + int(np.argmin(e)) * frame + frame // 2


def transcribe_long(stt: STT, audio: np.ndarray, beam_size: int | None = None) -> tuple[str, list]:
    """Offline helper (benchmarks): same segmentation rule as the live path for audio > window."""
    win = int(stt.window_s * SR)
    texts, results = [], []
    while len(audio) > win - int(0.5 * SR):
        cut = _quiet_cut(audio, lo=max(SR, win - int(2.5 * SR)), hi=win - int(0.5 * SR))
        r = stt.transcribe(audio[:cut], beam_size=beam_size)
        texts.append(r.text)
        results.append(r)
        audio = audio[cut:]
    if len(audio) >= int(0.2 * SR) or not results:
        r = stt.transcribe(audio, beam_size=beam_size)
        texts.append(r.text)
        results.append(r)
    return " ".join(t for t in texts if t).strip(), results


def _worst(confs: list) -> float | None:
    vals = [c for c in confs if c is not None]
    return min(vals) if vals else None
