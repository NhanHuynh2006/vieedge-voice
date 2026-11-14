"""Text utilities: question clean-up after ASR, and the normaliser used for WER scoring."""
from __future__ import annotations

import re
import unicodedata

# Typical Whisper hallucinations on silence/noise (YouTube outros etc.)
HALLUCINATIONS = [
    r"hãy subscribe.*", r"đăng ký kênh.*", r"cảm ơn các bạn đã (theo dõi|xem).*", r"hẹn gặp lại các bạn.*",
    r"nhớ like và share.*", r"subtitles? by.*", r"thanks for watching.*", r"ghiền mì gõ.*",
]
_HALL = re.compile(r"^(" + "|".join(HALLUCINATIONS) + r")$", re.I)
QUESTION_WORDS = ("gì", "sao", "nào", "không", "chưa", "bao nhiêu", "bao giờ", "ở đâu", "ai", "thế nào", "như nào",
                  "mấy", "à", "hả", "nhỉ", "chứ", "được không", "có phải")


def collapse_repeats(text: str, max_ngram: int = 6) -> str:
    """'xin chào xin chào xin chào' -> 'xin chào' (decoder loops)."""
    words = text.split()
    for n in range(max_ngram, 0, -1):
        i = 0
        out: list[str] = []
        while i < len(words):
            out.append(words[i])
            i += 1
            if len(out) >= 2 * n and out[-n:] == out[-2 * n:-n]:
                del out[-n:]
        words = out
    return " ".join(words)


def normalize_question(text: str) -> str:
    t = unicodedata.normalize("NFC", text or "").strip()
    t = re.sub(r"\s+", " ", t)
    t = collapse_repeats(t)
    if not t or _HALL.match(t.strip(" .!?")):
        return ""
    t = t[0].upper() + t[1:]
    if not re.search(r"[.!?]$", t):
        low = t.lower()
        t += "?" if any(low.endswith(w) or f" {w} " in f" {low} " for w in QUESTION_WORDS) else "."
    return t


def wer_normalize(text: str) -> str:
    """Lower-case, NFC, strip punctuation — applied to both reference and hypothesis before WER."""
    t = unicodedata.normalize("NFC", text).lower()
    t = re.sub(r"[^\w\sÀ-ỹ]", " ", t)
    t = t.replace("_", " ")
    return re.sub(r"\s+", " ", t).strip()
