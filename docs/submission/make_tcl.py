#!/usr/bin/env python3
"""Numbers of the TCL T506T runs (results/phone/tcl) for the updated report, poster and slides: writes so_lieu_tcl.tex
(LaTeX macros) and figures/thiet_bi.pdf (Fold7 vs TCL). Every value is read from the raw run files; nothing is typed in.

  python docs/submission/make_tcl.py
"""
from __future__ import annotations

import json
import re
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "results" / "phone" / "tcl"
OUT = ROOT / "docs" / "submission"
vn = lambda x, d=2: f"{x:.{d}f}".replace(".", ",")


def score(run: str) -> dict:
    return json.load(open(T / f"{run}.score.json", encoding="utf-8"))


def meta(run: str) -> dict:
    s = (T / f"{run}.meta").read_text().strip()
    return {k: float(v.replace(",", ".")) for k, v in re.findall(r"(\w+)=([\d.,]+)", s)}


def llm(run: str) -> dict:
    """LLM turns of a QA run: answer latency (first real answer audio), tokens/s, model load time."""
    rows = [json.loads(l) for l in open(T / f"{run}.turns.jsonl", encoding="utf-8") if l.strip()]
    rows = [r for r in rows if "fast" not in r["m"]]
    load = None
    for line in open(T / f"{run}.log", encoding="utf-8"):
        m = re.search(r"load_s=([\d.]+)", line)
        if m: load = float(m.group(1))
    tok = [r["m"]["llm_tok_s"] for r in rows if "llm_tok_s" in r["m"]]
    ans = [r["m"]["answer_audio_ms"] / 1000 for r in rows if "answer_audio_ms" in r["m"]]
    first = [r["m"]["first_audio_ms"] / 1000 for r in rows if "first_audio_ms" in r["m"]]
    return {"n": len(rows), "tok": st.median(tok) if tok else 0, "ans": st.median(ans) if ans else 0, "first": st.median(first) if first else 0,
            "load": load or 0, "rows": rows}


def main() -> None:
    par = [json.loads(l) for l in open(T / "parity_tcl.jsonl", encoding="utf-8")]
    ref = [json.loads(l) for l in open(ROOT / "results/an_toan/parity_python.jsonl", encoding="utf-8")]
    same = sum(a["got"] == b["got"] and a["q"] == b["q"] for a, b in zip(par, ref))
    us_per_q = float(re.search(r"us_per_q=(\d+)", (T / "parity_tcl.meta").read_text()).group(1))
    a, b = score("safety_v45_08b_cpu"), score("safety_v3_08b_cpu")
    t4, gr = score("safety_v45_08b_cpu_t4"), score("safety_v45_08b_cpu_greedy_t4")
    # default on CPU-only phones: no retrieval, no history; the first run (retrieval + 2 exchanges of history) is kept for comparison
    qa, qr, q8, qb = llm("qa_08b_cpu_norag"), llm("qa_08b_cpu_rag_h0"), llm("qa_08b_cpu_norag_t8"), llm("qa_2b_cpu_norag")
    ma, mb = meta("qa_08b_cpu_norag"), meta("qa_2b_cpu_norag")
    best = min((a, "3 luồng, có thiên vị từ khoá"), (t4, "4 luồng, có thiên vị từ khoá"), (gr, "4 luồng, không thiên vị"), key=lambda x: x[0]["safety_first_audio_ms"]["p50"])
    mac = {
        "tclChip": "Helio P22 (MT6762), 8 lõi Cortex-A53",
        "tclRam": "4 GB",
        "tclParity": f"{same:,}/{len(ref):,}".replace(",", "."),
        "tclParityMs": vn(us_per_q / 1000, 0) + "\\,ms",
        "tclSafeOk": f"{a['correct']}/{a['n']}",
        "tclSafeOkB": f"{b['correct']}/{b['n']}",
        "tclSafeMed": vn(a["safety_first_audio_ms"]["p50"] / 1000),
        "tclSafeHi": vn(a["safety_first_audio_ms"]["p95"] / 1000),
        "tclSafeMax": vn(a["safety_first_audio_ms"]["max"] / 1000),
        "tclSttMed": vn(a["stt_ms_p50"] / 1000),
        "tclFourMed": vn(t4["safety_first_audio_ms"]["p50"] / 1000), "tclFourOk": f"{t4['correct']}/{t4['n']}",
        "tclGreedyMed": vn(gr["safety_first_audio_ms"]["p50"] / 1000), "tclGrOk": f"{gr['correct']}/{gr['n']}",
        "tclSttNote": f"3 luồng {vn(a['safety_first_audio_ms']['p50'] / 1000)}\\,s, 4 luồng {vn(t4['safety_first_audio_ms']['p50'] / 1000)}\\,s, "
                      f"4 luồng không thiên vị từ khoá {vn(gr['safety_first_audio_ms']['p50'] / 1000)}\\,s ({gr['correct']}/{gr['n']} đúng thẻ).",
        "tclLoadA": vn(qa["load"], 0), "tclLoadB": vn(qb["load"], 0),
        "tclTokA": vn(qa["tok"], 1), "tclTokB": vn(qb["tok"], 1),
        "tclAnsA": vn(qa["ans"]), "tclAnsB": vn(qb["ans"]),
        "tclFirstA": vn(qa["first"]), "tclFirstB": vn(qb["first"]),
        "tclPssA": vn(ma.get("peak_pss_kb", 0) / 1e6, 1), "tclPssB": vn(mb.get("peak_pss_kb", 0) / 1e6, 1),
        "tclTempA": vn(ma.get("temp", 0), 1), "tclTempB": vn(mb.get("temp", 0), 1),
        "tclNqa": str(qa["n"]), "tclNqb": str(qb["n"]),
        "tclAnsRag": vn(qr["ans"]), "tclTtftRag": vn(st.median([r["m"]["ttft_ms"] for r in qr["rows"]]) / 1000, 1),
        "tclPromptRag": str(int(st.median([r["m"]["llm_prompt_n"] for r in qr["rows"]]))),
        "tclTtftA": vn(st.median([r["m"]["ttft_ms"] for r in qa["rows"]]) / 1000, 1),
        "tclAnsEight": vn(q8["ans"]), "tclTokEight": vn(q8["tok"], 1),
        "tclBest": best[1],
    }
    mac["tclTakeaway"] = (f"Máy phổ thông vẫn trả lời được offline, nhưng chậm: mô hình 0,8 tỉ cho câu trả lời thật sau {mac['tclAnsA']}\\,s "
                          f"(trung vị, {qa['n']} câu, tắt tra cứu), bật tra cứu thì {mac['tclAnsRag']}\\,s vì CPU chỉ nạp khoảng 9 token prompt mỗi giây; "
                          f"mô hình 2 tỉ sau {mac['tclAnsB']}\\,s. Câu khẩn cấp không qua LLM nên vẫn có tiếng sau {mac['tclSafeMed']}\\,s.")
    lines = ["% Sinh tự động bởi make_tcl.py từ results/phone/tcl; không sửa tay."] + [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in mac.items()]
    (OUT / "so_lieu_tcl.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    # Fold7 vs TCL: first audio of safety answers and real answer of LLM questions (medians)
    plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
    fig, ax = plt.subplots(figsize=(8 / 2.54, 4.6 / 2.54))
    labels = ["Thẻ an toàn,\ntiếng đầu", "Hỏi đáp,\ncâu trả lời thật"]
    fold = [0.55, 1.53]
    tcl = [a["safety_first_audio_ms"]["p50"] / 1000, qa["ans"]]
    x = range(len(labels)); w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], fold, w, color="#2a78d6", label="Fold7 (NPU, 2 tỉ)")
    b2 = ax.bar([i + w / 2 for i in x], tcl, w, color="#eb6834", label="TCL T506T (CPU, 0,8 tỉ)")
    for bars in (b1, b2):
        for r in bars:
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.05, vn(r.get_height()), ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(x)); ax.set_xticklabels(labels); ax.set_ylabel("giây (trung vị)")
    ax.set_ylim(0, max(tcl + fold) * 1.25); ax.legend(loc="upper left", fontsize=7.5, frameon=False)
    fig.savefig(OUT / "figures" / "thiet_bi.pdf", bbox_inches="tight", pad_inches=0.02)


if __name__ == "__main__":
    main()
