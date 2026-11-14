#!/usr/bin/env python3
"""Figures for the report/poster from results/ (PLAN §12 P6). Each figure is skipped when its data
does not exist yet, so the script can run at any stage. Output: docs/report/figures/*.png

  fig_stt_ladder      WER (clean / noisy) per STT configuration
  fig_quant_ladder    tokens/s, RAM and Global-MMLU-vi accuracy per GGUF quantisation
  fig_first_audio     CDF of "user stops talking -> first audio sample" per end-to-end config
  fig_waterfall       median latency waterfall (stages) per end-to-end config
  fig_cyclictest      max / histogram of cyclictest latency on the audio core, O0-O4
  fig_training        LoRA train/eval loss
"""
from __future__ import annotations

import csv
import glob
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from common import ROOT, results_dir  # noqa: E402

FIG = ROOT / "docs" / "report" / "figures"
PALETTE = ["#2f62c9", "#0f7b6c", "#e17055", "#6c5ce7", "#c98a00", "#5d6d7e"]


def rows() -> list[dict]:
    p = results_dir() / "experiments.csv"
    return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", dpi=160)
    plt.close(fig)
    print("figure", name)


def fig_stt(rs):
    sel = [r for r in rs if r["exp_id"].startswith("S") and f(r["wer"]) is not None]
    if not sel:
        return
    lab = [f"{r['exp_id']}\n{r['stt_model'][:22]}\n({r['os_cfg']})" for r in sel]
    x = np.arange(len(sel))
    fig, ax = plt.subplots(figsize=(max(6, len(sel) * 1.1), 4))
    ax.bar(x - 0.2, [f(r["wer"]) * 100 for r in sel], 0.4, label="sạch", color=PALETTE[0])
    ax.bar(x + 0.2, [(f(r["wer_noisy"]) or 0) * 100 for r in sel], 0.4, label="có ồn", color=PALETTE[2])
    ax.set_xticks(x, lab, fontsize=7)
    ax.set_ylabel("WER (%)")
    ax.legend()
    ax.set_title("STT tiếng Việt: WER theo cấu hình")
    save(fig, "fig_stt_ladder")


def fig_quant(rs):
    order = ["F16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q3_K_M"]
    sel = [r for r in rs if r["exp_id"].startswith(("M0", "M1")) and r["llm_quant"] in order]
    if not sel:
        return
    fig, ax1 = plt.subplots(figsize=(7.5, 4))
    x = np.arange(len(order))
    models = sorted({r["llm_model"].rsplit("-", 1)[0] for r in sel})
    ax2 = None
    for i, m in enumerate(models):
        acc = {r["llm_quant"]: f(r["llm_bench_acc"]) for r in sel if r["llm_model"].startswith(m + "-") and f(r["llm_bench_acc"])}
        tok = {r["llm_quant"]: f(r["tok_s"]) for r in sel if r["llm_model"].startswith(m + "-") and f(r["tok_s"])}
        ax1.plot(x, [acc.get(q, np.nan) * 100 if acc.get(q) else np.nan for q in order], "o-", color=PALETTE[i % 6],
                 label=f"{m} — Global-MMLU vi")
        if tok:
            ax2 = ax2 or ax1.twinx()
            ax2.bar(x + (i - 0.5) * 0.3, [tok.get(q, 0) for q in order], 0.3, color=PALETTE[i % 6], alpha=0.3)
            ax2.set_ylabel("tokens/s (Pi 5, cột mờ)")
    ax1.axhline(25, ls=":", color="gray", lw=1)
    ax1.set_xticks(x, order)
    ax1.set_ylabel("độ chính xác (%)  — đường chấm = ngẫu nhiên")
    ax1.legend(fontsize=7, loc="lower left")
    ax1.set_title("Thang lượng tử hoá LLM (LoRA vi-voice)")
    save(fig, "fig_quant_ladder")


def e2e_runs():
    out = {}
    for p in sorted(glob.glob(str(results_dir() / "raw" / "*.json"))):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if "sessions" in d and "summary" in d:
            out[f"{d['row']['exp_id']} ({d['row']['os_cfg']})"] = [t for s in d["sessions"] for t in s["turns"] if not t.get("timeout")]
    return out


def fig_first_audio(runs):
    if not runs:
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, (k, turns) in enumerate(runs.items()):
        v = np.sort([t["metrics"]["first_audio_ms"] for t in turns if t["metrics"].get("first_audio_ms")])
        if len(v):
            ax.plot(v, np.arange(1, len(v) + 1) / len(v), label=k, color=PALETTE[i % len(PALETTE)])
    ax.axvline(1500, ls="--", color="gray", lw=1)
    ax.set_xlabel("ngừng nói → âm thanh đầu tiên (ms)")
    ax.set_ylabel("CDF")
    ax.legend(fontsize=7)
    ax.set_title("Thời gian tới âm thanh đầu tiên")
    save(fig, "fig_first_audio")


def fig_waterfall(runs):
    if not runs:
        return
    stages = [("endpoint", "VAD endpoint"), ("stt_final", "STT xong"), ("llm_first_token", "token đầu"),
              ("first_chunk", "câu đầu"), ("tts_first_done", "TTS câu đầu"), ("first_audio", "âm thanh đầu")]
    fig, ax = plt.subplots(figsize=(8, 1.4 + 0.5 * len(runs)))
    for i, (k, turns) in enumerate(runs.items()):
        prev = 0
        for j, (s, lab) in enumerate(stages):
            v = [t["t_rel_ms"].get(s) for t in turns if t["t_rel_ms"].get(s) is not None]
            if not v:
                continue
            m = float(np.median(v))
            ax.barh(i, max(m - prev, 0), left=prev, color=PALETTE[j % len(PALETTE)], label=lab if i == 0 else None)
            prev = max(prev, m)
    ax.set_yticks(range(len(runs)), list(runs), fontsize=7)
    ax.set_xlabel("ms sau khi người dùng ngừng nói (trung vị)")
    ax.legend(fontsize=7, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.28), frameon=False)
    save(fig, "fig_waterfall")


def fig_cyclictest():
    files = sorted(glob.glob(str(results_dir() / "os" / "*" / "cyclictest_llm.txt")))
    if not files:
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, p in enumerate(files):
        hist = []
        for line in open(p):
            parts = line.split()
            if len(parts) == 2 and parts[0].isdigit():
                hist.append((int(parts[0]), int(parts[1])))
        if hist:
            us, cnt = zip(*hist)
            ax.semilogy(us, np.maximum(cnt, 0.8), label=Path(p).parent.name.split("-")[0], color=PALETTE[i % len(PALETTE)])
    ax.set_xlabel("độ trễ đánh thức (µs), lõi audio, LLM chạy hết tải")
    ax.set_ylabel("số mẫu")
    ax.legend()
    ax.set_title("cyclictest O0–O4")
    save(fig, "fig_cyclictest")


def fig_training():
    files = sorted(glob.glob(str(ROOT / "results" / "training" / "*.json")))
    if not files:
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    for i, p in enumerate(files):
        h = json.load(open(p))["history"]
        tr = [(x["step"], x["loss"]) for x in h if "loss" in x]
        ev = [(x["step"], x["eval_loss"]) for x in h if "eval_loss" in x]
        n = Path(p).stem
        if tr:
            ax.plot(*zip(*tr), color=PALETTE[i % len(PALETTE)], alpha=0.6, label=f"{n} train")
        if ev:
            ax.plot(*zip(*ev), "o--", color=PALETTE[i % len(PALETTE)], label=f"{n} eval")
    ax.set_xlabel("step")
    ax.set_ylabel("loss")
    ax.legend(fontsize=7)
    ax.set_title("LoRA hỏi đáp bằng lời")
    save(fig, "fig_training")


if __name__ == "__main__":
    rs = rows()
    fig_stt(rs)
    fig_quant(rs)
    runs = e2e_runs()
    fig_first_audio(runs)
    fig_waterfall(runs)
    fig_cyclictest()
    fig_training()
