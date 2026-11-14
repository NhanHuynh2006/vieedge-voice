#!/usr/bin/env python3
"""HEF-vs-ONNX encoder drift on the real Hailo-8L (PLAN §5.1, before measuring WER).

Runs the same Vietnamese test mels through the HEF on the NPU and through the FP32 ONNX encoder
(CPU) and reports cosine similarity per utterance + how often the CPU decoder output differs.
Mean cosine well below ~0.95 (or many empty transcripts) = the "silent output" failure mode.

  check_encoder_drift.py --hef stt/hef/phowhisper-tiny-encoder-10s_vi_h8l.hef --onnx stt/onnx/phowhisper-tiny-encoder-10s.onnx
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from common import append_experiment, load_audio, load_manifest, results_dir
from vieedge.config import load_config
from vieedge.stt.cpu_decoder import HybridWhisper
from vieedge.stt.hailo_encoder import HailoEncoder, OnnxEncoder
from vieedge.stt.mel import window_mel
from vieedge.stt.tokens import tokens_to_text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config")
    ap.add_argument("--hef", required=True)
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--decoder", default="stt/ct2/phowhisper-tiny-int8")
    ap.add_argument("--n", type=int, default=100)
    a = ap.parse_args()
    cfg = load_config(a.config)
    hef, onx = HailoEncoder(cfg.model_path(a.hef)), OnnxEncoder(cfg.model_path(a.onnx), 3)
    dec = HybridWhisper(onx, cfg.model_path(a.decoder))
    cos, same, empty_h = [], 0, 0
    rows = load_manifest("vivos_test", a.n)
    for r in rows:
        mel = window_mel(load_audio(r["audio"]), hef.window_s)
        h1, h0 = hef.encode(mel), onx.encode(mel)
        cos.append(float((h1 * h0).sum() / (np.linalg.norm(h1) * np.linalg.norm(h0) + 1e-9)))
        t1 = tokens_to_text(dec.decode(h1).sequences[0])
        t0 = tokens_to_text(dec.decode(h0).sequences[0])
        same += t1 == t0
        empty_h += not t1.strip()
    res = {"hef": a.hef, "n": len(rows), "cos_mean": float(np.mean(cos)), "cos_min": float(np.min(cos)),
           "cos_p05": float(np.percentile(cos, 5)), "same_transcript_rate": same / len(rows), "empty_hef_rate": empty_h / len(rows),
           "npu_ms_per_call": 1000 * hef.busy_s / max(hef.calls, 1)}
    print(json.dumps(res, indent=1))
    (results_dir() / "raw").mkdir(exist_ok=True)
    append_experiment({"exp_id": "S3-drift", "stt_model": a.hef.split("/")[-1], "stt_where": "npu",
                       "notes": f"cos_mean={res['cos_mean']:.4f};cos_p05={res['cos_p05']:.4f};same_text={res['same_transcript_rate']:.2f};"
                                f"empty={res['empty_hef_rate']:.2f};npu_ms={res['npu_ms_per_call']:.1f}"}, raw=res)


if __name__ == "__main__":
    main()
