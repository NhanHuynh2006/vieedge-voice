#!/usr/bin/env python3
"""End-to-end turns (P1-P3, S5 and the headline number of PLAN §9).

The full assistant runs with the `file` audio backend: each question WAV is streamed into the
"microphone" in real time, the pipeline answers, and the turn timeline is collected
(speech end -> final text -> first LLM token -> first sentence -> first audio sample -> done).
>= 100 turns per session, 3 sessions -> mean ± std and p50/p95/p99.

  bench_e2e.py --exp P3-npu  --manifest e2e_synth --turns 100 --sessions 3
  bench_e2e.py --exp P3-cpu  --set stt.backend=ct2
  bench_e2e.py --exp P1-full --set pipeline.stream_sentences=false
  bench_e2e.py --exp P2-300  --set vad.endpoint_ms=300            (also 500 / 800)
  bench_e2e.py --exp S5-off  --set stt.incremental.enabled=false
  bench_e2e.py --exp E2E-live --live    # 🧑 questions played on the speaker and heard through the mic

Energy: mean board power during the session (INA226/PMIC via sysmon, or the 🧑 external meter
CSV joined later in make_tables.py) x turn duration -> J per turn.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time

import numpy as np

from common import append_experiment, check_thermal, load_audio, load_manifest, pct, results_dir, thermal_state, wer
from vieedge.config import load_config, set_override
from vieedge.events import EventBus

METRICS = ["first_audio_ms", "answer_audio_ms", "stt_after_speech_ms", "stt_after_endpoint_ms", "endpoint_wait_ms", "ttft_ms",
           "first_chunk_ms", "tts_first_ms", "llm_total_ms", "turn_total_ms"]


def run_session(cfg, rows, live: bool, timeout: float, idx: int) -> dict:
    from vieedge.pipeline import Assistant

    bus = EventBus()
    asst = Assistant(cfg, bus)
    asst.run(block=False)
    sysq = bus.subscribe()
    recs, power, temps = [], [], []
    x0 = asst.engine.xruns()
    t_start = time.monotonic()
    try:
        for i, r in enumerate(rows):
            time.sleep(0.8)
            if live:
                x = load_audio(r["audio"])
                asst.mic.guard.mode = "off"
                asst.speaker.play(x, 16000)
                asst.speaker.wait_done()
                asst.mic.guard.mode = cfg["echo_guard"]["mode"]
                rec = asst.wait_turn(timeout)
            else:
                asst.engine.inject(r["audio"])
                rec = asst.wait_turn(timeout)
            while not sysq.empty():
                ev = sysq.get_nowait()
                if ev.get("type") == "sys":
                    if ev.get("power_w") is not None:
                        power.append(ev["power_w"])
                    if ev.get("temp_c") is not None:
                        temps.append(ev["temp_c"])
            if rec is None:
                print(f"  [{idx}:{i}] timeout / no turn")
                recs.append({"id": r["id"], "timeout": True})
                continue
            rec["id"], rec["ref_q"] = r["id"], r["text"]
            recs.append(rec)
            m = rec["metrics"]
            print(f"  [{idx}:{i}] first_audio {m.get('first_audio_ms')} ms | stt {m.get('stt_after_speech_ms')} | "
                  f"ttft {m.get('ttft_ms')} | Q: {rec['question'][:50]}")
    finally:
        dur_h = (time.monotonic() - t_start) / 3600
        x1 = asst.engine.xruns()
        asst.close()
    xr = (x1["capture"] - x0["capture"]) + (x1["playback"] - x0["playback"])
    return {"turns": recs, "xruns": xr, "xruns_per_h": xr / max(dur_h, 1e-9), "power": power, "temps": temps,
            "audio_info": asst.audio_info, "llm_rss_mb": asst.sysmon.last.get("llm_rss_mb"),
            "app_rss_mb": asst.sysmon.last.get("app_rss_mb"), "ram_used_mb": asst.sysmon.last.get("ram_used_mb")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--exp", required=True)
    ap.add_argument("--manifest", default="e2e_synth")
    ap.add_argument("--turns", type=int, default=100)
    ap.add_argument("--sessions", type=int, default=3)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--timeout", type=float, default=90)
    ap.add_argument("--notes", default="")
    a = ap.parse_args()
    over: dict = {"web": {"enabled": False}, "gpio": {"enabled": False}}
    if not a.live:
        over["audio"] = {"backend": "file"}
    for kv in a.set:
        k, v = kv.split("=", 1)
        set_override(over, k, v)
    cfg = load_config(a.config, over)
    rows = load_manifest(a.manifest)[: a.turns]
    th0 = thermal_state()
    sessions = []
    for s in range(a.sessions):
        print(f"[{a.exp}] session {s + 1}/{a.sessions}")
        sessions.append(run_session(cfg, rows, a.live, a.timeout, s))
    th1 = thermal_state()

    turns = [t for s in sessions for t in s["turns"] if not t.get("timeout")]
    agg = {k: pct([t["metrics"].get(k) for t in turns]) for k in METRICS}
    per_session_p50 = [pct([t["metrics"].get("first_audio_ms") for t in s["turns"] if not t.get("timeout")])["p50"] for s in sessions]
    asr_wer = wer([t["ref_q"] for t in turns], [t["question"] for t in turns]) if turns else None
    spec_hits = [t["meta"].get("stt_speculative_hit") for t in turns]
    tok_s = [t["meta"].get("llm_tok_s") for t in turns if t["meta"].get("llm_tok_s")]
    power = [p for s in sessions for p in s["power"]]
    temps = [x for s in sessions for x in s["temps"]] + [th1.get("temp_c") or 0]
    turn_s = [t["metrics"]["turn_total_ms"] / 1e3 for t in turns if t["metrics"].get("turn_total_ms")]
    p_w = statistics.mean(power) if power else None
    j_turn = p_w * statistics.mean(turn_s) if (p_w and turn_s) else None
    summary = {"metrics": agg, "first_audio_p50_per_session": per_session_p50,
               "first_audio_p50_mean_std": [round(float(np.mean([x for x in per_session_p50 if x])), 1),
                                            round(float(np.std([x for x in per_session_p50 if x])), 1)] if any(per_session_p50) else None,
               "asr_wer_on_questions": asr_wer, "speculative_hit_rate": (sum(bool(x) for x in spec_hits) / len(spec_hits)) if spec_hits else None,
               "timeouts": sum(1 for s in sessions for t in s["turns"] if t.get("timeout")),
               "xruns_per_h": [s["xruns_per_h"] for s in sessions], "power_w_mean": p_w}
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    s = cfg["stt"]
    fa = agg["first_audio_ms"]
    append_experiment({
        "exp_id": a.exp, "stt_model": (s["ct2"]["model"] if s["backend"] == "ct2" else
                                       s["hybrid"]["hef"] if s["hybrid"]["encoder"] == "hailo" else s["hybrid"]["onnx"]).split("/")[-1],
        "stt_where": "npu+cpu" if s["backend"] == "hybrid" and s["hybrid"]["encoder"] == "hailo" else "cpu",
        "llm_model": cfg["llm"]["model"].split("/")[-1], "spec_dec": cfg["llm"].get("draft_model") or "no",
        "threads": cfg["llm"]["threads"], "wer": round(asr_wer, 4) if asr_wer is not None else "",
        "ttft_ms": agg["ttft_ms"]["p50"], "tok_s": round(statistics.median(tok_s), 2) if tok_s else "",
        "first_audio_p50": fa["p50"], "first_audio_p95": fa["p95"], "first_audio_p99": fa["p99"],
        "ram_mb": sessions[-1].get("ram_used_mb"), "temp_max": max(temps) if temps else "", "power_w": round(p_w, 2) if p_w else "",
        "j_per_turn": round(j_turn, 1) if j_turn else "", "xruns_per_h": round(float(np.mean(summary["xruns_per_h"])), 2),
        "notes": ";".join(filter(None, [a.notes, f"manifest={a.manifest}", f"turns={len(turns)}x{a.sessions}sess",
                                        f"spec_hit={summary['speculative_hit_rate']:.2f}" if summary["speculative_hit_rate"] is not None else "",
                                        f"endpoint_ms={cfg['vad']['endpoint_ms']}", f"stream={cfg['pipeline']['stream_sentences']}",
                                        f"first_words={cfg['pipeline'].get('first_chunk_max_words')}",
                                        "live" if a.live else "file-audio", check_thermal(th0, th1)])),
    }, raw={"summary": summary, "sessions": sessions, "config": dict(cfg)})
    (results_dir() / "raw").mkdir(exist_ok=True)


if __name__ == "__main__":
    main()
