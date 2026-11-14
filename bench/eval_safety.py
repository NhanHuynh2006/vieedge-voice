#!/usr/bin/env python3
"""Evaluates the vetted safety cards (vieedge/safety): does an emergency question get the right card, does an emergency
without a card get the "call 115" fallback, and do ordinary questions stay off the safety path?

  eval_safety.py                       typed questions: data/an_toan/cau_hoi_thu.jsonl + the 345 general QA test questions
  eval_safety.py --asr manifest.jsonl  the same questions after TTS (another voice) and Zipformer STT (wav + q per line)

Labels: a card id, "du_phong" (no card: fallback expected) or "khong" (must not trigger). Writes results/an_toan/.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from common import ROOT

from vieedge.safety import SafetyCards


def classify(m):
    if m is None:
        return "khong"
    return m.card.id if m.card else "du_phong"


def score(rows):
    by = {"trong": Counter(), "ngoai": Counter(), "am": Counter(), "qa": Counter()}
    errs = []
    for r in rows:
        got, kind = r["got"], r["loai"]
        want = r["nhan"] if isinstance(r["nhan"], list) else [r["nhan"]]
        c = by[kind]
        c["n"] += 1
        if got in want:
            c["dung"] += 1
        elif kind == "trong":
            c["sot" if got in ("khong", "du_phong") else "sai_the"] += 1
            if got == "du_phong":
                c["du_phong"] += 1
        elif kind == "ngoai":
            c["sai_the" if got not in ("khong", "du_phong") else "khong_kich_hoat"] += 1
        else:
            c["kich_hoat_nham"] += 1
        if got not in want:
            errs.append(r)
    return {k: dict(v) for k, v in by.items()}, errs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", default=str(ROOT / "data/an_toan/the_an_toan.json"))
    ap.add_argument("--asr", type=Path, help="manifest with q (reference), text (STT output) and the label fields")
    ap.add_argument("--tag", default="typed")
    ap.add_argument("--set", default="data/an_toan/cau_hoi_thu.jsonl", help="labelled questions (dev set by default)")
    ap.add_argument("--no-qa", action="store_true", help="do not add the 345 general QA questions")
    ap.add_argument("--clf", help="second-stage classifier (data/an_toan/phan_loai.json)")
    a = ap.parse_args()
    sc = SafetyCards(a.cards, a.clf)
    if a.asr:
        items = [json.loads(l) for l in open(a.asr, encoding="utf-8") if l.strip()]
    else:
        items = [json.loads(l) for l in open(ROOT / a.set, encoding="utf-8") if l.strip()]
        relabel = {json.loads(l)["q"]: json.loads(l)["nhan"] for l in open(ROOT / "data/an_toan/qa_nhan_lai.jsonl", encoding="utf-8") if l.strip()}
        if not a.no_qa:
            items += [{"q": q, "nhan": relabel.get(q, "khong"), "loai": "qa"}
                      for q in (json.loads(l)["q"] for l in open(ROOT / "data/qa/test.jsonl", encoding="utf-8") if l.strip())]
    rows, t0 = [], time.perf_counter()
    for it in items:
        text = it.get("text", it["q"])
        m = sc.match(text)
        rows.append({**it, "text": text, "got": classify(m), "key": m.key if m else "", "via": m.via if m else ""})
    ms = (time.perf_counter() - t0) * 1000 / max(len(items), 1)
    summ, errs = score(rows)
    out = {"tag": a.tag, "classifier": bool(sc.clf), "by_classifier": sum(r["via"] == "phan_loai" for r in rows), "cards": len(sc.cards), "version": sc.version, "n": len(rows), "match_ms_per_question": round(ms, 3), "by_kind": summ}
    d = ROOT / "results/an_toan"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"eval_{a.tag}.json").write_text(json.dumps({**out, "errors": errs}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    for e in errs:
        print(f"  [{e['loai']}] want={str(e['nhan']):<18} got={e['got']:<18} key={e['key']!r:<22} {e['text']}")


if __name__ == "__main__":
    main()
