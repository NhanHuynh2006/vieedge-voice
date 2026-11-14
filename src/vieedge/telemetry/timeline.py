"""Per-turn latency timeline (monotonic clock, PLAN §9).

Stages: speech_start -> speech_end (last voiced frame, VAD) -> endpoint -> stt_final ->
llm_request -> llm_first_token -> first_chunk (first sentence ready) -> tts_first_done ->
first_audio (first sample reaches the speaker) -> llm_done -> audio_done.
Every finished turn is appended as one JSON line to <results>/turns/<session>.jsonl.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

STAGES = ["speech_start", "speech_end", "endpoint", "stt_final", "llm_request", "llm_first_token",
          "ack_audio", "first_chunk", "tts_first_done", "answer_audio", "first_audio", "llm_done", "audio_done"]


@dataclass
class Turn:
    turn_id: int
    t: dict = field(default_factory=dict)
    question: str = ""
    answer: str = ""
    meta: dict = field(default_factory=dict)

    def mark(self, stage: str, t: float | None = None) -> None:
        if stage not in self.t:
            self.t[stage] = t if t is not None else time.monotonic()

    def rel_ms(self, ref: str = "speech_end") -> dict:
        t0 = self.t.get(ref)
        if t0 is None:
            return {}
        return {k: round((v - t0) * 1e3, 1) for k, v in self.t.items()}

    def metrics(self) -> dict:
        t = self.t

        def d(a, b):
            return round((t[b] - t[a]) * 1e3, 1) if a in t and b in t else None

        return {
            "stt_after_speech_ms": d("speech_end", "stt_final"),
            "endpoint_wait_ms": d("speech_end", "endpoint"),
            "stt_after_endpoint_ms": d("endpoint", "stt_final"),
            "ttft_ms": d("llm_request", "llm_first_token"),
            "first_chunk_ms": d("llm_first_token", "first_chunk"),
            "tts_first_ms": d("first_chunk", "tts_first_done"),
            "first_audio_ms": d("speech_end", "first_audio"),  # the headline number (with pipeline.ack: the acknowledgement)
            "answer_audio_ms": d("speech_end", "answer_audio"),  # first sample of the real answer (== first_audio without ack)
            "llm_total_ms": d("llm_request", "llm_done"),
            "turn_total_ms": d("speech_end", "audio_done"),
        }

    def to_json(self) -> dict:
        return {"turn_id": self.turn_id, "question": self.question, "answer": self.answer,
                "t_rel_ms": self.rel_ms(), "metrics": self.metrics(), "meta": self.meta, "t_abs": self.t}


class TurnLog:
    def __init__(self, directory: Path, session: str | None = None):
        directory.mkdir(parents=True, exist_ok=True)
        self.session = session or time.strftime("%Y%m%d-%H%M%S")
        self.path = directory / f"{self.session}.jsonl"
        self._lock = threading.Lock()
        self._n = 0

    def new_turn(self, **meta) -> Turn:
        self._n += 1
        return Turn(self._n, meta=dict(meta))

    def write(self, turn: Turn) -> dict:
        rec = turn.to_json()
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec


def asdict_turn(t: Turn) -> dict:
    return asdict(t)
