#!/usr/bin/env python3
"""Retrieval probe: 20 factual questions with a required answer string; hit@2 = the string is inside the top-2 chunks."""
import json
import sys
import time

from common import ROOT
from vieedge.rag import KnowledgeBase, build_prompt_context
from vieedge.rag.index import strip_marks

kb = KnowledgeBase(ROOT / "models/rag/wiki_vi.sqlite")
kb.search("xin chào")
rows = [json.loads(line) for line in open(ROOT / "data/rag/retrieval_probe.jsonl", encoding="utf-8")]
verbose = "-v" in sys.argv
hit = 0
ms = []
for r in rows:
    t = time.monotonic()
    hits = kb.search(r["q"], 6)
    ms.append((time.monotonic() - t) * 1e3)
    ctx = build_prompt_context(hits, 420, 0.0, 2)
    ok = strip_marks(r["must"]) in strip_marks(ctx)
    hit += ok
    if verbose or not ok:
        print(("OK  " if ok else "MISS"), r["q"], "->", [(h["title"], round(h["score"]), h.get("source")) for h in hits[:3]])
ms.sort()
print(f"hit@2 {hit}/{len(rows)}  latency p50 {ms[len(ms) // 2]:.0f} ms  max {ms[-1]:.0f} ms")
