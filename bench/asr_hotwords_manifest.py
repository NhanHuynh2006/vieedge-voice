#!/usr/bin/env python3
"""Like asr_safety_manifest.py but decodes with the shipped phone setting: modified beam search (4 paths) and the safety
hotwords at score 1.0 (chosen on v2 by eval_hotwords.py).

  asr_hotwords_manifest.py data/manifests/e2e_an_toan_v3.jsonl data/an_toan/cau_hoi_doc_lap_v3.jsonl results/an_toan/asr_v3_hw.jsonl
"""
from __future__ import annotations

import json
import sys

from common import ROOT, load_audio, wer
from eval_hotwords import hotwords, recognizer

from vieedge.safety import SafetyCards, norm_vi


def main() -> None:
    man, labels, out = sys.argv[1:4]
    cards = SafetyCards(ROOT / "data/an_toan/the_an_toan.json")
    hw = ROOT / "results/an_toan/hotwords.txt"
    hw.write_text("\n".join(h.upper() for h in hotwords(cards)) + "\n", encoding="utf-8")
    rec = recognizer("modified_beam_search", str(hw), 1.0)
    lab = {json.loads(l)["q"]: json.loads(l) for l in open(ROOT / labels, encoding="utf-8") if l.strip()}
    rows, refs, hyps = [], [], []
    for l in open(ROOT / man, encoding="utf-8"):
        m = json.loads(l)
        st = rec.create_stream()
        st.accept_waveform(16000, load_audio(str(ROOT / m["audio"])))
        rec.decode_stream(st)
        t = st.result.text.strip().lower()
        rows.append({**lab[m["text"]], "text": t}); refs.append(norm_vi(m["text"])); hyps.append(t)
    with open(ROOT / out, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    print(f"{len(rows)} transcribed with hotwords, WER {wer(refs, hyps):.3f} -> {out}")


if __name__ == "__main__":
    main()
