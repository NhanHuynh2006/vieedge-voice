#!/usr/bin/env python3
"""Figures for the report and the slides, drawn from the raw result files (no hand-typed series except the Pi latency rows noted below)."""
from __future__ import annotations

import csv
import json
import re
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "report" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
INK, MUTED, ACC, TEAL, AMB, GREY, RED = "#13202b", "#566587", "#3158e8", "#0f7b6c", "#b4541a", "#9aa7bd", "#c0392b"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "text.color": INK, "axes.titleweight": "bold",
                     "figure.facecolor": "white", "axes.facecolor": "white", "savefig.dpi": 150})


def bars(ax, labels, vals, colors, fmt="{:.0f}", ylim=None, hline=None):
    b = ax.bar(labels, vals, color=colors)
    for r, v in zip(b, vals):
        ax.text(r.get_x() + r.get_width() / 2, r.get_height() * 1.01, fmt.format(v), ha="center", va="bottom", fontsize=10, fontweight="bold")
    ax.set_ylim(0, ylim or max(vals) * 1.2)
    if hline:
        ax.axhline(hline[0], color=RED, ls="--", lw=1.2)
        ax.text(len(vals) - 0.5, hline[0], hline[1], color=RED, ha="right", va="bottom", fontsize=9)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name)
    plt.close(fig)
    print("wrote", name)


# 1. WER
fig, ax = plt.subplots(1, 2, figsize=(10, 3.8))
bars(ax[0], ["Whisper-tiny\ngốc", "PhoWhisper-tiny\nINT8", "Zipformer-vi\n(CPU)"], [0.603, 0.158, 0.041], [GREY, GREY, TEAL], "{:.3f}")
ax[0].set_title("WER trên VIVOS+FLEURS / VIVOS (thấp hơn là tốt)\nWhisper gốc: 600 câu; hai cột sau: VIVOS", fontsize=10)
bars(ax[1], ["PhoWhisper-tiny\nSNR 5 dB", "Zipformer-vi\nSNR 5 dB"], [0.224, 0.059], [GREY, TEAL], "{:.3f}")
ax[1].set_title("WER khi trộn tiếng ồn 5 dB (VIVOS)", fontsize=10)
save(fig, "fig_wer.png")

# 2. Hailo cosine
fig, ax = plt.subplots(figsize=(6.2, 3.8))
bars(ax, ["INT8\n(không fine-tune)", "INT8 + fine-tune\nlượng tử (GPU, 6 epoch)"], [0.842, 0.655], [AMB, AMB], "{:.3f}", 1.05, (0.9, "ngưỡng dùng được 0,9"))
ax.set_title("Hailo-8L: độ giống encoder lượng tử so với ONNX\n(cosine, 100 câu VIVOS)", fontsize=10)
save(fig, "fig_hailo_cosine.png")

# 3. Pi latency (rows from results/compare/SUMMARY.md, Pi Yocto-RT, 12 turns, RAG off)
fig, ax = plt.subplots(figsize=(9.5, 3.9))
cfg = ["Mặc định", "+ \"Dạ.\"", "+ endpoint 300 ms\n+ câu đầu 3 từ", "Lệnh có sẵn\n(đường nhanh)"]
first = [2.45, 0.53, 0.43, 0.52]
real = [2.36, 2.44, 1.95, 0.52]
x = np.arange(len(cfg)); w = 0.38
ax.bar(x - w / 2, first, w, color=TEAL, label="tiếng đầu nghe thấy")
ax.bar(x + w / 2, real, w, color=ACC, label="câu trả lời thật bắt đầu")
for i in range(len(cfg)):
    ax.text(x[i] - w / 2, first[i] + 0.04, f"{first[i]:.2f}", ha="center", fontsize=9, fontweight="bold")
    ax.text(x[i] + w / 2, real[i] + 0.04, f"{real[i]:.2f}", ha="center", fontsize=9, fontweight="bold")
ax.set_xticks(x, cfg); ax.set_ylabel("giây (p50)"); ax.legend(frameon=False); ax.set_ylim(0, 2.9)
ax.set_title("Pi 5 Yocto-RT: từ lúc nói xong tới khi nghe thấy tiếng (12–16 lượt, tắt tra cứu)", fontsize=10)
save(fig, "fig_latency_pi.png")

# 4. Phone latency from the raw matrix files
raw = ROOT / "results" / "phone" / "raw"
def med(tag, key, only_llm=True):
    d = json.loads((raw / f"phone_{tag}.json").read_text())
    v = [t["m"][key] for t in d["turns"] if t["m"].get(key) and (not only_llm or "fast" not in t["m"])]
    return st.median(v) if v else float("nan")
rows = [("2B NPU\ngiọng chuẩn", "2B_NPU_vais"), ("+ \"Dạ.\"", "2B_NPU_vais_ack"), ("giọng nhanh\n+ \"Dạ.\" + 300 ms", "2B_NPU_xlow_ack_ep300"),
        ("0,8B GPU", "08B_GPU_vais"), ("2B GPU", "2B_GPU_vais"), ("3 từ + 4 luồng\n+ tra cứu + \"Dạ.\"", "C_w3_t4")]
fig, ax = plt.subplots(figsize=(11, 3.9))
x = np.arange(len(rows)); w = 0.38
f = [med(t, "first_audio_ms") / 1000 for _, t in rows]; r = [med(t, "answer_audio_ms") / 1000 for _, t in rows]
ax.bar(x - w / 2, f, w, color=TEAL, label="tiếng đầu nghe thấy"); ax.bar(x + w / 2, r, w, color=ACC, label="câu trả lời thật bắt đầu")
for i in range(len(rows)):
    ax.text(x[i] - w / 2, f[i] + 0.03, f"{f[i]:.2f}", ha="center", fontsize=9, fontweight="bold"); ax.text(x[i] + w / 2, r[i] + 0.03, f"{r[i]:.2f}", ha="center", fontsize=9, fontweight="bold")
ax.set_xticks(x, [a for a, _ in rows], fontsize=9); ax.set_ylabel("giây (p50)"); ax.legend(frameon=False); ax.set_ylim(0, 2.3)
ax.set_title("Galaxy Z Fold7: ứng dụng chạy trọn vòng trên máy (12 câu hỏi tổng hợp, từ lúc nói xong)", fontsize=10)
save(fig, "fig_latency_phone.png")

# 5. Jitter: 30-minute tail
def hist(path):
    h = []
    for l in open(path):
        m = re.match(r"^(\d+)\s+(\d+)", l)
        if m:
            h.append((int(m.group(1)), int(m.group(2))))
    return h
fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.9))
mx = {}
for name, d, col in [("Pi OS nguyên bản", "PIOS-O0-v2-20261021-141749", GREY), ("Yocto-RT", "YOCTO-RT-O4-20261013-124501", TEAL)]:
    h = hist(ROOT / "results" / "jitter_long" / d / "cyclictest_load.txt")
    us = np.array([a for a, _ in h]); c = np.array([b for _, b in h], dtype=float)
    cdf = np.cumsum(c) / c.sum(); nz = c > 0
    ax[0].semilogy(us[nz], (1 - cdf[nz]) + 1e-8, color=col, label=name, lw=2)
    mx[name] = us[nz].max()
ax[0].set_xlabel("độ trễ lập lịch lõi 3 (µs)"); ax[0].set_ylabel("tỉ lệ mẫu vượt ngưỡng"); ax[0].set_xlim(0, 140); ax[0].legend(frameon=False)
ax[0].set_title("Đuôi jitter, tải nặng, 30 phút (1,8 triệu mẫu)", fontsize=10)
bars(ax[1], ["Pi OS\n5 phút", "Yocto-RT\n5 phút", "Pi OS\n30 phút", "Yocto-RT\n30 phút"], [105, 85, 127, 92], [GREY, TEAL, GREY, TEAL], "{:.0f} µs")
ax[1].set_title("Đỉnh jitter (max) khi tải nặng", fontsize=10)
save(fig, "fig_jitter.png")

# 6. OS comparison final numbers
fig, ax = plt.subplots(1, 3, figsize=(11.5, 3.7))
bars(ax[0], ["Pi OS", "Yocto-RT"], [33, 13], [GREY, TEAL], "{:.0f} µs"); ax[0].set_title("Đỉnh jitter khi rảnh (5 phút)", fontsize=10)
bars(ax[1], ["Pi OS\n(O1)", "Yocto-RT"], [490, 285], [GREY, TEAL], "{:.0f} MB"); ax[1].set_title("RAM sau khởi động", fontsize=10)
bars(ax[2], ["Pi OS", "Yocto-RT"], [1.60, 2.02], [GREY, TEAL], "{:.2f} s"); ax[2].set_title("Câu trả lời thật bắt đầu (p50, yên, Q4_0)", fontsize=10)
save(fig, "fig_os_compare.png")

# 7. Phone power from the raw log
rows_p = list(csv.DictReader(open(raw / "power_20261027.csv")))
t = np.array([int(r["t_s"]) for r in rows_p]); pw = np.array([abs(int(r["current_ua"])) * int(r["voltage_mv"]) / 1e9 for r in rows_p])
ph = np.array([r["phase"] for r in rows_p])
k = 15
sm = np.convolve(pw, np.ones(k) / k, mode="same")
fig, ax = plt.subplots(figsize=(10, 3.8))
ax.set_ylim(0, 7)
ax.plot(t, pw, color=GREY, lw=0.6, alpha=0.7, label="mẫu mỗi giây")
ax.plot(t, sm, color=ACC, lw=2, label="trung bình trượt 15 s")
sw = np.where(ph == "assistant")[0][0]
ax.axvline(t[sw], color=MUTED, ls=":"); ax.text(t[sw] + 3, 6.4, "bắt đầu chạy trợ lý", fontsize=9, color=MUTED)
ax.axhline(3.2, color=AMB, ls="--", lw=1.2); ax.text(t[-1], 5.3, "Pi 5 ≈ 3,2 W (chỉ bo mạch, đường chấm cam)", ha="right", fontsize=9, color=AMB)
ax.axhline(2.2, color=TEAL, ls="--", lw=1.2); ax.text(t[-1], 1.0, "2,2 W: ước tính theo mức pin (thô, ±1 %)\n3,1 W: trung bình dòng điện cắt 5 %", ha="right", va="top", fontsize=9, color=TEAL)
ax.set_xlabel("giây từ lúc rút sạc"); ax.set_ylabel("công suất (W)"); ax.legend(frameon=False, loc="upper right", bbox_to_anchor=(1, 0.88))
ax.set_title("Fold7 chạy bằng pin: 2B trên NPU + tra cứu + \"Dạ.\", 78 lượt, màn hình sáng", fontsize=10)
save(fig, "fig_power.png")

# 8. Soak: temperatures
soak = json.loads((raw / "phone_soak.json").read_text())
lg = soak["log"]
ts = [e[0] for e in lg]; temps = np.array([e[2] for e in lg])
fig, ax = plt.subplots(figsize=(10, 3.8))
for i, (n, c) in enumerate([("CPU", ACC), ("GPU", GREY), ("NPU (HVX)", TEAL), ("NPU (HMX)", AMB)]):
    idx = [0, 2, 3, 4][i]
    ax.plot(ts, temps[:, idx], color=c, lw=2, label=n)
ax.set_xlabel("giây"); ax.set_ylabel("°C"); ax.legend(frameon=False, ncol=4, loc="lower center")
ax.set_title("Chạy liên tục 7,5 phút (62 lượt): nhiệt độ; tốc độ sinh token giữ 25,3 token/s từ đầu tới cuối", fontsize=10)
save(fig, "fig_soak.png")

# 9. RAG
fig, ax = plt.subplots(1, 2, figsize=(10.5, 3.8))
bars(ax[0], ["Không tra cứu", "Có tra cứu"], [0.52, 0.30], [GREY, TEAL], "{:.2f}")
ax[0].set_title("Tỉ lệ bịa (câu qua STT, giám khảo LLM, laptop)", fontsize=10)
bars(ax[1], ["Pi 5\n(thấp)", "Pi 5\n(cao)", "Fold7 NPU"], [1.4, 2.8, 0.06], [GREY, GREY, TEAL], "+{:.2f} s")
ax[1].set_title("Câu trả lời thật chậm thêm bao nhiêu khi bật tra cứu", fontsize=10)
save(fig, "fig_rag.png")

# 10. Quantisation formats on the Pi
fig, ax = plt.subplots(1, 3, figsize=(11.5, 3.7))
bars(ax[0], ["Q4_K_M", "Q4_0", "IQ4_NL"], [87.9, 125.3, 96.0], [GREY, TEAL, GREY], "{:.0f}"); ax[0].set_title("Nạp prompt (token/s), Pi 5", fontsize=10)
bars(ax[1], ["Q4_K_M", "Q4_0", "IQ4_NL"], [16.2, 18.2, 17.6], [GREY, TEAL, GREY], "{:.1f}"); ax[1].set_title("Sinh token (token/s), Pi 5", fontsize=10)
bars(ax[2], ["Q4_K_M", "Q4_0", "IQ4_NL", "Q8_0"], [0.333, 0.308, 0.340, 0.393], [GREY, TEAL, GREY, GREY], "{:.3f}", 0.5); ax[2].set_title("Global-MMLU-vi (n=400, ±0,025), 0,8B", fontsize=10)
save(fig, "fig_quant_pi.png")

# 11. Fold7 llama-bench incl. bigger models
fig, ax = plt.subplots(1, 2, figsize=(11, 3.9))
labs = ["Pi 5 CPU\n0,8B", "Fold7 CPU\n0,8B", "Fold7 GPU\n0,8B", "Fold7 NPU\n0,8B", "Fold7 NPU\n1,5B", "Fold7 NPU\n2B"]
bars(ax[0], labs, [126, 635, 1009, 2012, 2121, 1409], [GREY, ACC, ACC, TEAL, TEAL, TEAL], "{:.0f}"); ax[0].set_title("Nạp prompt (token/s)", fontsize=10); ax[0].tick_params(axis="x", labelsize=8)
bars(ax[1], labs, [18.1, 90.7, 70.0, 63.2, 45.9, 32.9], [GREY, ACC, ACC, TEAL, TEAL, TEAL], "{:.0f}"); ax[1].set_title("Sinh token (token/s)", fontsize=10); ax[1].tick_params(axis="x", labelsize=8)
save(fig, "fig_platform_llm.png")
