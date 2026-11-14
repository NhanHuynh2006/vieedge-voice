"""Shared helpers for all benchmarks: experiment rows (PLAN §9), manifests, WER, stats, thermal checks.

Every number in reports comes from rows appended here; nothing is typed by hand (PLAN header).
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "src").exists():
    sys.path.insert(0, str(ROOT / "src"))

COLUMNS = ["exp_id", "date", "os_cfg", "stt_model", "stt_where", "stt_prec", "calib_lang", "llm_model", "llm_quant", "lora",
           "spec_dec", "threads", "wer", "wer_noisy", "llm_bench_acc", "answer_score", "ttft_ms", "tok_s", "first_audio_p50",
           "first_audio_p95", "first_audio_p99", "ram_mb", "temp_max", "power_w", "j_per_turn", "xruns_per_h",
           "cyclictest_max_us", "notes", "git_commit"]


def results_dir() -> Path:
    d = Path(os.environ.get("VIEEDGE_RESULTS", ROOT / "results" if (ROOT / "src").exists() else "/opt/vieedge/results"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def git_commit() -> str:
    if os.environ.get("VIEEDGE_GIT_COMMIT"):
        return os.environ["VIEEDGE_GIT_COMMIT"]
    for f in (ROOT / "GIT_COMMIT", Path("/opt/vieedge/GIT_COMMIT")):
        if f.exists():
            return f.read_text().strip()
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
        return out.stdout.strip() + ("-dirty" if dirty else "") if out.returncode == 0 else "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def os_cfg() -> str:
    from vieedge.config import _env_file_os_cfg

    return os.environ.get("VIEEDGE_OS_CFG") or _env_file_os_cfg() or ("laptop" if (ROOT / ".venv").exists() else "unknown")


def append_experiment(row: dict, raw: dict | None = None) -> dict:
    """Append one row to results/experiments.csv (+ full details in results/raw/<exp_id>-<ts>.json)."""
    rd = results_dir()
    row = {k: row.get(k, "") for k in COLUMNS}
    row["date"] = row.get("date") or dt.datetime.now().isoformat(timespec="seconds")
    row["git_commit"] = row.get("git_commit") or git_commit()
    row["os_cfg"] = row.get("os_cfg") or os_cfg()
    path = rd / "experiments.csv"
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        w.writerow({k: _fmt(row.get(k, "")) for k in COLUMNS})
    if raw is not None:
        (rd / "raw").mkdir(exist_ok=True)
        ts = time.strftime("%Y%m%d-%H%M%S")
        (rd / "raw" / f"{row['exp_id']}-{ts}.json").write_text(json.dumps({"row": row, **raw}, ensure_ascii=False, indent=1, default=str))
    print("experiments.csv <-", {k: v for k, v in row.items() if v not in ("", None) and k not in ("date", "git_commit")})
    return row


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.4g}"
    return v


def load_manifest(name: str, limit: int | None = None, seed: int = 0) -> list[dict]:
    for base in (ROOT / "data" / "manifests", Path("/opt/vieedge/data/manifests")):
        p = base / f"{name}.jsonl"
        if p.exists():
            rows = [json.loads(l) for l in open(p, encoding="utf-8")]
            for r in rows:
                if not os.path.isabs(r["audio"]):
                    r["audio"] = str(base.parents[1] / r["audio"])
            if limit and limit < len(rows):
                rows = random.Random(seed).sample(rows, limit)
            return rows
    raise FileNotFoundError(f"manifest {name}")


def load_audio(path: str) -> np.ndarray:
    try:
        import soundfile as sf

        x, sr = sf.read(path, dtype="float32", always_2d=True)
        x = x.mean(1)
    except ImportError:  # device without soundfile: 16-bit WAV only
        import wave

        with wave.open(path) as w:
            sr = w.getframerate()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
            if w.getnchannels() > 1:
                x = x.reshape(-1, w.getnchannels()).mean(1)
    if sr != 16000:
        from vieedge.audio.resample import resample

        x = resample(x, sr, 16000)
    return x


def mix_snr(x: np.ndarray, noise: np.ndarray, snr_db: float, rnd: random.Random) -> np.ndarray:
    if len(noise) < len(x):
        noise = np.tile(noise, int(np.ceil(len(x) / len(noise))))
    st = rnd.randrange(0, len(noise) - len(x) + 1)
    n = noise[st:st + len(x)]
    ps, pn = float(np.mean(x ** 2)) + 1e-10, float(np.mean(n ** 2)) + 1e-10
    return (x + n * np.sqrt(ps / (pn * 10 ** (snr_db / 10)))).astype(np.float32)


def edit_distance(a: list, b: list) -> int:
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return d[len(b)]


def wer(refs: list[str], hyps: list[str]) -> float:
    from vieedge.textproc import wer_normalize

    err = tot = 0
    for r, h in zip(refs, hyps):
        rw, hw = wer_normalize(r).split(), wer_normalize(h).split()
        err += edit_distance(rw, hw)
        tot += len(rw)
    return err / max(tot, 1)


def cer(refs: list[str], hyps: list[str]) -> float:
    from vieedge.textproc import wer_normalize

    err = tot = 0
    for r, h in zip(refs, hyps):
        rc, hc = list(wer_normalize(r).replace(" ", "")), list(wer_normalize(h).replace(" ", ""))
        err += edit_distance(rc, hc)
        tot += len(rc)
    return err / max(tot, 1)


def pct(xs, ps=(50, 95, 99)) -> dict:
    xs = [x for x in xs if x is not None]
    if not xs:
        return {f"p{p}": None for p in ps} | {"mean": None, "std": None, "n": 0}
    a = np.asarray(xs, dtype=float)
    nd = 1 if abs(a).max() >= 10 else 4  # ms -> 0.1, ratios (RTF) -> 4 digits
    return {f"p{p}": round(float(np.percentile(a, p)), nd) for p in ps} | {
        "mean": round(float(a.mean()), nd), "std": round(float(a.std()), nd), "n": len(a)}


def thermal_state() -> dict:
    from vieedge.telemetry.sysmon import governor, soc_temp, throttled

    return {"temp_c": soc_temp(), "throttled": throttled(), "governor": governor(), "t": time.time()}


def check_thermal(before: dict, after: dict) -> str:
    """Note for the experiment row if the SoC throttled during the run (PLAN §9)."""
    notes = []
    if after.get("throttled") not in (None, 0):
        notes.append(f"THROTTLED=0x{after['throttled']:x}")
    if after.get("governor") and after["governor"] != "performance":
        notes.append(f"governor={after['governor']}")
    return ";".join(notes)
