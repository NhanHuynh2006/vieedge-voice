#!/usr/bin/env python3
"""results/experiments.csv -> Markdown tables per ladder for the report (docs/report/tables.md).

Only numbers present in the CSV are printed; empty cells stay "–". Rows measured on the laptop are
labelled (os_cfg = laptop) so they are never mistaken for Raspberry Pi numbers.
Optional: --meter CSV from an external USB-C power logger + --turns results/turns/*.jsonl -> J/turn.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from common import ROOT, results_dir

LADDERS = {
    "STT (S0–S5)": ("S", ["exp_id", "os_cfg", "stt_model", "stt_where", "stt_prec", "calib_lang", "wer", "wer_noisy", "temp_max", "notes"]),
    "LLM (M0–M5)": ("M", ["exp_id", "os_cfg", "llm_model", "llm_quant", "lora", "spec_dec", "threads", "ttft_ms", "tok_s", "ram_mb",
                          "llm_bench_acc", "answer_score", "notes"]),
    "TTS (T0–T2)": ("T", ["exp_id", "os_cfg", "threads", "notes"]),
    "Hệ thống (P1–P3)": ("P", ["exp_id", "os_cfg", "stt_where", "llm_model", "first_audio_p50", "first_audio_p95", "first_audio_p99",
                               "ttft_ms", "tok_s", "wer", "power_w", "j_per_turn", "xruns_per_h", "notes"]),
    "Hệ điều hành (O0–O4)": ("O", ["exp_id", "os_cfg", "cyclictest_max_us", "xruns_per_h", "tok_s", "ram_mb", "first_audio_p95",
                                   "first_audio_p99", "notes"]),
}


def load_rows() -> list[dict]:
    p = results_dir() / "experiments.csv"
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def md_table(rows: list[dict], cols: list[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join((r.get(c) or "–").replace("|", "/") for c in cols) + " |")
    return "\n".join(out)


def energy_from_meter(meter_csv: Path, turn_files: list[Path]) -> dict:
    from vieedge.telemetry.power import energy_j, load_meter_csv

    samples = load_meter_csv(str(meter_csv))
    per_cfg = defaultdict(list)
    for tf in turn_files:
        for l in open(tf, encoding="utf-8"):
            t = json.loads(l)
            off = t["meta"].get("wall_minus_mono")
            ta, tb = t["t_abs"].get("speech_start"), t["t_abs"].get("audio_done")
            if off and ta and tb:
                per_cfg[(t["meta"].get("os_cfg"), t["meta"].get("stt"))].append(energy_j(samples, ta + off, tb + off))
    return {f"{k[0]}/{k[1]}": round(sum(v) / len(v), 2) for k, v in per_cfg.items() if v}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "report" / "tables.md")
    ap.add_argument("--meter", type=Path)
    ap.add_argument("--turns", nargs="*", type=Path, default=[])
    a = ap.parse_args()
    rows = load_rows()
    parts = ["# Bảng kết quả (sinh tự động từ results/experiments.csv)", "",
             f"Tổng số dòng thí nghiệm: {len(rows)}. Cột `os_cfg = laptop` là số đo trên laptop phát triển, "
             "không phải Raspberry Pi 5 (chỉ dùng cho chỉ số không phụ thuộc phần cứng như WER/độ chính xác).", ""]
    for title, (prefix, cols) in LADDERS.items():
        sel = [r for r in rows if r["exp_id"].upper().startswith(prefix) or (prefix == "O" and r["exp_id"].upper().startswith("O"))]
        parts += [f"## {title}", "", md_table(sel, cols) if sel else "_Chưa có số đo — chạy script tương ứng trên thiết bị._", ""]
    if a.meter:
        parts += ["## Năng lượng theo đồng hồ ngoài (J/lượt)", "", "```", json.dumps(energy_from_meter(a.meter, a.turns), indent=1), "```", ""]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(parts), encoding="utf-8")
    print(f"-> {a.out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
