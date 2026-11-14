"""Tiny thread-safe pub/sub used to push pipeline events to the dashboard (and tests)."""
from __future__ import annotations

import queue
import threading
import time
from collections import deque


class EventBus:
    def __init__(self, history: int = 200):
        self._subs: list[queue.Queue] = []
        self._lock = threading.Lock()
        self.history: deque = deque(maxlen=history)

    def publish(self, kind: str, **data) -> None:
        ev = {"type": kind, "ts": time.time(), **data}
        if kind in ("final", "answer_done", "turn"):
            self.history.append(ev)
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(ev)
            except queue.Full:
                pass

    def subscribe(self, maxsize: int = 1000) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)
