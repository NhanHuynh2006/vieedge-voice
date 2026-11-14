"""Fast path: questions that have a prepared answer are answered without the LLM (PLAN: "no dead time" for simple turns).

Order (cheapest first, same as the Go2 assistant): go_to -> combo of reflexes -> single reflex -> FAQ dataset (exact, then fuzzy).
A hit returns the sentence to speak and, for robot commands, the list of actions. The spoken sentence is pre-synthesised
(disk cache, so a hit costs a ring-buffer write instead of ~0.5 s of TTS). Anything not matched returns None -> RAG + LLM.

Guard: this assistant also answers general questions, and the Go2 rules match on substrings ("tien" in "tiền Việt Nam là gì").
A question that contains an interrogative marker is therefore never taken by the reflex rules, only by the FAQ dataset.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .combo import ComboMatcher, _strip_tail
from .reflex import ReflexMatcher, norm
from ..safety import SafetyCards

log = logging.getLogger(__name__)

# accent-stripped markers of an information question: such a sentence is not a robot command
_INTERROGATIVE = (" la gi", " la ai", "bao nhieu", "bao lau", "tai sao", "vi sao", "nhu the nao", "the nao", "o dau", "khi nao",
                  "luc nao", "bao gio", "co phai", "ai la", "cai nao", "may gio", "thu may", "bang may", "nghia la",
                  "lam sao", "nam nao", "cho minh hoi", "muon biet", "xin hoi", "nao la", "tot nhat", "co the giup")
_INTERROGATIVE_WORDS = frozenset({"gi", "ai", "sao"})


@dataclass
class Hit:
    say: str
    actions: list = field(default_factory=list)
    intent: str = ""
    source: str = ""  # safety | safety-fallback | goto | combo | reflex | faq | faq-fuzzy


def _tokens(s: str) -> frozenset:
    return frozenset(norm(s).split())


class FastPath:
    def __init__(self, faq_path: str | None = None, fuzzy: float = 0.85, robot_commands: bool = True, locations=None,
                 safety_path: str | None = None):
        self.reflex = ReflexMatcher()
        self.combo = ComboMatcher(locations)
        self.robot_commands = robot_commands
        self.fuzzy = fuzzy
        self.faq: dict[str, dict] = {}
        self._faq_tok: list[tuple[frozenset, dict]] = []
        if faq_path and Path(faq_path).exists():
            for line in open(faq_path, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    self.faq[norm(r["q"])] = r
                    self._faq_tok.append((_tokens(r["q"]), r))
        self.safety = SafetyCards(safety_path) if safety_path and Path(safety_path).exists() else None
        self._cache: dict[str, tuple[np.ndarray, int]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _looks_like_command(t: str) -> bool:
        """Robot commands are imperatives; information questions (interrogatives, yes/no "...không?") are not."""
        words = t.split()
        if t.endswith((" khong", " chua", " a", " ha")) or (" co " in " " + t + " " and " khong" in t):
            return False
        return not (any(m in " " + t for m in _INTERROGATIVE) or _INTERROGATIVE_WORDS & set(words))

    # ---- matching -------------------------------------------------------------------------------------------------------
    def lookup(self, text: str) -> Hit | None:
        text = re.sub(r"[^\w\s]", " ", text)  # the normaliser adds sentence punctuation; the rules match bare words
        t = norm(text)
        if not t:
            return None
        if self.safety is not None:  # emergencies first: a vetted card, or "call 115" instead of a generated guess
            m = self.safety.match(text)
            if m is not None:
                return Hit(m.say, [], m.card.id if m.card else "no-card", "safety" if m.card else "safety-fallback")
        if self.robot_commands and self._looks_like_command(t):
            for src, fn in (("goto", self.combo.resolve_goto), ("combo", self.combo.match), ("reflex", lambda x: self.reflex.match(_strip_tail(norm(x))))):
                r = fn(text)
                if r:
                    return Hit(r["say"], list(r.get("actions", [])), r.get("intent", src), src)
        r = self.faq.get(t)
        if r:
            return Hit(r["say"], list(r.get("actions", [])), r.get("intent", "faq"), "faq")
        words = _tokens(text)
        if self.fuzzy and 2 <= len(words) <= 8:
            best, score = None, 0.0
            for toks, row in self._faq_tok:
                j = len(words & toks) / max(len(words | toks), 1)
                if j > score:
                    best, score = row, j
            if best is not None and score >= self.fuzzy:
                return Hit(best["say"], list(best.get("actions", [])), best.get("intent", "faq"), "faq-fuzzy")
        return None

    # ---- audio cache ----------------------------------------------------------------------------------------------------
    def audio(self, say: str, tts, cache_dir: Path | None = None) -> tuple[np.ndarray, int]:
        """Pre-synthesised audio for `say` (memory, then disk cache keyed by voice + text, else synthesise once)."""
        with self._lock:
            if say in self._cache:
                return self._cache[say]
        f = None
        if cache_dir is not None:
            key = hashlib.sha1(f"{tts.name}|{say}".encode()).hexdigest()[:20]
            f = cache_dir / f"{key}.npz"
            if f.exists():
                z = np.load(f)
                out = (z["audio"].astype(np.float32), int(z["sr"]))
                with self._lock:
                    self._cache[say] = out
                return out
        r = tts.synthesize(say)
        out = (np.asarray(r.audio, dtype=np.float32), int(r.sample_rate))
        if f is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            np.savez(f, audio=out[0].astype(np.float16), sr=out[1])
        with self._lock:
            self._cache[say] = out
        return out

    def prewarm(self, tts, phrases: list[str], cache_dir: Path | None) -> threading.Thread:
        def run():
            for p in phrases:
                try:
                    self.audio(p, tts, cache_dir)
                except Exception as e:  # noqa: BLE001 - a missing phrase just falls back to on-demand synthesis
                    log.warning("fastpath prewarm failed for %r: %s", p, e)
            log.info("fastpath: %d phrases ready", len(self._cache))

        th = threading.Thread(target=run, daemon=True, name="fastpath-prewarm")
        th.start()
        return th
