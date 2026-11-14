"""Streaming sentence segmenter: LLM tokens in, speakable chunks out (P1).

The first chunk is cut early (at a comma once `first_min` characters are available, or after
`first_max_words` words) so TTS can start as soon as possible; later chunks end at sentence punctuation, or at a comma when they grow
beyond `max_chars`. Decimal points ("3.5"), thousand separators and common abbreviations do not split.
"""
from __future__ import annotations

import re

_ABBR = re.compile(r"(?:TP|Tp|GS|PGS|TS|ThS|BS|KS|Q|P|v\.v|St|Mr|Mrs|Dr|vd|VD)\.$")


class SentenceSegmenter:
    def __init__(self, first_min: int = 18, min_chars: int = 12, max_chars: int = 120, first_max_words: int = 0):
        self.first_min, self.min_chars, self.max_chars = first_min, min_chars, max_chars
        # >0: if the first sentence has no punctuation after this many words, cut at a word boundary
        # (one-sentence answers would otherwise wait for the whole LLM output before TTS starts)
        self.first_max_words = first_max_words
        self.buf = ""
        self.emitted = 0

    def _cut(self) -> int:
        """Index after which buf can be cut, or -1."""
        b = self.buf
        limit = self.first_min if self.emitted == 0 else self.min_chars
        for m in re.finditer(r"[.!?…;:\n]+(?=\s|$)|\n", b):
            end = m.end()
            if end >= len(b) and b[-1] not in "\n":  # need the following char to be sure ("3." -> "3.5")
                continue
            head = b[:end].strip()
            if len(head) < limit:
                continue
            if m.group(0).startswith(".") and _ABBR.search(b[: m.start() + 1]):
                continue  # "TP. HCM", "v.v. ..." (decimals never match: no space after the point)
            return end
        if self.emitted == 0 and self.first_max_words and b.endswith(" "):
            words = b.split()
            if len(words) >= self.first_max_words:
                return len(b)
        # comma split: first chunk (latency) or long chunks
        if self.emitted == 0 or len(b) > self.max_chars:
            for m in re.finditer(r",(?=\s)", b):
                if len(b[: m.end()].strip()) >= (self.first_min if self.emitted == 0 else self.max_chars // 2):
                    return m.end()
        return -1

    def push(self, text: str) -> list[str]:
        self.buf += text
        out = []
        while True:
            i = self._cut()
            if i < 0:
                break
            chunk, self.buf = self.buf[:i].strip(), self.buf[i:]
            if chunk:
                out.append(chunk)
                self.emitted += 1
        return out

    def flush(self) -> list[str]:
        chunk, self.buf = self.buf.strip(), ""
        if chunk:
            self.emitted += 1
            return [chunk]
        return []
