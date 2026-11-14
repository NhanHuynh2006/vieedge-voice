#!/usr/bin/env python3
"""STT ladder S0-S4 (PLAN §6): WER (clean + noisy), latency, RTF, encoder/decoder split.

  # S0 / S1: PhoWhisper on the CPU (FP32 / INT8), standard 30 s window and the 10 s window
  bench_stt.py --exp S0 --set stt.backend=ct2 --set stt.ct2.model=stt/ct2/phowhisper-tiny-float32 --set stt.ct2.compute_type=float32
  bench_stt.py --exp S1 --set stt.backend=ct2 --set stt.ct2.window_s=10
  # S2: original Whisper HEF on Hailo-8L + Whisper decoder on CPU
  bench_stt.py --exp S2 --set stt.hybrid.hef=stt/hef/whisper-tiny-encoder-10s_h8l.hef --set stt.hybrid.decoder=stt/ct2/whisper-tiny-int8
  # S3 / S4: PhoWhisper HEF, Vietnamese vs English calibration
  bench_stt.py --exp S3 --set stt.hybrid.hef=stt/hef/phowhisper-tiny-encoder-10s_vi_h8l.hef --calib-lang vi
  bench_stt.py --exp S4 --set stt.hybrid.hef=stt/hef/phowhisper-tiny-encoder-10s_en_h8l.hef --calib-lang en

Noise: --snr 20 10 5 mixes DEMAND cafeteria/restaurant/station/meeting noise into the test audio.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np

from common import ROOT, append_experiment, cer, check_thermal, load_audio, load_manifest, pct, results_dir, thermal_state, wer
from vieedge.config import load_config, set_override
from vieedge.stt import make_stt
from vieedge.stt.incremental import transcribe_long


def noise_bank() -> list[np.ndarray]:
    files = []
    for base in (ROOT / "data" / "noise", Path("/opt/vieedge/data/noise")):
        files += sorted(base.rglob("*.wav"))
    # one channel per DEMAND scene is enough (ch01)
    files = [f for f in files if f.name.lower().startswith("ch01")] or files
    return [load_audio(str(f)) for f in files]


def run(stt, rows, snr=None, noises=None, beam=None, seed=0):
    rnd = random.Random(seed)
    hyps, lat, rtf, enc, dec = [], [], [], [], []
    for r in rows:
        x = load_audio(r["audio"])
        if snr is not None and noises:
            from common import mix_snr

            x = mix_snr(x, rnd.choice(noises), snr, rnd)
        t0 = time.monotonic()
        text, res = transcribe_long(stt, x, beam)
        dt = time.monotonic() - t0
        hyps.append(text)
        lat.append(dt * 1e3)
        rtf.append(dt / (len(x) / 16000))
        enc.append(sum(z.timings.get("encoder_ms", 0) for z in res))
        dec.append(sum(z.timings.get("decoder_ms", z.timings.get("encdec_ms", 0)) for z in res))
    refs = [r["text"] for r in rows]
    return {"wer": wer(refs, hyps), "cer": cer(refs, hyps), "latency_ms": pct(lat), "rtf": pct(rtf, (50, 95)),
            "encoder_ms": pct(enc), "decoder_ms": pct(dec), "hyps": hyps}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config")
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--exp", required=True)
    ap.add_argument("--manifests", nargs="+", default=["vivos_test", "fleurs_vi_test"])
    ap.add_argument("--limit", type=int, default=300, help="utterances per manifest (0 = all)")
    ap.add_argument("--snr", nargs="*", type=float, default=[], help="also evaluate in noise at these SNRs")
    ap.add_argument("--beam", type=int)
    ap.add_argument("--calib-lang", default="")
    ap.add_argument("--notes", default="")
    a = ap.parse_args()
    over: dict = {}
    for kv in a.set:
        k, v = kv.split("=", 1)
        set_override(over, k, v)
    cfg = load_config(a.config, over)
    stt = make_stt(cfg)
    stt.warmup()
    info = stt.info()
    th0 = thermal_state()
    out: dict = {"stt": info, "config": cfg["stt"], "sets": {}}
    noises = noise_bank() if a.snr else []
    clean_w, noisy_w, lat_all = [], [], []
    for m in a.manifests:
        rows = load_manifest(m, a.limit or None)
        res = run(stt, rows, beam=a.beam)
        lat_all.append(res["latency_ms"]["p50"])
        clean_w.append(res["wer"])
        out["sets"][m] = {k: v for k, v in res.items() if k != "hyps"}
        dump = results_dir() / "raw" / f"stt_{a.exp}_{m}.jsonl"
        dump.parent.mkdir(exist_ok=True)
        with open(dump, "w", encoding="utf-8") as f:
            for r, h in zip(rows, res["hyps"]):
                f.write(json.dumps({"id": r["id"], "ref": r["text"], "hyp": h}, ensure_ascii=False) + "\n")
        print(f"[{a.exp}] {m}: WER {res['wer']:.3f} CER {res['cer']:.3f} lat p50 {res['latency_ms']['p50']} ms "
              f"(enc {res['encoder_ms']['p50']} / dec {res['decoder_ms']['p50']}) RTF {res['rtf']['p50']}")
        for snr in a.snr:
            rn = run(stt, rows, snr=snr, noises=noises, beam=a.beam, seed=int(snr))
            out["sets"][f"{m}@{snr:g}dB"] = {k: v for k, v in rn.items() if k != "hyps"}
            noisy_w.append(rn["wer"])
            print(f"[{a.exp}] {m} @ {snr:g} dB: WER {rn['wer']:.3f}")
    th1 = thermal_state()
    out["thermal"] = [th0, th1]
    s = cfg["stt"]
    model = (s["ct2"]["model"] if s["backend"] == "ct2" else
             s["hybrid"]["hef"] if s["hybrid"]["encoder"] == "hailo" else s["hybrid"]["onnx"])
    prec = (f"enc-INT8(HEF)+dec-{s['hybrid']['compute_type']}" if s["backend"] == "hybrid" and s["hybrid"]["encoder"] == "hailo"
            else f"enc-FP32(ONNX)+dec-{s['hybrid']['compute_type']}" if s["backend"] == "hybrid" else s["ct2"]["compute_type"])
    append_experiment({
        "exp_id": a.exp, "stt_model": Path(model).name, "stt_where": info.get("where"), "stt_prec": prec,
        "calib_lang": a.calib_lang, "wer": round(float(np.mean(clean_w)), 4),
        "wer_noisy": round(float(np.mean(noisy_w)), 4) if noisy_w else "",
        "temp_max": th1.get("temp_c"), "threads": s[s["backend"]]["threads"],
        "notes": ";".join(filter(None, [a.notes, f"sets={'+'.join(a.manifests)}", f"n={a.limit}", f"lat_p50_ms={np.mean(lat_all):.0f}",
                                        f"window={info.get('window_s')}s", check_thermal(th0, th1)])),
    }, raw=out)


if __name__ == "__main__":
    main()
