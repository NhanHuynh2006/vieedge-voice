#!/usr/bin/env python3
"""Transcribes a synthesised question manifest with the Zipformer STT and joins the labels back, for eval_safety.py --asr.

  asr_safety_manifest.py data/manifests/e2e_an_toan_v2.jsonl data/an_toan/cau_hoi_doc_lap_v2.jsonl results/an_toan/asr_v2.jsonl
"""
from __future__ import annotations

import json
import sys

from common import ROOT, load_audio, wer

from vieedge.stt.zipformer import ZipformerVi


def main() -> None:
    man, labels, out = sys.argv[1:4]
    lab = {json.loads(l)["q"]: json.loads(l) for l in open(ROOT / labels, encoding="utf-8") if l.strip()}
    stt = ZipformerVi(str(ROOT / "models/stt/zipformer-vi"), threads=3)
    rows, refs, hyps = [], [], []
    for l in open(ROOT / man, encoding="utf-8"):
        m = json.loads(l)
        r = stt.transcribe(load_audio(str(ROOT / m["audio"])))
        rows.append({**lab[m["text"]], "text": r.text})
        refs.append(m["text"])
        hyps.append(r.text)
    with open(ROOT / out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} transcribed, WER {wer(refs, hyps):.3f} -> {out}")


if __name__ == "__main__":
    main()
