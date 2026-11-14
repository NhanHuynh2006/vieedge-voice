#!/usr/bin/env python3
"""LLM router for the safety cards: the on-device LLM only *chooses* a card id (grammar-constrained), it never writes advice.
Used when the key-phrase matcher finds nothing. Evaluates router-only and key-phrase + router on a labelled set.

  route_safety_llm.py --set data/an_toan/cau_hoi_thu.jsonl [--qa] --url http://127.0.0.1:8095 --tag dev
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

from common import ROOT

from vieedge.safety import SafetyCards


def build_prompt(sc: SafetyCards, question: str) -> str:
    lines = "\n".join(f"{c.id}: {c.title}" for c in sc.cards)
    sys = ("Bạn là bộ phân loại câu nói cho trợ lý an toàn. Đọc câu của người dùng rồi trả lời đúng một mã.\n"
           "Chọn mã của tình huống trong danh sách nếu người dùng đang gặp, sắp gặp, hoặc hỏi cách xử lý tình huống đó.\n"
           "Trả lời KHAC nếu là tình huống khẩn cấp hay vấn đề sức khỏe mà danh sách không có.\n"
           "Trả lời KHONG nếu câu không xin hướng dẫn xử lý: hỏi kiến thức, tin tức, lịch sử, chuyện thường ngày.\n"
           "Danh sách:\n" + lines)
    return f"<|im_start|>system\n{sys}<|im_end|>\n<|im_start|>user\n{question}<|im_end|>\n<|im_start|>assistant\n"


def grammar(sc: SafetyCards) -> str:
    return "root ::= " + " | ".join(f'"{x}"' for x in [c.id for c in sc.cards] + ["KHAC", "KHONG"])


def route(url: str, sc: SafetyCards, q: str, gram: str) -> tuple[str, float]:
    body = json.dumps({"prompt": build_prompt(sc, q), "grammar": gram, "n_predict": 16, "temperature": 0, "cache_prompt": True}).encode()
    t0 = time.perf_counter()
    r = json.loads(urllib.request.urlopen(urllib.request.Request(url + "/completion", body, {"Content-Type": "application/json"}), timeout=60).read())
    out = r["content"].strip()
    return {"KHAC": "du_phong", "KHONG": "khong"}.get(out, out), (time.perf_counter() - t0) * 1000


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="data/an_toan/cau_hoi_thu.jsonl")
    ap.add_argument("--qa", action="store_true")
    ap.add_argument("--url", default="http://127.0.0.1:8095")
    ap.add_argument("--tag", default="dev")
    a = ap.parse_args()
    sc = SafetyCards(ROOT / "data/an_toan/the_an_toan.json")
    gram = grammar(sc)
    items = [json.loads(l) for l in open(ROOT / a.set, encoding="utf-8") if l.strip()]
    if a.qa:
        rel = {json.loads(l)["q"]: json.loads(l)["nhan"] for l in open(ROOT / "data/an_toan/qa_nhan_lai.jsonl", encoding="utf-8") if l.strip()}
        items += [{"q": q, "nhan": rel.get(q, "khong"), "loai": "qa"} for q in (json.loads(l)["q"] for l in open(ROOT / "data/qa/test.jsonl", encoding="utf-8"))]
    res = {"router": Counter(), "hybrid": Counter()}
    per, lat, errs = Counter(), [], []
    for it in items:
        want = it["nhan"] if isinstance(it["nhan"], list) else [it["nhan"]]
        m = sc.match(it["q"])
        kw = None if m is None else (m.card.id if m.card else "du_phong")
        rt, ms = route(a.url, sc, it["q"], gram)
        lat.append(ms)
        hy = kw if kw is not None else rt
        for name, got in (("router", rt), ("hybrid", hy)):
            res[name][(it["loai"], got in want)] += 1
        if hy not in want:
            errs.append({"q": it["q"], "loai": it["loai"], "want": want, "kw": kw, "router": rt})
    out = {"tag": a.tag, "n": len(items), "router_ms_p50": sorted(lat)[len(lat) // 2],
           "router": {f"{k[0]}_{'dung' if k[1] else 'sai'}": v for k, v in sorted(res["router"].items())},
           "hybrid": {f"{k[0]}_{'dung' if k[1] else 'sai'}": v for k, v in sorted(res["hybrid"].items())}}
    (ROOT / "results/an_toan" / f"router_{a.tag}.json").write_text(json.dumps({**out, "errors": errs}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    for e in errs[:60]:
        print(f"  [{e['loai']}] want={e['want']} kw={e['kw']} router={e['router']} | {e['q']}")


if __name__ == "__main__":
    main()
