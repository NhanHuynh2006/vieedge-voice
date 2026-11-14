"""Single-producer / single-consumer int16 ring buffer in POSIX shared memory.

Used between the real-time audio process (pinned to the isolated core, SCHED_FIFO) and the
main process, so ALSA I/O never waits on the main process' GIL. Indices are monotonically
increasing 64-bit sample counters (aligned 8-byte stores are atomic on arm64/x86-64).
"""
from __future__ import annotations

import time
from multiprocessing import shared_memory

import numpy as np

# header layout (float64/int64 slots)
_W, _R, _T_LAST, _FLUSH, _XRUN, _AUDIBLE_END, _FIRST_T, _EPOCH, _OVERRUN, _N_HDR = range(10)


class SharedRing:
    def __init__(self, capacity: int, name: str | None = None, create: bool = True):
        self.capacity = int(capacity)
        hdr_bytes = _N_HDR * 8
        size = hdr_bytes + self.capacity * 2
        if create:
            self.shm = shared_memory.SharedMemory(create=True, size=size, name=name)
        else:
            self.shm = shared_memory.SharedMemory(name=name)
        self._owner = create
        self.hdr_i = np.ndarray((_N_HDR,), dtype=np.int64, buffer=self.shm.buf[:hdr_bytes])
        self.hdr_f = np.ndarray((_N_HDR,), dtype=np.float64, buffer=self.shm.buf[:hdr_bytes])
        self.buf = np.ndarray((self.capacity,), dtype=np.int16, buffer=self.shm.buf[hdr_bytes:size])
        if create:
            self.hdr_i[:] = 0

    @property
    def name(self) -> str:
        return self.shm.name

    # ---- indices -------------------------------------------------------
    @property
    def widx(self) -> int:
        return int(self.hdr_i[_W])

    @property
    def ridx(self) -> int:
        return int(self.hdr_i[_R])

    def available(self) -> int:
        return self.widx - self.ridx

    def free(self) -> int:
        return self.capacity - self.available()

    # ---- producer ------------------------------------------------------
    def write(self, x: np.ndarray, t_end: float | None = None) -> int:
        """Write int16 samples; on overflow the oldest data is dropped (reader lags)."""
        x = np.asarray(x, dtype=np.int16).ravel()
        n = len(x)
        if n == 0:
            return 0
        if n > self.capacity:
            x = x[-self.capacity:]
            n = self.capacity
        w = self.widx
        start = w % self.capacity
        first = min(n, self.capacity - start)
        self.buf[start:start + first] = x[:first]
        if first < n:
            self.buf[: n - first] = x[first:]
        if t_end is not None:
            self.hdr_f[_T_LAST] = t_end
        self.hdr_i[_W] = w + n
        if self.available() > self.capacity:  # reader too slow: skip ahead
            self.hdr_i[_OVERRUN] += 1
            self.hdr_i[_R] = self.widx - self.capacity
        return n

    # ---- consumer ------------------------------------------------------
    def read(self, max_n: int | None = None) -> tuple[np.ndarray, int]:
        """Return (samples, index_of_first_sample)."""
        r, w = self.ridx, self.widx
        n = w - r
        if max_n is not None:
            n = min(n, max_n)
        if n <= 0:
            return np.zeros(0, dtype=np.int16), r
        start = r % self.capacity
        first = min(n, self.capacity - start)
        out = np.empty(n, dtype=np.int16)
        out[:first] = self.buf[start:start + first]
        if first < n:
            out[first:] = self.buf[: n - first]
        self.hdr_i[_R] = r + n
        return out, r

    def drop_all(self) -> None:
        self.hdr_i[_R] = self.widx

    # ---- shared status fields ------------------------------------------
    @property
    def t_last(self) -> float:
        return float(self.hdr_f[_T_LAST])

    def request_flush(self) -> None:
        self.hdr_i[_FLUSH] += 1

    @property
    def flush_counter(self) -> int:
        return int(self.hdr_i[_FLUSH])

    def add_xrun(self) -> None:
        self.hdr_i[_XRUN] += 1

    @property
    def xruns(self) -> int:
        return int(self.hdr_i[_XRUN])

    @property
    def overruns(self) -> int:
        return int(self.hdr_i[_OVERRUN])

    @property
    def audible_end(self) -> float:
        """Monotonic time at which the last non-silent sample handed to the device will have played."""
        return float(self.hdr_f[_AUDIBLE_END])

    @audible_end.setter
    def audible_end(self, t: float) -> None:
        self.hdr_f[_AUDIBLE_END] = t

    @property
    def first_audio_t(self) -> float:
        return float(self.hdr_f[_FIRST_T])

    @first_audio_t.setter
    def first_audio_t(self, t: float) -> None:
        self.hdr_f[_FIRST_T] = t

    @property
    def epoch(self) -> int:
        return int(self.hdr_i[_EPOCH])

    def bump_epoch(self) -> None:
        self.hdr_i[_EPOCH] += 1

    def close(self) -> None:
        try:
            self.shm.close()
            if self._owner:
                self.shm.unlink()
        except FileNotFoundError:
            pass


def now() -> float:
    return time.monotonic()
