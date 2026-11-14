"""Whisper byte-level BPE helpers (CTranslate2 returns token strings, not text)."""
from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _byte_decoder() -> dict[str, int]:
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return {chr(c): b for b, c in zip(bs, cs)}


def is_special(tok: str) -> bool:
    return tok.startswith("<|") and tok.endswith("|>")


def tokens_to_text(tokens: list[str]) -> str:
    dec = _byte_decoder()
    data = bytearray()
    for t in tokens:
        if is_special(t):
            continue
        for ch in t:
            b = dec.get(ch)
            if b is not None:
                data.append(b)
    return data.decode("utf-8", errors="ignore").strip()


def prompt_tokens(language: str = "vi", task: str = "transcribe", timestamps: bool = False) -> list[str]:
    p = ["<|startoftranscript|>", f"<|{language}|>", f"<|{task}|>"]
    if not timestamps:
        p.append("<|notimestamps|>")
    return p
