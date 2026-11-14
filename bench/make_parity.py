#!/usr/bin/env python3
"""Writes results/an_toan/parity_python.jsonl: the Python matcher's answer (rules + classifier) for every safety question
we have, typed and transcribed; SafetyCardsParityTest (Android) and the in-app safety_eval hook must give the same answers."""
from __future__ import annotations

import json

from common import ROOT

from vieedge.safety import SafetyCards

A = ROOT / "data/an_toan"


def qs():
    for p in ["cau_hoi_thu.jsonl", "cau_hoi_doc_lap.jsonl", "cau_hoi_doc_lap_v2.jsonl", "cau_hoi_doc_lap_v3.jsonl", "cau_hoi_doc_lap_v4.jsonl", "cau_hoi_doc_lap_v5.jsonl"]:
        yield from (json.loads(l)["q"] for l in open(A / p, encoding="utf-8") if l.strip())
    for p in ["results/an_toan/asr_v2.jsonl", "results/an_toan/asr_v3.jsonl", "results/an_toan/asr_v3_vais.jsonl", "results/an_toan/asr_v4_hw.jsonl",
              "results/an_toan/asr_v4_vais_hw.jsonl", "results/an_toan/asr_v5_hw.jsonl", "results/an_toan/asr_v5_vais_hw.jsonl"]:
        if (ROOT / p).exists():
            yield from (json.loads(l)["text"] for l in open(ROOT / p, encoding="utf-8") if l.strip())
    for p in ["data/qa/test.jsonl", "data/qa/test_asr.jsonl"]:
        yield from (json.loads(l)["q"] for l in open(ROOT / p, encoding="utf-8") if l.strip())


def main() -> None:
    sc = SafetyCards(A / "the_an_toan.json", A / "phan_loai.json")
    seen, n = set(), 0
    with open(ROOT / "results/an_toan/parity_python.jsonl", "w", encoding="utf-8") as f:
        for q in qs():
            if q in seen:
                continue
            seen.add(q)
            m = sc.match(q)
            got = "khong" if m is None else (m.card.id if m.card else "du_phong")
            f.write(json.dumps({"q": q, "got": got, "via": m.via if m else ""}, ensure_ascii=False) + "\n")
            n += 1
    print(n, "questions -> results/an_toan/parity_python.jsonl", "classifier" if sc.clf else "rules only")


if __name__ == "__main__":
    main()
