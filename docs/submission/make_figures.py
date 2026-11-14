#!/usr/bin/env python3
"""Vector figures and statistics for the paper and the poster. All series come from raw result files."""
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
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "submission" / "figures"
PHONE = ROOT / "results" / "phone" / "raw"
RAW = ROOT / "results" / "raw"
CM = 1 / 2.54
W = 8.0 * CM  # one column of the paper
BLUE, ORANGE, AQUA, YELLOW, GREY, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#a3a29a", "#0b0b0b", "#52514e"
plt.rcParams.update({
    "font.family": "Liberation Sans", "font.size": 9, "axes.labelsize": 9, "axes.titlesize": 9, "xtick.labelsize": 9, "ytick.labelsize": 9,
    "legend.fontsize": 9, "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
    "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.color": MUTED, "ytick.color": INK,
    "axes.labelcolor": MUTED, "text.color": INK, "axes.titlelocation": "left", "axes.titleweight": "bold", "legend.frameon": False,
})
vn = lambda x, d=2: f"{x + 1e-9:.{d}f}".replace(".", ",")
comma = matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:g}".replace(".", ","))
LOG: list[str] = []


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight", pad_inches=0.015)
    plt.close(fig)


def turns_pi(name):
    d = json.loads((RAW / f"{name}.json").read_text())
    return [t for s in d["sessions"] for t in s["turns"]]


def turns_phone(tag):
    return [t for t in json.loads((PHONE / f"phone_{tag}.json").read_text())["turns"] if "fast" not in t["m"]]


def boot(v, n=10000, seed=1):
    r = np.random.default_rng(seed)
    v = np.asarray(v, float)
    m = np.median(r.choice(v, (n, len(v))), axis=1)
    return np.percentile(m, [2.5, 97.5])


def report(label, v):
    lo, hi = boot(v)
    LOG.append(f"{label}: n={len(v)} p50={np.median(v):.0f} p95={np.percentile(v, 95):.0f} CI95(p50)=[{lo:.0f},{hi:.0f}] ms")


# ---- statistics
for lbl, tag in [("A 5w/3t", "A_w5_t3"), ("B 3w/3t", "B_w3_t3"), ("C 3w/4t", "C_w3_t4"), ("D 3w/4t/300", "D_w3_t4_ep30"), ("2B base", "2B_NPU_vais"),
                 ("2B ack", "2B_NPU_vais_ack"), ("xlow", "2B_NPU_xlow"), ("xlow ack ep300", "2B_NPU_xlow_ack_ep300"), ("0.8 GPU", "08B_GPU_vais"), ("0.8 NPU", "08B_NPU_vais"),
                 ("2B GPU", "2B_GPU_vais"), ("norag", "2Bimx_NPU_norag"), ("rag", "2Bimx_NPU_rag")]:
    t = turns_phone(tag)
    cfg = json.loads((PHONE / f"phone_{tag}.json").read_text())["cfg"]
    report(lbl + " answer", [x["m"]["answer_audio_ms"] for x in t if x["m"].get("answer_audio_ms")])
    report(lbl + " first", [x["m"]["first_audio_ms"] for x in t if x["m"].get("first_audio_ms")])
    LOG.append(f"   cfg={cfg}")
qs = {}
for os_, n in [("yocto", "CMP2-YOCTO-quiet-20261021-060040"), ("pios", "CMP-PIOS-O0-v2-quiet-20261021-141132")]:
    for t in turns_pi(n):
        qs.setdefault(t.get("turn_id"), {})[os_] = t["metrics"]["answer_audio_ms"]
    report(os_ + " answer", [t["metrics"]["answer_audio_ms"] for t in turns_pi(n) if t["metrics"].get("answer_audio_ms")])
pairs = [(v["yocto"], v["pios"]) for v in qs.values() if v.get("yocto") and v.get("pios")]
a, b = np.array(pairs).T
d = a - b
LOG.append(f"paired yocto-pios: n={len(d)} median diff={np.median(d):.0f} ms CI={boot(d)} wilcoxon p={stats.wilcoxon(a, b).pvalue:.3f}")
for os_, n in [("yocto loaded", "CMP2-YOCTO-loaded-20261021-060709"), ("pios loaded", "CMP-PIOS-O0-v2-loaded-20261021-141749")]:
    report(os_ + " answer", [t["metrics"]["answer_audio_ms"] for t in turns_pi(n) if t["metrics"].get("answer_audio_ms")])

# turns that really went through the LLM (the others were answered "please repeat" by the confidence gate)
qq = {}
for os_, n in [("yocto", "CMP2-YOCTO-quiet-20261021-060040"), ("pios", "CMP-PIOS-O0-v2-quiet-20261021-141132")]:
    tt = turns_pi(n)
    LOG.append(f"{os_} questions: " + " | ".join(str(x.get("question"))[:24] for x in tt[:4]))
    report(os_ + " answer LLM-only", [x["metrics"]["answer_audio_ms"] for x in tt if x["metrics"].get("ttft_ms")])
    for x in tt:
        qq.setdefault(x["turn_id"], {})[os_] = x["metrics"]["answer_audio_ms"] if x["metrics"].get("ttft_ms") else None

pr = [(v["yocto"], v["pios"]) for v in qq.values() if v.get("yocto") and v.get("pios")]
a2, b2 = np.array(pr).T
LOG.append(f"paired LLM-only n={len(a2)} median diff={np.median(a2 - b2):.0f} CI={boot(a2 - b2)} wilcoxon p={stats.wilcoxon(a2, b2).pvalue:.3f}")

# ---- Fig: where the time goes
def stages_pi():
    rows = []
    for t in turns_pi("CMP2-YOCTO-quiet-20261021-060040"):
        r = t["t_rel_ms"]
        if r.get("llm_first_token") and r.get("answer_audio"):
            rows.append((r["llm_request"], r["llm_first_token"] - r["llm_request"], r["first_chunk"] - r["llm_first_token"], r["answer_audio"] - r["first_chunk"]))
    return rows


def stages_phone():
    rows = []
    for t in turns_phone("C_w3_t4"):
        m = t["m"]
        ft = m["llm_request_ms"] + m["ttft_ms"]
        rows.append((m["llm_request_ms"], m["ttft_ms"], m["first_chunk_ms"] - ft, m["answer_audio_ms"] - m["first_chunk_ms"]))
    return rows


sp, sf = np.median(stages_pi(), axis=0) / 1000, np.median(stages_phone(), axis=0) / 1000
LOG.append(f"stages Pi n={len(stages_pi())}: {np.round(sp, 3)} sum={sp.sum():.3f}; Fold7 n={len(stages_phone())}: {np.round(sf, 3)} sum={sf.sum():.3f}")
labels = ["Ngắt câu, STT, tra cứu", "LLM ra token đầu", "LLM ra đủ câu đầu", "TTS câu đầu"]
cols = [BLUE, ORANGE, AQUA, YELLOW]
fig, ax = plt.subplots(figsize=(W, 3.5 * CM))
for y, s in zip((1, 0), (sp, sf)):
    left = 0
    for v, c, l in zip(s, cols, labels):
        ax.barh(y, v - 0.012, left=left, color=c, height=0.62, label=l if y == 1 else None)
        if v > 0.25:
            ax.text(left + v / 2, y, vn(v), ha="center", va="center", color="white" if c in (BLUE,) else INK, fontsize=9)
        left += v
ax.set_yticks([1, 0], ["Pi 5 Yocto-RT", "Fold7 NPU"])
ax.set_xlabel("giây từ lúc nói xong (trung vị từng chặng)")
ax.set_xlim(0, 2.6)
ax.xaxis.set_major_formatter(comma)
ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False)
ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(-0.28, 1.0), handlelength=0.9, columnspacing=1.0, handletextpad=0.4, borderaxespad=0.1)
save(fig, "stages")

# ---- Fig: latency ablation
rows = []
for lbl, name in [("Pi: mặc định", "YO-LAT-base-20261013-131838"), ("Pi: + “Dạ.”", "YO-LAT-ack-20261013-132117"), ("Pi: + 300 ms, 3 từ", "YO-LAT-ack-ep300-w3-20261013-132355")]:
    m = json.loads((RAW / f"{name}.json").read_text())["summary"]["metrics"]
    rows.append((lbl, m["first_audio_ms"]["p50"] / 1000, m["answer_audio_ms"]["p50"] / 1000))
    LOG.append(f"{name}: n={m['answer_audio_ms']['n']} first p50/p95={m['first_audio_ms']['p50']:.0f}/{m['first_audio_ms']['p95']:.0f} answer={m['answer_audio_ms']['p50']:.0f}/{m['answer_audio_ms']['p95']:.0f}")
for lbl, tag in [("Fold7: 2 tỉ, NPU", "2B_NPU_vais"), ("Fold7: + “Dạ.”", "2B_NPU_vais_ack"), ("Fold7: 3 từ, tra cứu", "C_w3_t4")]:
    t = turns_phone(tag)
    rows.append((lbl, st.median(x["m"]["first_audio_ms"] for x in t) / 1000, st.median(x["m"]["answer_audio_ms"] for x in t) / 1000))
fig, ax = plt.subplots(figsize=(W, 5.0 * CM))
for i, (l, f, r) in enumerate(rows[::-1]):
    ax.plot([f, r], [i, i], color=GREY, lw=1.2, zorder=1)
    ax.scatter(f, i, s=30, color=ORANGE, marker="o", zorder=2, edgecolor="white", linewidth=0.5, label="Tiếng đầu nghe thấy" if i == 0 else None)
    ax.scatter(r, i, s=30, color=BLUE, marker="s", zorder=2, edgecolor="white", linewidth=0.5, label="Câu trả lời thật" if i == 0 else None)
    ax.text(max(f, r) + 0.07, i, vn(r), va="center", fontsize=9)
ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
ax.set_xlim(0, 3.0)
ax.xaxis.set_major_formatter(comma)
ax.set_xlabel("giây từ lúc nói xong (p50)")
ax.grid(axis="x", color="#e6e5df", lw=0.5)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
ax.spines["left"].set_visible(False)
ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(-0.45, 1.0), handletextpad=0.1, columnspacing=1.0, borderaxespad=0.1)
save(fig, "latency")

# ---- Fig: platforms (llama-bench, results/phone/fold7_llama_bench + bigger_models)
labs = ["Pi 5 CPU, 0,8 tỉ", "Fold7 CPU, 0,8 tỉ", "Fold7 GPU, 0,8 tỉ", "Fold7 NPU, 0,8 tỉ", "Fold7 NPU, 1,5 tỉ", "Fold7 NPU, 2 tỉ"]
pp = [125.7, 634.9, 1008.9, 2011.7, 2120.8, 1409.5]
tg = [18.1, 90.7, 70.0, 63.2, 45.9, 32.9]
c = [GREY, GREY, GREY, BLUE, BLUE, BLUE]
fig, ax = plt.subplots(1, 2, figsize=(W, 4.2 * CM), sharey=True, gridspec_kw={"wspace": 0.12})
for a, v, t, xm in zip(ax, (pp, tg), ("Nạp prompt", "Sinh token"), (2900, 125)):
    y = np.arange(len(v))[::-1]
    a.barh(y, v, color=c, height=0.66)
    for yy, x in zip(y, v):
        a.text(x + xm * 0.025, yy, f"{x:,.0f}".replace(",", "."), va="center", fontsize=9)
    a.set_title(t + ", token/s", fontsize=9)
    a.set_xlim(0, xm)
    a.set_xticks([])
    a.spines["bottom"].set_visible(False)
    a.tick_params(axis="y", length=0)
ax[0].set_yticks(np.arange(len(labs))[::-1], labs)
save(fig, "platform")

# ---- Fig: jitter tail
def hist(p):
    return [(int(m[1]), int(m[2])) for l in open(p) if (m := re.match(r"^(\d+)\s+(\d+)", l))]


fig, ax = plt.subplots(figsize=(W, 4.0 * CM))
for n, dd, col, ls in [("Pi OS: đỉnh 127 µs", "PIOS-O0-v2-20261021-141749", ORANGE, "-"), ("Yocto-RT: đỉnh 92 µs", "YOCTO-RT-O4-20261013-124501", BLUE, "-")]:
    h = np.array(hist(ROOT / "results" / "jitter_long" / dd / "cyclictest_load.txt"), float)
    keep = h[:, 1] > 0
    us, cnt = h[keep, 0], h[keep, 1]
    sf_ = 1 - np.cumsum(cnt) / cnt.sum()
    sf_ = np.maximum(sf_, 0.5 / cnt.sum())
    ax.semilogy(us, sf_, color=col, lw=1.4, ls=ls, label=n)
    LOG.append(f"jitter {n}: samples={cnt.sum():.0f} max={us.max():.0f}")
ax.set_xlabel("độ trễ lập lịch trên lõi 3 (µs)")
ax.set_ylabel("tỉ lệ mẫu vượt ngưỡng")
ax.set_xlim(0, 135)
ax.grid(color="#e6e5df", lw=0.5)
ax.set_axisbelow(True)
ax.legend(loc="upper right", handlelength=1.4)
save(fig, "jitter")

# ---- Fig: soak
soak = json.loads((PHONE / "phone_soak.json").read_text())
lg = soak["log"]
ts = np.array([e[0] for e in lg], float)
T = np.array([e[2] for e in lg], float)
LOG.append(f"soak log sample {lg[0][:3]}, keys {list(soak)}")
tm = [t["m"] for t in soak["turns"]]
toks = np.array([m["llm_tok_s"] for m in tm if m.get("llm_tok_s")])
n4 = len(toks) // 4
LOG.append(f"soak tok/s n={len(toks)} q1={np.median(toks[:n4]):.1f} q4={np.median(toks[-n4:]):.1f} std={toks.std():.2f}")
fig, ax = plt.subplots(figsize=(W, 3.6 * CM))
ax.plot(ts, T[:, 3], color=BLUE, lw=1.3, label="NPU (HVX)")
ax.plot(ts, T[:, 0], color=ORANGE, lw=1.3, label="CPU")
ax.set_xlabel("giây")
ax.set_ylabel("°C")
ax.grid(axis="y", color="#e6e5df", lw=0.5)
ax.set_axisbelow(True)
ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1.0), borderaxespad=0.1)
save(fig, "soak")
(OUT / "stats.txt").write_text("\n".join(LOG) + "\n")
print("\n".join(LOG))
