#!/usr/bin/env python3
"""Build the offline knowledge base: Vietnamese Wikipedia (CC BY-SA 3.0, wikimedia/wikipedia 20231101.vi) -> SQLite FTS5.

Keeps the `--articles` longest articles (a proxy for notability: removes the many bot-made stubs), and from each the first
~6000 characters cut into chunks of <= ~420 characters at sentence boundaries. Output: models/rag/wiki_vi.sqlite
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from vieedge.rag.index import add_title_index  # noqa: E402

SKIP_TITLE = re.compile(r"^(Danh sách|Thể loại|Bản mẫu|Tập tin|Wikipedia|Mô đun|Cổng thông tin|Thảo luận|\d{1,4}$|Niên biểu)", re.I)


def chunks(text: str, limit: int = 420, head: int = 6000) -> list[str]:
    text = re.sub(r"\s*\n+\s*", " ", text[:head]).strip()
    sents = re.split(r"(?<=[.!?])\s+", text)
    out, cur = [], ""
    for s in sents:
        if cur and len(cur) + len(s) + 1 > limit:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return [c[: limit + 120] for c in out if len(c) > 40]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--articles", type=int, default=200_000)
    ap.add_argument("--out", type=Path, default=ROOT / "models/rag/wiki_vi.sqlite")
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(4):
        p = hf_hub_download("wikimedia/wikipedia", f"20231101.vi/train-0000{i}-of-00004.parquet", repo_type="dataset")
        t = pq.read_table(p, columns=["title", "text"])
        titles, texts = t.column("title").to_pylist(), t.column("text").to_pylist()
        rows += [(len(x), ti, x) for ti, x in zip(titles, texts) if not SKIP_TITLE.match(ti) and len(x) > 500]
        print(f"shard {i}: {len(rows)} candidate articles", flush=True)
    rows.sort(key=lambda r: -r[0])
    rows = rows[: a.articles]
    if a.out.exists():
        a.out.unlink()
    db = sqlite3.connect(a.out)
    db.execute("CREATE VIRTUAL TABLE chunks USING fts5(title, body, tokenize='unicode61 remove_diacritics 2')")
    n = 0
    for _, title, text in rows:
        for c in chunks(text):
            db.execute("INSERT INTO chunks(title, body) VALUES (?, ?)", (title, c))
            n += 1
        if n % 100000 < 6:
            db.commit()
    db.commit()
    db.execute("INSERT INTO chunks(chunks) VALUES('optimize')")
    db.commit()
    add_title_index(db)  # title phrase lookup
    db.execute("CREATE VIRTUAL TABLE vocab USING fts5vocab(chunks, 'row')")  # document frequencies for query pruning
    db.commit()
    db.execute("VACUUM")
    db.close()
    print(f"{len(rows)} articles, {n} chunks -> {a.out} ({a.out.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
