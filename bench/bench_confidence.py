#!/usr/bin/env python3
"""Does the STT confidence predict transcription errors? (basis for "I did not hear you, please repeat")

Literature: Whisper's own heuristics reject segments with avg_logprob < -1.0; Naderi et al. (Interspeech 2024) use ASR
confidence to restrict LLM correction to uncertain sentences. Here: per-utterance confidence vs word error rate on
VIVOS+FLEURS test (clean and 10 dB noise); reports AUROC and, for several thresholds, the share of utterances rejected
and the WER of the ones that are accepted.
"""
from __future__ import annotations

import argparse
import json
import random

import numpy as np

from common import ROOT, append_experiment, edit_distance, load_audio, load_manifest, mix_snr
from vieedge.config import load_config
from vieedge.stt import make_stt
from vieedge.textproc import wer_normalize


def auroc(score_good: np.ndarray, is_bad: np.ndarray) -> float:
    """P(confidence of a bad utterance < confidence of a good one)."""
    bad, good = score_good[is_bad], score_good[~is_bad]
    if len(bad) == 0 or len(good) == 0:
        return float("nan")
    return float(np.mean([(g > b) + 0.5 * (g == b) for b in bad for g in good]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default=str(ROOT / "deploy/config/vieedge-laptop.yaml"))
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--model", default="stt/ct2/phowhisper-tiny-int8")
    ap.add_argument("--backend", default="ct2", choices=["ct2", "zipformer"])
    ap.add_argument("--sets", nargs="+", default=["vivos_test", "fleurs_vi_test"])
    a = ap.parse_args()
    cfg = load_config(a.config, {"stt": {"backend": a.backend, "ct2": {"model": a.model, "window_s": 10, "threads": 3}}})
    stt = make_stt(cfg)
    stt.warmup()
    noises = [load_audio(str(p)) for p in sorted((ROOT / "data/noise").rglob("ch01.wav"))]
    rnd = random.Random(0)
    rows = []
    for m in a.sets:
        for r in load_manifest(m, a.n):
            x = load_audio(r["audio"])[: 10 * 16000]
            for snr in (None, 10.0):
                y = x if snr is None else mix_snr(x, rnd.choice(noises), snr, rnd)
                res = stt.transcribe(y)
                ref, hyp = wer_normalize(r["text"]).split(), wer_normalize(res.text).split()
                rows.append({"set": m, "snr": snr, "conf": res.confidence, "err": edit_distance(ref, hyp), "n": len(ref),
                             "ref": r["text"], "hyp": res.text})
    conf = np.array([r["conf"] for r in rows])
    err = np.array([r["err"] for r in rows], dtype=float)
    n = np.array([r["n"] for r in rows], dtype=float)
    wer_u = err / n
    bad = wer_u > 0.30
    out = {"n_utts": len(rows), "overall_wer": float(err.sum() / n.sum()), "frac_bad(>30% WER)": float(bad.mean()),
           "auroc_bad_vs_conf": auroc(conf, bad), "thresholds": []}
    print(f"utts {len(rows)}  WER {out['overall_wer']:.3f}  bad {bad.mean():.2f}  AUROC(conf predicts bad) {out['auroc_bad_vs_conf']:.3f}")
    print("threshold  rejected  WER(accepted)  bad-answers-passed")
    for thr in (-0.05, -0.08, -0.1, -0.15, -0.2, -0.25, -0.3, -0.4, -0.5, -9):
        acc = conf >= thr
        w = float(err[acc].sum() / n[acc].sum()) if acc.any() else float("nan")
        out["thresholds"].append({"thr": thr, "rejected": float(1 - acc.mean()), "wer_accepted": w, "bad_passed": float((bad & acc).sum() / max(bad.sum(), 1))})
        print(f"{thr:>8}  {1 - acc.mean():>7.1%}  {w:>12.3f}  {(bad & acc).sum() / max(bad.sum(), 1):>10.1%}")
    (ROOT / "results/raw").mkdir(exist_ok=True)
    json.dump({"summary": out, "rows": rows}, open(ROOT / f"results/raw/confidence_study_{a.backend}.json", "w"), ensure_ascii=False)
    append_experiment({"exp_id": "C1" if a.backend == "ct2" else "C2", "stt_model": a.model.split("/")[-1] if a.backend == "ct2" else "zipformer-vi-30M-int8", "stt_where": "cpu", "wer": round(out["overall_wer"], 4),
                       "notes": f"confidence study: AUROC={out['auroc_bad_vs_conf']:.3f}; n={len(rows)}; thresholds in results/raw/confidence_study.json"})


if __name__ == "__main__":
    main()
