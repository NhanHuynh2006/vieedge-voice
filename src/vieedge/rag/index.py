"""Retrieval-augmented generation, offline (PLAN: reduce hallucination of the 0.8-2B LLM; Lancaster 2025, arXiv 2506.21568).

Why SQLite FTS5: disk-based (low RAM on the Pi), ~10 ms queries, BM25 ranking built in, no embedding model on the CPU
that is busy with the LLM. `remove_diacritics 2` makes matching tolerant to the tone/vowel errors the speech recogniser
makes ("tây sơn" ~ "tay son"); the title column is weighted so named entities dominate. Query = content syllables (stop
syllables removed) + adjacent-syllable phrases (word-like units: "hồ gươm"), all OR-ed and ranked by BM25.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from pathlib import Path

_TOKEN = re.compile(r"[0-9a-zà-ỹđ]+", re.I)

# Syllables that carry no topic (question words, function words, fillers) — never used as query terms on their own.
STOP = set("""
là của và có không được cho với trong một những các này đó khi thì mà bị đã sẽ đang cũng như để từ ra vào lên xuống
nên rồi vậy nhỉ nhé ạ ơi bạn mình tôi em anh chị hỏi gì sao nào ai đâu bao nhiêu mấy thế làm hay hoặc nhưng nếu
vì tại do bởi theo về trên dưới giữa sau trước lại còn chỉ rất quá lắm hơn nhất đều cả mọi mỗi nữa luôn thật
biết nói cần muốn phải thể nghĩa giúp xin vui lòng giải thích cho_biết tại_sao vì_sao thế_nào như_thế_nào
""".split())


def strip_marks(s: str) -> str:
    # FTS5 remove_diacritics leaves "đ" untouched, so the query must too (mapping it to "d" would never match the index)
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn"))


def syllables(text: str) -> list[str]:
    return _TOKEN.findall(unicodedata.normalize("NFC", text.lower()))


def query_terms(question: str) -> tuple[list[str], list[str]]:
    """(content syllables, adjacent content pairs), diacritics stripped (the index is diacritic-insensitive).
    Stop-word status is decided on the toned syllable: "nói" is a stop word, "nội" (Hà Nội) is not."""
    raw = syllables(question)
    keep = [strip_marks(t) for t in raw]
    is_stop = [t in STOP or len(t) < 2 for t in raw]
    content = [k for k, st in zip(keep, is_stop) if not st]
    pairs = [f"{keep[i]} {keep[i + 1]}" for i in range(len(keep) - 1) if not is_stop[i] and not is_stop[i + 1]]
    return list(dict.fromkeys(content)), list(dict.fromkeys(pairs))


def fts_query(question: str, doc_freq: dict[str, int] | None = None, n_rows: int = 0, max_terms: int = 6,
              max_df_frac: float = 0.02) -> str | None:
    """OR of the rarest content syllables and of adjacent-syllable phrases. With document frequencies, syllables present
    in more than `max_df_frac` of all chunks are dropped (they only add postings to scan, not signal) and at most
    `max_terms` of the rarest remain — this keeps queries around 10-30 ms instead of hundreds."""
    content, pairs = query_terms(question)
    if doc_freq is not None and n_rows:
        rare = [t for t in content if 0 < doc_freq.get(t, 0) <= max_df_frac * n_rows]
        content = sorted(rare or content, key=lambda t: doc_freq.get(t, 0))[:max_terms]
        pairs = [p for p in pairs if all(t in content or doc_freq.get(t, 0) <= max_df_frac * n_rows for t in p.split())][:max_terms]
    if not content:
        return None
    return " OR ".join([f'"{p}"' for p in pairs] + [f'"{t}"' for t in content])


_ASK_YEAR = re.compile(r"\b(năm nào|khi nào|bao giờ|hồi nào|thời gian nào|ngày nào|thế kỷ nào)\b", re.I)
_ASK_NUM = re.compile(r"\b(bao nhiêu|bao xa|bao lâu|bao nhiêu tuổi|cao|dài|rộng|nặng|sâu|diện tích|dân số|mấy)\b", re.I)
_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-9]{2}|[0-9]{1,2}\s+tháng\s+[0-9]{1,2})\b")
_NUM = re.compile(r"\b[0-9][0-9.,]*\s?(km|m|kg|nghìn|triệu|tỷ|%|mét|dặm|năm|tuổi|người)\b", re.I)


def answer_bonus(question: str, text: str) -> float:
    """Chunks that contain the kind of answer being asked for (a date, a quantity) are worth more."""
    b = 0.0
    if _ASK_YEAR.search(question) and _YEAR.search(text):
        b += 40.0
    if _ASK_NUM.search(question) and _NUM.search(text):
        b += 40.0
    return b


def add_title_index(db: sqlite3.Connection) -> None:
    """Per-article chunk rowid ranges + an FTS table over titles (chunk rowids are contiguous per article)."""
    db.execute("CREATE TABLE IF NOT EXISTS art AS SELECT title, min(rowid) lo, max(rowid) hi FROM chunks GROUP BY title")
    db.execute("CREATE INDEX IF NOT EXISTS art_title ON art(title)")
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS tfts USING fts5(title, tokenize='unicode61 remove_diacritics 2')")
    if not db.execute("SELECT 1 FROM tfts LIMIT 1").fetchone():
        db.execute("INSERT INTO tfts(rowid, title) SELECT rowid, title FROM art")
    db.commit()


class KnowledgeBase:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self.db.execute("PRAGMA query_only=1")
        self.db.execute("PRAGMA mmap_size=268435456")
        try:
            self.n_rows = self.db.execute("SELECT count(*) FROM chunks_docsize").fetchone()[0]
            self._has_vocab = bool(self.db.execute("SELECT 1 FROM sqlite_master WHERE name='vocab'").fetchone())
        except sqlite3.Error:
            self.n_rows, self._has_vocab = 0, False

    def _doc_freq(self, terms: list[str]) -> dict[str, int]:
        if not self._has_vocab or not terms:
            return {}
        qs = ",".join("?" * len(terms))
        return dict(self.db.execute(f"SELECT term, doc FROM vocab WHERE term IN ({qs})", terms).fetchall())

    def _title_candidates(self, question: str, max_titles: int = 6) -> list[tuple[str, int, int, float]]:
        """Articles whose TITLE matches a phrase of the question ("nhat ban", "truyen kieu"): longest phrase first, an exact
        title match ranks above a title that merely contains the phrase."""
        raw = syllables(question)
        toks = [strip_marks(t) for t in raw]
        is_stop = [t in STOP or len(t) < 2 for t in raw]
        found: dict[str, tuple[int, int, float]] = {}
        for n in (4, 3, 2, 1):
            for i in range(len(toks) - n + 1):
                span = toks[i:i + n]
                if is_stop[i] or is_stop[i + n - 1]:
                    continue
                phrase = " ".join(span)
                raw_span = raw[i:i + n]
                rows = self.db.execute(
                    "SELECT a.title, a.lo, a.hi FROM tfts JOIN art a ON a.rowid = tfts.rowid "
                    "WHERE tfts MATCH ? ORDER BY length(a.title) LIMIT 6", (f'"{phrase}"',)).fetchall()
                for title, lo, hi in rows:
                    base = syllables(re.sub(r"\s*\(.*?\)\s*", " ", title))
                    tt = [strip_marks(t) for t in base]
                    exact = tt == span
                    exact_marks = exact and base == raw_span  # same tones too (the STT keeps them)
                    if n == 1 and not exact_marks:
                        continue  # a single syllable only counts when it IS the title with the same tones ("Phở", "Tokyo")
                    # phrase length dominates; matching the tones as well as the letters is worth much more than letters alone
                    score = 50.0 * n + (25.0 if exact_marks else 5.0 if exact else 0.0) - 1.0 * max(len(tt) - n, 0)
                    if title not in found or score > found[title][2]:
                        found[title] = (lo, hi, score)
        ranked = sorted(found.items(), key=lambda kv: -kv[1][2])[:max_titles]
        return [(t, lo, hi, sc) for t, (lo, hi, sc) in ranked]

    def search(self, question: str, k: int = 5, title_weight: float = 6.0) -> list[dict]:
        content, pairs = query_terms(question)
        terms = set(content)
        out: list[dict] = []
        for title, lo, hi, sc in self._title_candidates(question):
            for rid, body in self.db.execute("SELECT rowid, body FROM chunks WHERE rowid BETWEEN ? AND ?", (lo, hi)).fetchall():
                words = {strip_marks(w) for w in syllables(body + " " + title)}
                overlap = len(terms & words)
                out.append({"title": title, "text": body, "source": "title",
                            "score": sc + 25.0 * overlap + (5.0 if rid == lo else 0.0) + answer_bonus(question, body)})
        out.sort(key=lambda h: -h["score"])
        out = out[:k]
        if len([h for h in out if h["score"] >= 100]) < 2:  # nothing convincing by title: BM25 over the bodies
            q = fts_query(question, self._doc_freq(content + [t for p in pairs for t in p.split()]), self.n_rows)
            if q is not None:
                rows = self.db.execute(
                    "SELECT title, body, bm25(chunks, ?, 1.0) AS s FROM chunks WHERE chunks MATCH ? ORDER BY s LIMIT ?",
                    (title_weight, q, k)).fetchall()
                out += [{"title": t, "text": b, "score": -sc_, "source": "body"} for t, b, sc_ in rows]
        out.sort(key=lambda h: -h["score"])
        return out[:k]

    def close(self) -> None:
        self.db.close()


_CAPTION = re.compile(r"(?:nhỏ|thumb|trái|phải|giữa)\|[^.]*?(?:\.|$)", re.I)
_PAGEREF = re.compile(r"tr\.\s?\d+(?:[,–-]\d+)*")


def clean_text(t: str) -> str:
    """Drop wiki image captions ("nhỏ|...") and page references ("tr.223") that waste the prompt budget."""
    t = _PAGEREF.sub("", _CAPTION.sub(" ", t))
    return re.sub(r"\s{2,}", " ", t).strip()


def build_prompt_context(hits: list[dict], max_chars: int = 420, min_score: float = 0.0, max_docs: int = 2) -> str:
    """Compact, deduplicated context block under a character budget (prefill cost is the price of RAG on a CPU)."""
    out, used, per_title = [], 0, {}
    hits = [{**h, "text": clean_text(h["text"])} for h in hits]
    for h in hits:
        if h["score"] < min_score or per_title.get(h["title"], 0) >= 2:
            continue
        per_title[h["title"]] = per_title.get(h["title"], 0) + 1
        room = max_chars - used
        if room < 80:
            break
        text = h["text"]
        if len(text) > room:
            cut = text[:room]
            text = cut[: max(cut.rfind(". "), cut.rfind(", "), 60) + 1]
        out.append(f"[{h['title']}] {text}")
        used += len(text) + len(h["title"]) + 3
        if len(out) >= max_docs:
            break
    return "\n".join(out)
