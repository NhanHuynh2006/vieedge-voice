#!/usr/bin/env python3
"""Median per-stage latency (ms after the user stops talking) from the newest turn log(s). usage: stage_summary.py [n_files]"""
import glob
import json
import os
import statistics as st
import sys

n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
d = os.environ.get("VIEEDGE_RESULTS", "results")
for f in sorted(glob.glob(f"{d}/turns/*.jsonl"), key=os.path.getmtime)[-n:]:
    rows = [json.loads(l) for l in open(f)]
    keys = ["endpoint", "stt_final", "llm_request", "llm_first_token", "first_chunk", "tts_first_done", "first_audio"]
    med = {k: round(st.median(r["t_rel_ms"][k] for r in rows if k in r["t_rel_ms"])) for k in keys}
    tok = st.median(r["meta"].get("llm_tok_s", 0) for r in rows)
    tts = st.median(r["meta"]["tts_ms"][0] for r in rows if r["meta"].get("tts_ms"))
    print(os.path.basename(f), len(rows), "turns", med, f"tok/s={tok:.1f} first-chunk-tts={tts:.0f}ms")
