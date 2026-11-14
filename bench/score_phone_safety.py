#!/usr/bin/env python3
"""Scores a phone run of bench/phone_wavs.sh on spoken safety questions: right card, and first-audio latency.

  score_phone_safety.py <run prefix> <pick.json>   (writes <run prefix>.score.json and prints a summary)
"""
import json
import re
import statistics as st
import sys


def main() -> None:
    run, pick = sys.argv[1:3]
    pk = {p["name"]: p for p in json.load(open(pick, encoding="utf-8"))}
    rows = []
    for line in open(run + ".log", encoding="utf-8"):
        m = re.search(r"TEST turn wav=\S*/(\S+\.wav) (\{.*)$", line)
        if not m or m.group(1) not in pk:
            continue
        t = json.loads(m.group(2)); p = pk[m.group(1)]
        want = p["nhan"] if isinstance(p["nhan"], list) else [p["nhan"]]
        f = t["m"].get("fast", "")
        got = t["m"].get("intent") if f == "safety" else ("du_phong" if f == "safety-fallback" else "khong")
        rows.append({"wav": m.group(1), "q_ref": p["q"], "heard": t["q"], "want": want, "got": got,
                     "first_audio_ms": t["m"].get("first_audio_ms"), "stt_ms": t["m"].get("stt_ms")})
    fa = sorted(r["first_audio_ms"] for r in rows if r["got"] != "khong" and r["first_audio_ms"])
    q = lambda a, x: a[min(len(a) - 1, int(x * (len(a) - 1) + 0.5))] if a else None
    s = {"n": len(rows), "correct": sum(r["got"] in r["want"] for r in rows), "safety_first_audio_ms": {"n": len(fa), "p50": q(fa, .5), "p95": q(fa, .95), "max": fa[-1] if fa else None},
         "stt_ms_p50": st.median([r["stt_ms"] for r in rows if r["stt_ms"]]) if rows else None, "rows": rows}
    json.dump(s, open(run + ".score.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{run}: {s['correct']}/{s['n']} correct; first audio p50 {s['safety_first_audio_ms']['p50']:.0f} ms p95 {s['safety_first_audio_ms']['p95']:.0f} max {s['safety_first_audio_ms']['max']:.0f}; stt+endpoint p50 {s['stt_ms_p50']:.0f} ms")
    for r in rows:
        if r["got"] not in r["want"]:
            print("  MISS", r["want"], r["got"], "|", r["q_ref"], "=>", r["heard"])


if __name__ == "__main__":
    main()
