"""Real-time audio process.

A separate process (not a thread) owns the sound card: pinned to the isolated core
(`audio.rt_core`, core 3 in O4), SCHED_FIFO `audio.rt_priority`, mlockall. It moves 20 ms
periods between ALSA and two shared-memory rings, so heavy work in the main process
(STT decoder, TTS, LLM HTTP streaming, Python GIL) can never starve the sound card.

Playback is continuous: when there is nothing to say, silence is written. An underrun is
therefore a real deadline miss, and is counted as an xrun (PLAN §6, O0–O4 "xrun/giờ").
"""
from __future__ import annotations

import collections
import logging
import multiprocessing as mp
import os
import queue
import threading
import time
import wave
from pathlib import Path

import numpy as np

from ..rt import mlockall, pin_current_thread, set_fifo
from .ring import SharedRing

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------------- backends
class _Backend:
    def __init__(self, cfg: dict, cap_rate: int, pb_rate: int):
        self.cfg, self.cap_rate, self.pb_rate = cfg, cap_rate, pb_rate
        self.cap_period = int(cap_rate * cfg["period_ms"] / 1000)
        self.pb_period = int(pb_rate * cfg["period_ms"] / 1000)

    def open(self) -> None: ...
    def read(self) -> tuple[np.ndarray, bool]: raise NotImplementedError  # (int16 period, overrun)
    def write(self, x: np.ndarray) -> bool: raise NotImplementedError  # underrun?
    def latency_s(self) -> float: return self.cfg["periods"] * self.cfg["period_ms"] / 1000
    def control(self, msg: tuple) -> None: ...
    def close(self) -> None: ...


class AlsaBackend(_Backend):
    def open(self) -> None:
        import alsaaudio

        self.aa = alsaaudio
        periods = self.cfg["periods"]
        self.cap = alsaaudio.PCM(type=alsaaudio.PCM_CAPTURE, mode=alsaaudio.PCM_NORMAL,
                                 device=self.cfg["capture_device"], channels=1, rate=self.cap_rate,
                                 format=alsaaudio.PCM_FORMAT_S16_LE, periodsize=self.cap_period, periods=periods)
        self.pb = alsaaudio.PCM(type=alsaaudio.PCM_PLAYBACK, mode=alsaaudio.PCM_NORMAL,
                                device=self.cfg["playback_device"], channels=1, rate=self.pb_rate,
                                format=alsaaudio.PCM_FORMAT_S16_LE, periodsize=self.pb_period, periods=periods)
        self._pending = np.zeros(0, dtype=np.int16)

    def read(self) -> tuple[np.ndarray, bool]:
        n, data = self.cap.read()
        if n < 0:  # -EPIPE: capture overrun
            return np.zeros(self.cap_period, dtype=np.int16), True
        return np.frombuffer(data, dtype=np.int16).copy(), False

    def write(self, x: np.ndarray) -> bool:
        try:
            n = self.pb.write(x.astype(np.int16).tobytes())
            return n is not None and n < 0
        except self.aa.ALSAAudioError:
            return True

    def close(self) -> None:
        for p in (getattr(self, "cap", None), getattr(self, "pb", None)):
            try:
                p and p.close()
            except Exception:
                pass


class SoundDeviceBackend(_Backend):
    """Laptop development backend (PortAudio, blocking streams)."""

    def open(self) -> None:
        import sounddevice as sd

        dev_in = None if self.cfg["capture_device"] in (None, "default") else self.cfg["capture_device"]
        dev_out = None if self.cfg["playback_device"] in (None, "default") else self.cfg["playback_device"]
        lat = self.latency_s()
        self.cap = sd.RawInputStream(samplerate=self.cap_rate, channels=1, dtype="int16",
                                     blocksize=self.cap_period, device=dev_in, latency=lat)
        self.pb = sd.RawOutputStream(samplerate=self.pb_rate, channels=1, dtype="int16",
                                     blocksize=self.pb_period, device=dev_out, latency=lat)
        self.cap.start()
        self.pb.start()

    def read(self) -> tuple[np.ndarray, bool]:
        data, overflowed = self.cap.read(self.cap_period)
        return np.frombuffer(bytes(data), dtype=np.int16).copy(), bool(overflowed)

    def write(self, x: np.ndarray) -> bool:
        return bool(self.pb.write(x.astype(np.int16).tobytes()))

    def close(self) -> None:
        for s in (getattr(self, "cap", None), getattr(self, "pb", None)):
            try:
                s and (s.stop(), s.close())
            except Exception:
                pass


class FileBackend(_Backend):
    """Benchmarks: plays injected WAV files into the 'microphone' in real time (optionally over
    background noise at a given SNR) and records what the assistant says to a WAV file."""

    def open(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._cur = np.zeros(0, dtype=np.int16)
        self._noise = None
        self._noise_pos = 0
        self._noise_gain = 0.0
        self._t_cap = time.monotonic()
        self._t_pb = time.monotonic()
        self._out = None
        out = self.cfg.get("record_playback")
        if out:
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            self._out = wave.open(str(out), "wb")
            self._out.setnchannels(1)
            self._out.setsampwidth(2)
            self._out.setframerate(self.pb_rate)

    def control(self, msg: tuple) -> None:
        if msg[0] == "inject":
            self._q.put(_load_wav_16k(msg[1]))
        elif msg[0] == "noise":
            path, level_db = msg[1], msg[2]
            self._noise = _load_wav_16k(path) if path else None
            self._noise_gain = 10 ** (level_db / 20) if path else 0.0
        elif msg[0] == "clear":
            self._q = queue.Queue()
            self._cur = np.zeros(0, dtype=np.int16)

    def _sleep_until(self, t: float) -> float:
        d = t - time.monotonic()
        if d > 0:
            time.sleep(d)
        return t

    def read(self) -> tuple[np.ndarray, bool]:
        n = self.cap_period
        self._t_cap = self._sleep_until(self._t_cap + n / self.cap_rate)
        out = np.zeros(n, dtype=np.float32)
        filled = 0
        while filled < n:
            if len(self._cur) == 0:
                try:
                    self._cur = self._q.get_nowait()
                except queue.Empty:
                    break
            k = min(n - filled, len(self._cur))
            out[filled:filled + k] = self._cur[:k]
            self._cur = self._cur[k:]
            filled += k
        if self._noise is not None and len(self._noise):
            idx = (np.arange(n) + self._noise_pos) % len(self._noise)
            out += self._noise[idx].astype(np.float32) * self._noise_gain
            self._noise_pos = int((self._noise_pos + n) % len(self._noise))
        return np.clip(out, -32768, 32767).astype(np.int16), False

    def write(self, x: np.ndarray) -> bool:
        self._t_pb = self._sleep_until(self._t_pb + len(x) / self.pb_rate)
        if self._out is not None:
            self._out.writeframes(x.astype(np.int16).tobytes())
        return False

    def close(self) -> None:
        if self._out is not None:
            self._out.close()


class NullBackend(FileBackend):
    pass


class RemoteBackend(_Backend):
    """The phone is the microphone and the speaker (browser over WebSocket, `web/server.py` `/audio`).

    The web server lives in the main process, so audio crosses the process boundary on queues: 16 kHz int16 microphone chunks arrive as
    ("mic", bytes) control messages; what the assistant says leaves through `out_q` as raw int16 bytes at the playback rate. Both sides
    are paced to the wall clock like a sound card: a late microphone chunk reads as silence, a burst is trimmed to a short backlog.
    """

    max_backlog_s = 0.25

    def open(self) -> None:
        self._chunks: collections.deque = collections.deque()
        self._cur = np.zeros(0, dtype=np.int16)
        self._t_cap = time.monotonic()
        self._t_pb = time.monotonic()
        self.out_q = None  # set by _audio_main

    def latency_s(self) -> float:
        # period buffering here + network + the phone's own output buffer (it schedules ~60 ms ahead)
        return float(self.cfg.get("remote_latency_ms", 150)) / 1000

    def control(self, msg: tuple) -> None:
        if msg[0] == "mic":
            self._chunks.append(np.frombuffer(msg[1], dtype=np.int16))
            while sum(len(c) for c in self._chunks) > self.max_backlog_s * self.cap_rate:  # phone clock ahead: keep the newest
                self._chunks.popleft()

    def _sleep_until(self, t: float) -> float:
        d = t - time.monotonic()
        if d > 0:
            time.sleep(d)
        return t

    def read(self) -> tuple[np.ndarray, bool]:
        n = self.cap_period
        self._t_cap = self._sleep_until(self._t_cap + n / self.cap_rate)
        if time.monotonic() - self._t_cap > 1.0:  # the process stalled: do not replay a backlog of time
            self._t_cap = time.monotonic()
        out = np.zeros(n, dtype=np.int16)
        filled = 0
        while filled < n:
            if len(self._cur) == 0:
                try:
                    self._cur = self._chunks.popleft()
                except IndexError:
                    break
            k = min(n - filled, len(self._cur))
            out[filled:filled + k] = self._cur[:k]
            self._cur = self._cur[k:]
            filled += k
        return out, False

    def write(self, x: np.ndarray) -> bool:
        self._t_pb = self._sleep_until(self._t_pb + len(x) / self.pb_rate)
        if time.monotonic() - self._t_pb > 1.0:
            self._t_pb = time.monotonic()
        if self.out_q is not None:
            try:
                self.out_q.put_nowait(x.astype(np.int16).tobytes())
            except queue.Full:
                pass  # nobody is draining (no phone connected): drop
        return False


def _load_wav_16k(path: str) -> np.ndarray:
    try:
        import soundfile as sf

        x, sr = sf.read(path, dtype="float32", always_2d=True)
        x = x.mean(axis=1)
    except ImportError:  # device image has no soundfile: 16-bit PCM WAV via the standard library
        with wave.open(path) as w:
            sr, ch = w.getframerate(), w.getnchannels()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
            if ch > 1:
                x = x.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        from .resample import resample

        x = resample(x, sr, 16000)
    return np.clip(x * 32767, -32768, 32767).astype(np.int16)


def resolve_backend(cfg: dict, cards_path: str = "/proc/asound/cards") -> str:
    """`audio.backend: auto` -> ALSA when a USB sound card is plugged in, otherwise the phone (remote) is mic and speaker."""
    b = cfg.get("backend", "alsa")
    if b != "auto":
        return b
    try:
        txt = Path(cards_path).read_text()
    except OSError:
        return "remote"
    return "alsa" if any(k in txt for k in ("USB-Audio", "USB Audio", "usb")) else "remote"


BACKENDS = {"alsa": AlsaBackend, "sounddevice": SoundDeviceBackend, "file": FileBackend, "null": NullBackend, "remote": RemoteBackend}


# ----------------------------------------------------------------------------- audio process
def _audio_main(cfg: dict, cap_name: str, pb_name: str, cap_cap: int, pb_cap: int, cap_rate: int, pb_rate: int,
                ctrl: mp.Queue, status: mp.Queue, audio_out: mp.Queue | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s audio %(levelname)s %(message)s")
    core = cfg.get("rt_core")
    if core is not None and core < (os.cpu_count() or 1):
        pin_current_thread({int(core)})
    prio = int(cfg.get("rt_priority") or 0)  # 0 -> SCHED_OTHER (O0-O3), 80 -> SCHED_FIFO (O4)
    fifo = set_fifo(prio) if prio > 0 else False
    locked = mlockall()

    cap = SharedRing(cap_cap, name=cap_name, create=False)
    pb = SharedRing(pb_cap, name=pb_name, create=False)

    be = BACKENDS[cfg["backend"]](cfg, cap_rate, pb_rate)
    be.open()
    if cfg["backend"] == "remote":
        be.out_q = audio_out
    latency = be.latency_s()
    status.put({"ready": True, "fifo": fifo, "mlock": locked, "core": core, "latency_s": latency,
                "pid": os.getpid(), "backend": cfg["backend"]})
    stop = threading.Event()

    def capture_loop() -> None:
        if fifo:
            set_fifo(prio)
        while not stop.is_set():
            x, overrun = be.read()
            if overrun:
                cap.add_xrun()
            cap.write(x, t_end=time.monotonic())

    def playback_loop() -> None:
        if fifo:
            set_fifo(prio - 1)
        last_flush = pb.flush_counter
        period = be.pb_period
        silence = np.zeros(period, dtype=np.int16)
        while not stop.is_set():
            fc = pb.flush_counter
            if fc != last_flush:
                pb.drop_all()
                last_flush = fc
            x, _ = pb.read(period)
            if len(x):
                t = time.monotonic()
                if pb.first_audio_t < 0:
                    pb.first_audio_t = t + latency  # when the first sample reaches the speaker
                pb.audible_end = t + latency + period / pb_rate
                if len(x) < period:
                    x = np.concatenate([x, silence[: period - len(x)]])
            else:
                x = silence
            if be.write(x):
                pb.add_xrun()

    th = [threading.Thread(target=capture_loop, daemon=True, name="audio-cap"),
          threading.Thread(target=playback_loop, daemon=True, name="audio-pb")]
    for t in th:
        t.start()
    try:
        while True:
            msg = ctrl.get()
            if msg is None or msg[0] == "stop":
                break
            be.control(msg)
    finally:
        stop.set()
        for t in th:
            t.join(timeout=1.0)
        be.close()
        cap.close()
        pb.close()


class AudioEngine:
    """Main-process handle: owns the shared rings and the audio process."""

    def __init__(self, cfg: dict, playback_rate: int):
        self.cfg = dict(cfg)
        self.cap_rate = int(cfg["sample_rate"])
        self.pb_rate = int(cfg.get("playback_rate") or playback_rate)
        secs = int(cfg.get("ring_seconds", 30))
        self.cap = SharedRing(self.cap_rate * secs)
        self.pb = SharedRing(self.pb_rate * secs)
        self.pb.first_audio_t = 0.0
        ctx = mp.get_context("spawn")
        self._ctrl: mp.Queue = ctx.Queue()
        self._status: mp.Queue = ctx.Queue()
        self.audio_out: mp.Queue = ctx.Queue(maxsize=200)  # remote backend: speech bound for the phone
        self.proc = ctx.Process(target=_audio_main, name="vieedge-audio", daemon=True,
                                args=(self.cfg, self.cap.name, self.pb.name, self.cap.capacity, self.pb.capacity,
                                      self.cap_rate, self.pb_rate,
                                      self._ctrl, self._status, self.audio_out))
        self.info: dict = {}

    def start(self, timeout: float = 45.0) -> dict:
        self.proc.start()
        self.info = self._status.get(timeout=timeout)
        log.info("audio process ready: %s", self.info)
        return self.info

    # capture side ------------------------------------------------------
    def read(self, max_n: int | None = None) -> tuple[np.ndarray, int]:
        return self.cap.read(max_n)

    def sample_time(self, idx: int) -> float:
        """Monotonic capture time of absolute capture sample `idx`."""
        return self.cap.t_last - (self.cap.widx - idx) / self.cap_rate

    # playback side -----------------------------------------------------
    def arm_first_audio(self) -> None:
        self.pb.first_audio_t = -1.0

    def first_audio_time(self) -> float | None:
        t = self.pb.first_audio_t
        return t if t > 0 else None

    def play(self, pcm: np.ndarray) -> None:
        """Queue int16 PCM at pb_rate; blocks while the ring is full (back-pressure)."""
        pcm = np.asarray(pcm, dtype=np.int16)
        while len(pcm):
            free = self.pb.free()
            if free <= 0:
                time.sleep(0.01)
                continue
            k = min(free, len(pcm))
            self.pb.write(pcm[:k])
            pcm = pcm[k:]

    def flush_playback(self) -> None:
        self.pb.request_flush()
        self.pb.drop_all()

    def playback_pending_s(self) -> float:
        return self.pb.available() / self.pb_rate

    def is_audible(self, t: float | None = None) -> bool:
        return (t or time.monotonic()) < self.pb.audible_end or self.pb.available() > 0

    def xruns(self) -> dict:
        return {"capture": self.cap.xruns, "playback": self.pb.xruns, "ring_overruns": self.cap.overruns}

    # phone as microphone / speaker (remote backend) --------------------
    @property
    def remote(self) -> bool:
        return self.cfg["backend"] == "remote"

    def remote_in(self, pcm16k: bytes) -> None:
        """Microphone samples from the phone (int16 mono at `sample_rate`)."""
        self._ctrl.put(("mic", pcm16k))

    # benchmark helpers (file backend) ------------------------------------
    def inject(self, wav_path: str) -> None:
        self._ctrl.put(("inject", str(wav_path)))

    def set_noise(self, wav_path: str | None, level_db: float = -20.0) -> None:
        self._ctrl.put(("noise", wav_path, level_db))

    def stop(self) -> None:
        try:
            self._ctrl.put(("stop",))
            self.proc.join(timeout=3)
        finally:
            if self.proc.is_alive():
                self.proc.terminate()
            self.cap.close()
            self.pb.close()
