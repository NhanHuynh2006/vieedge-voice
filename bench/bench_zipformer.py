#!/usr/bin/env python3
"""Vietnamese Zipformer-30M RNN-T (hynt, 6000 h, int8, sherpa-onnx) vs PhoWhisper on the same test utterances.
Note: FLEURS is part of that model's training data, so only VIVOS is a fair test of it."""
from __future__ import annotations

import argparse
import time

import numpy as np
import sherpa_onnx

from common import ROOT, append_experiment, check_thermal, load_audio, load_manifest, pct, thermal_state, wer

D = ROOT / "models/stt/zipformer-vi"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--exp", default="S6")
    a = ap.parse_args()
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(D / "encoder-epoch-20-avg-10.int8.onnx"), decoder=str(D / "decoder-epoch-20-avg-10.int8.onnx"),
        joiner=str(D / "joiner-epoch-20-avg-10.int8.onnx"), tokens=str(D / "tokens.txt"), num_threads=a.threads,
        sample_rate=16000, feature_dim=80, decoding_method="greedy_search", modeling_unit="bpe", bpe_vocab=str(D / "bpe.model"))
    th0 = thermal_state()
    rows = load_manifest("vivos_test", a.n)
    refs, hyps, lat, rtf = [], [], [], []
    s = rec.create_stream()
    s.accept_waveform(16000, np.zeros(16000, np.float32))
    rec.decode_stream(s)
    for r in rows:
        x = load_audio(r["audio"])
        t0 = time.monotonic()
        st = rec.create_stream()
        st.accept_waveform(16000, x)
        rec.decode_stream(st)
        dt = time.monotonic() - t0
        refs.append(r["text"])
        hyps.append(st.result.text)
        lat.append(dt * 1e3)
        rtf.append(dt / (len(x) / 16000))
    w = wer(refs, hyps)
    th1 = thermal_state()
    print(f"Zipformer-vi int8, VIVOS n={len(rows)}: WER {w:.3f}  latency p50 {pct(lat)['p50']} ms  RTF p50 {pct(rtf, (50,))['p50']}")
    for r, h in list(zip(refs, hyps))[:3]:
        print("  REF", r.lower(), "\n  HYP", h.lower())
    append_experiment({"exp_id": a.exp, "stt_model": "zipformer-vi-30M-int8", "stt_where": "cpu", "stt_prec": "int8", "wer": round(w, 4),
                       "threads": a.threads, "temp_max": th1.get("temp_c"),
                       "notes": f"sherpa-onnx offline RNNT greedy; VIVOS only (FLEURS in its train set); lat_p50_ms={pct(lat)['p50']};"
                                f"rtf_p50={pct(rtf, (50,))['p50']};{check_thermal(th0, th1)}"})


if __name__ == "__main__":
    main()
