#!/usr/bin/env python3
"""Download evaluation / calibration data into data/ and write JSONL manifests (PLAN §8).

  asr       VIVOS (CC BY-NC-SA 4.0) + FLEURS vi_vn (CC BY 4.0)  -> data/asr_test, data/calib
  calib_en  LibriSpeech dev-clean (CC BY 4.0) for the English-calibration ablation (S4)
  noise     DEMAND 16 kHz (CC BY 4.0): cafeteria, restaurant, station, meeting   -> data/noise
  bench     Global-MMLU vi (Apache-2.0) + VMLU validation mirror                  -> data/llm_bench

Common Voice Vietnamese is no longer distributed through the HF Hub (moved to Mozilla Data
Collective, account + terms required); FLEURS replaces it here — see docs/REFERENCES.md.
Manifests: data/manifests/<name>.jsonl, one {"audio": <path rel. to repo>, "text": ..., "dur": s} per line.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MAN = DATA / "manifests"
HF = "https://huggingface.co/datasets"


def fetch(url: str, dst: Path) -> Path:
    if dst.exists() and dst.stat().st_size > 0:
        print(f"  have {dst.relative_to(ROOT)}")
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"  get  {url}")
    tmp = dst.with_suffix(dst.suffix + ".part")
    # curl: resumable + retries (Zenodo drops long transfers)
    subprocess.run(["curl", "-fL", "--retry", "8", "--retry-all-errors", "-C", "-", "-o", str(tmp), url], check=True)
    tmp.rename(dst)
    return dst


def wav_dur(p: Path) -> float:
    import soundfile as sf  # handles float WAV (FLEURS) and FLAC

    return sf.info(str(p)).duration


def write_manifest(name: str, rows: list[dict]) -> None:
    MAN.mkdir(parents=True, exist_ok=True)
    with open(MAN / f"{name}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  wrote manifests/{name}.jsonl ({len(rows)} rows)")


def asr() -> None:
    # --- VIVOS ---
    vdir = DATA / "asr_test" / "vivos"
    if not (vdir / "vivos").exists():  # archives in data/downloads may be deleted after extraction
        tgz = fetch(f"{HF}/AILAB-VNUHCM/vivos/resolve/main/data/vivos.tar.gz", DATA / "downloads" / "vivos.tar.gz")
        vdir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tgz) as t:
            t.extractall(vdir, filter="data")
    for split, man in (("test", "vivos_test"), ("train", "vivos_train")):
        base = vdir / "vivos" / split
        rows = []
        for line in (base / "prompts.txt").read_text(encoding="utf-8").splitlines():
            uid, text = line.split(" ", 1)
            spk = uid.split("_")[0]
            wav = base / "waves" / spk / f"{uid}.wav"
            if wav.exists():
                rows.append({"id": uid, "audio": str(wav.relative_to(ROOT)), "text": text.strip(), "dur": round(wav_dur(wav), 3)})
        write_manifest(man, rows)

    # --- FLEURS vi_vn ---
    fdir = DATA / "asr_test" / "fleurs_vi"
    for split in ("test", "train"):
        tsv = fetch(f"{HF}/google/fleurs/resolve/main/data/vi_vn/{split}.tsv", fdir / f"{split}.tsv")
        if not (fdir / split).exists():
            tgz = fetch(f"{HF}/google/fleurs/resolve/main/data/vi_vn/audio/{split}.tar.gz", DATA / "downloads" / f"fleurs_vi_{split}.tar.gz")
            with tarfile.open(tgz) as t:
                t.extractall(fdir, filter="data")
        rows = []
        with open(tsv, encoding="utf-8") as f:
            for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                wav = fdir / split / r[1]
                if wav.exists():
                    rows.append({"id": f"fleurs_{r[0]}_{wav.stem}", "audio": str(wav.relative_to(ROOT)),
                                 "text": r[2].strip(), "dur": round(wav_dur(wav), 3)})
        write_manifest(f"fleurs_vi_{split}", rows)


def calib_en() -> None:
    ldir = DATA / "calib" / "librispeech"
    if not (ldir / "LibriSpeech").exists():
        tgz = fetch("https://www.openslr.org/resources/12/dev-clean.tar.gz", DATA / "downloads" / "librispeech-dev-clean.tar.gz")
        ldir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tgz) as t:
            t.extractall(ldir, filter="data")
    rows = []
    for trans in sorted((ldir / "LibriSpeech" / "dev-clean").rglob("*.trans.txt")):
        for line in trans.read_text().splitlines():
            uid, text = line.split(" ", 1)
            flac = trans.parent / f"{uid}.flac"
            rows.append({"id": uid, "audio": str(flac.relative_to(ROOT)), "text": text.lower(), "dur": None})
    write_manifest("librispeech_dev_clean", rows)


DEMAND = ["PCAFETER", "PRESTO", "PSTATION", "OMEETING"]


def noise() -> None:
    ndir = DATA / "noise" / "demand"
    for n in DEMAND:
        if not (ndir / n).exists():
            z = fetch(f"https://zenodo.org/api/records/1227121/files/{n}_16k.zip/content", DATA / "downloads" / f"{n}_16k.zip")
            with zipfile.ZipFile(z) as zf:
                zf.extractall(ndir)
    print(f"  noise in {ndir.relative_to(ROOT)}: {sorted(p.name for p in ndir.iterdir())}")


def bench() -> None:
    bdir = DATA / "llm_bench"
    for split in ("test", "dev"):
        fetch(f"{HF}/CohereLabs/Global-MMLU/resolve/main/vi/{split}-00000-of-00001.parquet", bdir / f"global_mmlu_vi_{split}.parquet")
    # VMLU (Zalo AI / vmlu.ai). Official test answers are hidden; the public validation split mirror is used
    # only as a secondary signal. Licence/terms recorded in docs/REFERENCES.md.
    try:
        from huggingface_hub import snapshot_download
        snapshot_download("vilm/vmlu_val", repo_type="dataset", local_dir=bdir / "vmlu_val")
        print("  have data/llm_bench/vmlu_val")
    except Exception as e:  # optional
        print(f"  !! VMLU mirror unavailable: {e}")


GROUPS = {"asr": asr, "calib_en": calib_en, "noise": noise, "bench": bench}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("groups", nargs="*", default=list(GROUPS))
    for g in ap.parse_args().groups:
        print(f"[{g}]")
        GROUPS[g]()
