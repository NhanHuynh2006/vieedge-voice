#!/usr/bin/env python3
"""Strong phone vs weak phone, same inputs (07/11/2026): Galaxy Z Fold7 (Snapdragon 8 Elite) and TCL T506T (Helio P22).
Reads results/phone/fold7 and results/phone/tcl (the same 8 spoken questions, the same 24 spoken safety questions, the same
per-stage benchmark) and writes, for the updated report, poster and slides:
  figures/hai_may_latency.pdf   time to the first sound and to the real answer, every configuration, log scale
  figures/stages_v2.pdf         where the time goes, Pi 5 / Fold7 NPU / Fold7 CPU / TCL CPU
  figures/platform_v2.pdf       llama-bench, adds the TCL
  so_lieu_hai_may.tex           macros for the per-stage table
Nothing is typed in: every value comes from a raw run file.

  python docs/submission/make_hai_may.py
"""
from __future__ import annotations

import json
import re
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
F7, TC = ROOT / "results/phone/fold7", ROOT / "results/phone/tcl"
RAW, PHONE = ROOT / "results/raw", ROOT / "results/phone/raw"
OUT = ROOT / "docs/submission"
CM = 1 / 2.54
W = 8.0 * CM
BLUE, ORANGE, AQUA, YELLOW, GREY, INK, MUTED, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#a3a29a", "#0b0b0b", "#52514e", "#d93a3a"
plt.rcParams.update({
    "font.family": "Liberation Sans", "font.size": 9, "axes.labelsize": 9, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8.5,
    "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED, "axes.linewidth": 0.6,
    "xtick.color": MUTED, "ytick.color": INK, "axes.labelcolor": MUTED, "text.color": INK, "legend.frameon": False,
})
vn = lambda x, d=2: f"{x:.{d}f}".replace(".", ",")


def turns(d: Path, run: str) -> list[dict]:
    p = d / f"{run}.turns.jsonl"
    return [r for r in (json.loads(l) for l in open(p, encoding="utf-8") if l.strip()) if "fast" not in r["m"]]


def med(rows, key, scale=1000):
    v = [r["m"][key] for r in rows if key in r["m"]]
    return st.median(v) / scale if v else float("nan")


def stage(d: Path, run: str) -> dict:
    for line in open(d / f"{run}.log", encoding="utf-8"):
        if "STAGEBENCH" in line:
            return json.loads(line.split("STAGEBENCH ", 1)[1])
    raise SystemExit(f"no STAGEBENCH in {d / run}")


def load_s(d: Path, run: str) -> float:
    for line in open(d / f"{run}.log", encoding="utf-8"):
        m = re.search(r"TEST start .*load_s=([\d.]+)", line)
        if m:
            return float(m.group(1))
    return float("nan")


def meta(d: Path, run: str) -> dict:
    s = (d / f"{run}.meta").read_text()
    return {k: float(v.replace(",", ".")) for k, v in re.findall(r"(\w+)=([\d.,]+)", s)}


def bench(path: Path) -> dict:
    """llama-bench markdown table -> {(model, test): tokens/s}."""
    out = {}
    for line in open(path, encoding="utf-8"):
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) > 6 and (c[-2].startswith("pp") or c[-2].startswith("tg")):
            out[(c[0], c[-2])] = float(c[-1].split("±")[0])
    return out


def turns_pi(name):
    d = json.loads((RAW / f"{name}.json").read_text())
    return [t for s in d["sessions"] for t in s["turns"]]


def main() -> None:
    # ---------------------------------------------------------------- latency of every configuration (same 8 questions)
    cfg = [
        ("Fold7 NPU, 2 tỉ, tra cứu", F7, "qa_2b_npu_rag", BLUE),
        ("Fold7 NPU, 2 tỉ", F7, "qa_2b_npu_norag", BLUE),
        ("Fold7 NPU, 0,8 tỉ", F7, "qa_08b_npu_norag", BLUE),
        ("Fold7 CPU, 0,8 tỉ", F7, "qa_08b_cpu_norag", BLUE),
        ("Fold7 CPU, 0,8 tỉ, tra cứu", F7, "qa_08b_cpu_rag", BLUE),
        ("Fold7 CPU, 2 tỉ", F7, "qa_2b_cpu_norag", BLUE),
        ("TCL CPU, 0,8 tỉ", TC, "qa_08b_cpu_norag", ORANGE),
        ("TCL CPU, 0,8 tỉ, tra cứu", TC, "qa_08b_cpu_rag_h0", ORANGE),
        ("TCL CPU, 2 tỉ", TC, "qa_2b_cpu_norag", ORANGE),
    ]
    rows = []
    for lbl, name in [("Pi 5: 0,8 tỉ, CPU", "YO-LAT-base-20261013-131838"), ("Pi 5: + “Dạ.”", "YO-LAT-ack-20261013-132117")]:
        m = json.loads((RAW / f"{name}.json").read_text())["summary"]["metrics"]
        rows.append((lbl, m["first_audio_ms"]["p50"] / 1000, m["answer_audio_ms"]["p50"] / 1000, float("nan"), float("nan"), m["answer_audio_ms"]["n"], GREY))
    for lbl, d, run, col in cfg:
        t = turns(d, run)
        rows.append((lbl, med(t, "first_audio_ms"), med(t, "answer_audio_ms"), med(t, "llm_tok_s", 1), med(t, "ttft_ms"), len(t), col))
    fig, ax = plt.subplots(figsize=(W, 6.8 * CM))
    for i, (l, f, a, tok, ttft, n, col) in enumerate(rows[::-1]):
        ax.plot([f, a], [i, i], color=GREY, lw=1.1, zorder=1)
        ax.scatter(f, i, s=24, color=GREY, marker="o", zorder=2, edgecolor="white", linewidth=0.5, label="Phản hồi đầu (“Dạ.”)" if i == 0 else None)
        ax.scatter(a, i, s=28, color=col, marker="s", zorder=2, edgecolor="white", linewidth=0.5)
        ax.text(a * 1.12, i, vn(a, 1), va="center", fontsize=8.5)
    ax.scatter([], [], s=28, color=GREY, marker="s", label="Nội dung trả lời, Pi 5")
    ax.scatter([], [], s=28, color=BLUE, marker="s", label="Nội dung trả lời, Fold7")
    ax.scatter([], [], s=28, color=ORANGE, marker="s", label="Nội dung trả lời, TCL")
    ax.set_xscale("log"); ax.set_xlim(0.2, 80)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:g}".replace(".", ",")))
    ax.set_xticks([0.3, 1, 3, 10, 30])
    ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
    ax.set_xlabel("giây kể từ khi người dùng nói xong (trung vị, thang log)")
    ax.grid(axis="x", color="#e6e5df", lw=0.5); ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(-0.62, 1.0), handletextpad=0.1, columnspacing=0.8, borderaxespad=0.1)
    fig.savefig(OUT / "figures/hai_may_latency.pdf", bbox_inches="tight", pad_inches=0.015); plt.close(fig)

    # ---------------------------------------------------------------- stages: Pi and Fold7 NPU from the original figure, plus two CPUs
    def stg(d, run):
        t = turns(d, run)
        v = [(r["m"]["llm_request_ms"], r["m"]["ttft_ms"], r["m"]["first_chunk_ms"] - r["m"]["llm_request_ms"] - r["m"]["ttft_ms"],
              r["m"]["answer_audio_ms"] - r["m"]["first_chunk_ms"]) for r in t if all(k in r["m"] for k in ("llm_request_ms", "ttft_ms", "first_chunk_ms", "answer_audio_ms"))]
        return np.median(np.array(v), axis=0) / 1000
    pi = []
    for t in turns_pi("CMP2-YOCTO-quiet-20261021-060040"):
        r = t["t_rel_ms"]
        if r.get("llm_first_token") and r.get("answer_audio"):
            pi.append((r["llm_request"], r["llm_first_token"] - r["llm_request"], r["first_chunk"] - r["llm_first_token"], r["answer_audio"] - r["first_chunk"]))
    bars = [("Pi 5 CPU, 0,8 tỉ", np.median(np.array(pi), axis=0) / 1000), ("Fold7 NPU, 0,8 tỉ", stg(F7, "qa_08b_npu_norag")), ("Fold7 CPU, 0,8 tỉ", stg(F7, "qa_08b_cpu_norag")), ("TCL CPU, 0,8 tỉ", stg(TC, "qa_08b_cpu_norag"))]
    labels = ["Ngắt câu + STT", "LLM: token đầu", "LLM: đủ câu đầu", "TTS: câu đầu"]
    cols = [BLUE, ORANGE, AQUA, YELLOW]
    fig, ax = plt.subplots(figsize=(W, 4.2 * CM))
    for y, (name, s) in zip(range(len(bars))[::-1], bars):
        left = 0
        for v, c, l in zip(s, cols, labels):
            ax.barh(y, max(v - 0.02, 0.001), left=left, color=c, height=0.62, label=l if y == len(bars) - 1 else None)
            if v > 0.9:
                ax.text(left + v / 2, y, vn(v, 1), ha="center", va="center", color="white" if c == BLUE else INK, fontsize=8)
            left += v
        ax.text(left + 0.15, y, vn(left, 1), va="center", fontsize=8.5)
    ax.set_yticks(range(len(bars))[::-1], [b[0] for b in bars])
    ax.set_xlabel("giây kể từ khi người dùng nói xong (trung vị từng chặng, tắt tra cứu)")
    ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
    ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(-0.36, 1.0), handlelength=0.9, columnspacing=0.8, handletextpad=0.4, borderaxespad=0.1)
    fig.savefig(OUT / "figures/stages_v2.pdf", bbox_inches="tight", pad_inches=0.015); plt.close(fig)

    # ---------------------------------------------------------------- llama-bench (pp128 / tg64), adds the TCL
    tb, fb = bench(TC / "llama_bench.md"), bench(F7 / "llama_bench_cpu_t4.md")
    def get(b, model_has, test):
        v = [x for (m, tt), x in b.items() if model_has in m and tt == test]
        return v[0] if v else float("nan")
    tcl = lambda m, t: get(tb, m, t)
    # CPU rows: 4 threads on both phones (llama-bench -p 128 -n 64 -r 2 -t 4); NPU rows and Pi from the 21/10 runs
    labs = ["Pi 5 CPU, 0,8 tỉ", "TCL CPU, 0,8 tỉ", "TCL CPU, 2 tỉ", "Fold7 CPU, 0,8 tỉ", "Fold7 CPU, 2 tỉ", "Fold7 NPU, 0,8 tỉ", "Fold7 NPU, 2 tỉ"]
    pp = [125.7, tcl("0.8B", "pp128"), tcl("2B", "pp128"), get(fb, "0.8B", "pp128"), get(fb, "2B", "pp128"), 2011.7, 1409.5]
    tg = [18.1, tcl("0.8B", "tg64"), tcl("2B", "tg64"), get(fb, "0.8B", "tg64"), get(fb, "2B", "tg64"), 63.2, 32.9]
    c = [GREY, ORANGE, ORANGE, GREY, GREY, BLUE, BLUE]
    fig, ax = plt.subplots(1, 2, figsize=(W, 4.6 * CM), sharey=True, gridspec_kw={"wspace": 0.22})
    for a, v, t, xm in zip(ax, (pp, tg), ("Xử lý prompt", "Sinh token"), (2900, 125)):
        y = np.arange(len(v))[::-1]
        a.barh(y, v, color=c, height=0.66)
        for yy, x in zip(y, v):
            a.text(x + xm * 0.025, yy, f"{x:,.0f}".replace(",", ".") if x >= 20 else vn(x, 1), va="center", fontsize=8.5)
        a.set_title(t + " (token/s)", fontsize=8.5, loc="left", fontweight="bold")
        a.set_xlim(0, xm); a.set_xticks([]); a.spines["bottom"].set_visible(False); a.tick_params(axis="y", length=0)
    ax[0].set_yticks(np.arange(len(labs))[::-1], labs)
    fig.savefig(OUT / "figures/platform_v2.pdf", bbox_inches="tight", pad_inches=0.015); plt.close(fig)

    # ---------------------------------------------------------------- per-stage table
    sf, sc = stage(F7, "stagebench"), stage(TC, "stagebench")
    safe = {k: json.load(open(d / f"{r}.score.json", encoding="utf-8")) for k, d, r in (("f", F7, "safety_v45_gps_build"), ("t", TC, "safety_v45_08b_cpu"))}
    mac = {
        "hmAsrF": vn(sf["asr_ms_per_utt"], 0), "hmAsrT": vn(sc["asr_ms_per_utt"], 0),
        "hmAsrRtfF": vn(sf["asr_rtf"], 3), "hmAsrRtfT": vn(sc["asr_rtf"], 3),
        "hmTtsF": vn(sf["tts_ms_per_sentence"], 0), "hmTtsT": vn(sc["tts_ms_per_sentence"], 0),
        "hmTtsRtfF": vn(sf["tts_rtf"], 3), "hmTtsRtfT": vn(sc["tts_rtf"], 3),
        "hmSafeMsF": vn(sf["safety_ms_per_q"], 1), "hmSafeMsT": vn(sc["safety_ms_per_q"], 1),
        "hmPpF": vn(get(fb, "0.8B", "pp128"), 0), "hmPpT": vn(tcl("0.8B", "pp128"), 1), "hmTgF": vn(get(fb, "0.8B", "tg64"), 1), "hmTgT": vn(tcl("0.8B", "tg64"), 1),
        "hmPpBF": vn(get(fb, "2B", "pp128"), 0), "hmPpBT": vn(tcl("2B", "pp128"), 1), "hmTgBF": vn(get(fb, "2B", "tg64"), 1), "hmTgBT": vn(tcl("2B", "tg64"), 1),
        "hmLoadF": vn(load_s(F7, "qa_08b_cpu_norag"), 0), "hmLoadT": vn(load_s(TC, "qa_08b_cpu_norag"), 0),
        "hmSafeF": vn(safe["f"]["safety_first_audio_ms"]["p50"] / 1000), "hmSafeT": vn(safe["t"]["safety_first_audio_ms"]["p50"] / 1000),
        "hmSafeOkF": f"{safe['f']['correct']}/{safe['f']['n']}", "hmSafeOkT": f"{safe['t']['correct']}/{safe['t']['n']}",
    }
    for key, d in (("F", F7), ("T", TC)):
        t = turns(d, "qa_08b_cpu_norag")
        mac[f"hmAns{key}"] = vn(med(t, "answer_audio_ms"), 1); mac[f"hmFirst{key}"] = vn(med(t, "first_audio_ms"))
        mac[f"hmTtft{key}"] = vn(med(t, "ttft_ms"), 1)
        mac[f"hmPss{key}"] = vn(meta(d, "qa_08b_cpu_norag").get("peak_pss_kb", 0) / 1e6, 1)
    mac["hmSpeedup"] = vn(med(turns(TC, "qa_08b_cpu_norag"), "answer_audio_ms") / med(turns(F7, "qa_08b_cpu_norag"), "answer_audio_ms"), 0)
    lines = ["% Sinh tự động bởi make_hai_may.py; không sửa tay."] + [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in mac.items()]
    (OUT / "so_lieu_hai_may.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    for r in rows:
        print(f"{r[0]:<28} first {r[1]:.2f}  answer {r[2]:.2f}  tok/s {r[3]:.1f}  ttft {r[4]:.2f}  n={r[5]}")
    for name, s in bars:
        print(name, np.round(s, 2), round(float(s.sum()), 2))


if __name__ == "__main__":
    main()
