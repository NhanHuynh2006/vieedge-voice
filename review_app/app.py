#!/usr/bin/env python3
"""Quick human review tool (🧑 PLAN §8): runs on the laptop, opens in a browser, keyboard-driven.

  python review_app/app.py --mode qa      --file results/raw/answers_M2_<model>.jsonl --n 100   (~45 min)
  python review_app/app.py --mode mos     --dir results/audio/mos_vi_VN-vais1000-medium          (20 sentences, 1-5)
  python review_app/app.py --mode numbers --dir results/audio/t2_norm                            (30 sentences, đúng/sai)
Answers are saved after every click to results/review/<mode>_<name>_<rater>.jsonl.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parents[1]
HTML = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


def load_items(a) -> list[dict]:
    if a.mode == "qa":
        rows = [json.loads(l) for l in open(a.file, encoding="utf-8")]
        random.Random(0).shuffle(rows)
        return [{"id": r.get("id") or i, "q": r["q"], "ref": r.get("ref", ""), "answer": r["answer"]} for i, r in enumerate(rows[: a.n])]
    d = Path(a.dir)
    sheet = list(csv.DictReader(open(d / "sheet.csv", encoding="utf-8")))
    return [{"id": s["file"], "text": s["text"], "expected": s.get("expected_reading", ""), "audio": s["file"]} for s in sheet]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["qa", "mos", "numbers"], required=True)
    ap.add_argument("--file")
    ap.add_argument("--dir")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--port", type=int, default=8077)
    a = ap.parse_args()
    items = load_items(a)
    name = Path(a.file).stem if a.file else Path(a.dir).name
    out_dir = ROOT / "results" / "review"
    out_dir.mkdir(parents=True, exist_ok=True)
    app = FastAPI()

    @app.get("/")
    def index():
        return HTMLResponse(HTML)

    @app.get("/items")
    def get_items():
        return JSONResponse({"mode": a.mode, "name": name, "items": items})

    @app.get("/audio/{fname}")
    def audio(fname: str):
        return FileResponse(Path(a.dir) / Path(fname).name)

    @app.post("/save")
    async def save(req: Request):
        d = await req.json()
        rater = "".join(c for c in d.get("rater", "anon") if c.isalnum()) or "anon"
        with open(out_dir / f"{a.mode}_{name}_{rater}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
        return {"ok": True}

    print(f"open http://127.0.0.1:{a.port}  ({len(items)} items, mode {a.mode})")
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
