#!/usr/bin/env python3
"""Compile a (Pho)Whisper encoder ONNX into a Hailo-8L HEF with the Dataflow Compiler (DFC v3.x).

Runs on the x86 laptop inside the DFC environment (hailo_compile/Dockerfile or a venv with the DFC
wheel from the Hailo Developer Zone). Steps = hailo-whisper's convert_whisper_encoder.py, with:
  * our calibration set (Vietnamese train audio, or English for the S4 ablation),
  * the model script (.alls) from hailo-whisper for the same variant/arch, finetune dataset size
    clipped to the calibration size,
  * after optimisation: an emulator check (SDK_FP_OPTIMIZED vs SDK_QUANTIZED vs ONNX) on held-out
    Vietnamese *test* audio -> cosine similarity report (catches the "silent output" failure mode
    before spending time on WER), then compilation to HEF.

  python hailo_compile/convert_encoder.py hailo_compile/work/onnx/phowhisper-tiny-encoder-10s.onnx \
      --variant tiny --calib hailo_compile/work/calib/vi_10s.npy --tag vi
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HW = HERE / "work" / "hailo-whisper"
sys.path.insert(0, str(ROOT / "src"))


def model_script(variant: str, arch: str, calib_n: int, mode: str = "hailo", ft_batch: int | None = None) -> str:
    src = HW / "conversion" / "optimization" / variant / arch / f"encoder_model_script_{variant}.alls"
    txt = src.read_text()
    if mode in ("no16", "no16-nofinetune"):
        # hailo-whisper's per-layer a16_w16 lines are keyed to the layer numbering of their own export; on our
        # graph (DFC 3.34) several of them produce precision_change layers the Hailo-8L cannot run -> drop them
        txt = "\n".join(l for l in txt.splitlines() if not l.startswith("quantization_param("))
    if mode == "no16-nofinetune":
        # quantisation-aware fine-tuning takes hours on a CPU: skip it, the emulator drift check decides if INT8 alone is good enough
        txt = re.sub(r"post_quantization_optimization\(finetune, policy=enabled", "post_quantization_optimization(finetune, policy=disabled", txt)
    if ft_batch:  # QAFT batch size: the stock 8 needs more than the 5.7 GB free on an 8 GB laptop GPU
        txt = re.sub(r"(post_quantization_optimization\(finetune.*?)batch_size=\d+", rf"\g<1>batch_size={ft_batch}", txt)
    txt = re.sub(r"dataset_size=\d+", f"dataset_size={calib_n}", txt)
    txt = re.sub(r"calibset_size=\d+", f"calibset_size={min(calib_n, 1024)}", txt)
    return txt


def test_mels(window: float, n: int) -> np.ndarray:
    import soundfile as sf

    from vieedge.stt.mel import window_mel

    rows = [json.loads(l) for l in open(ROOT / "data" / "manifests" / "vivos_test.jsonl", encoding="utf-8")][:n]
    out = []
    for r in rows:
        x, _ = sf.read(str(ROOT / r["audio"]), dtype="float32")
        out.append(window_mel(x, window).T[None, None])
    return np.concatenate(out).astype(np.float32)


def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a = a.reshape(len(a), -1)
    b = b.reshape(len(b), -1)
    return (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-9)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("onnx", type=Path)
    ap.add_argument("--variant", choices=["tiny", "base"], required=True)
    ap.add_argument("--arch", default="hailo8l", choices=["hailo8", "hailo8l", "hailo10h"])
    ap.add_argument("--calib", type=Path, required=True)
    ap.add_argument("--tag", default="vi", help="calibration language tag in the output name")
    ap.add_argument("--n-test", type=int, default=100)
    ap.add_argument("--script", choices=["hailo", "no16", "no16-nofinetune"], default="hailo", help="model script variant")
    ap.add_argument("--ft-batch", type=int, help="override the fine-tuning batch size (GPU memory)")
    ap.add_argument("--har", type=Path, help="start from an already optimised .har (skip translate+optimise)")
    ap.add_argument("--test-mels", type=Path, help="precomputed NHWC test mels (.npy) if soundfile is not in the DFC env")
    ap.add_argument("--outdir", type=Path, default=HERE / "work" / "hef")
    a = ap.parse_args()

    from hailo_sdk_client import ClientRunner, InferenceContext

    name = a.onnx.stem  # phowhisper-tiny-encoder-10s
    out = a.outdir / f"{name}_{a.tag}_{'h8l' if a.arch == 'hailo8l' else a.arch}"
    out.mkdir(parents=True, exist_ok=True)
    calib = np.load(a.calib)
    frames = calib.shape[2]
    window = frames / 100
    report: dict = {"onnx": str(a.onnx), "variant": a.variant, "arch": a.arch, "calib": str(a.calib),
                    "calib_shape": list(calib.shape), "window_s": window}
    t0 = time.time()

    if a.har:
        runner = ClientRunner(har=str(a.har))
    else:
        runner = ClientRunner(hw_arch=a.arch)
        runner.translate_onnx_model(str(a.onnx), name)
        runner.save_har(str(out / f"{name}.har"))
        script = model_script(a.variant, a.arch, len(calib), a.script, a.ft_batch)
        (out / "model_script.alls").write_text(script)
        runner.load_model_script(script)
        runner.optimize(calib, work_dir=str(out))
        runner.save_har(str(out / f"{name}_optimized.har"))
    report["optimize_s"] = round(time.time() - t0)

    # ---- drift check on held-out Vietnamese test audio
    import onnxruntime as ort

    mels = np.load(a.test_mels) if a.test_mels else test_mels(window, a.n_test)
    sess = ort.InferenceSession(str(a.onnx), providers=["CPUExecutionProvider"])
    ref = np.concatenate([sess.run(None, {sess.get_inputs()[0].name: m.transpose(0, 3, 1, 2)})[0] for m in np.split(mels, len(mels))])
    with runner.infer_context(InferenceContext.SDK_FP_OPTIMIZED) as ctx:
        fp = runner.infer(ctx, mels)
    with runner.infer_context(InferenceContext.SDK_QUANTIZED) as ctx:
        q = runner.infer(ctx, mels)
    cs_fp, cs_q = cosine(ref, np.asarray(fp)), cosine(ref, np.asarray(q))
    report["cosine_fp_optimized"] = {"mean": float(cs_fp.mean()), "min": float(cs_fp.min())}
    report["cosine_quantized"] = {"mean": float(cs_q.mean()), "min": float(cs_q.min()), "p05": float(np.percentile(cs_q, 5))}
    np.save(out / "emulator_quantized_test.npy", np.asarray(q).reshape(len(mels), -1, ref.shape[-1]))
    print(json.dumps(report, indent=1))
    if cs_q.mean() < 0.9:
        print("WARNING: quantised encoder output drifts strongly from ONNX (mean cosine < 0.9); "
              "expect 'silent'/garbage transcripts. Try the other calibration set or a16 precision on more layers.")

    # ---- compile
    t1 = time.time()
    hef = runner.compile()
    hef_path = out / f"{name}_{a.tag}_h8l.hef" if a.arch == "hailo8l" else out / f"{name}_{a.tag}_{a.arch}.hef"
    hef_path.write_bytes(hef)
    runner.save_har(str(out / f"{name}_compiled.har"))
    report["compile_s"] = round(time.time() - t1)
    report["hef"] = str(hef_path)
    report["hef_mb"] = round(hef_path.stat().st_size / 2**20, 1)
    (out / "report.json").write_text(json.dumps(report, indent=1))
    res = ROOT / "results" / "hailo_compile"
    res.mkdir(parents=True, exist_ok=True)
    (res / f"{hef_path.stem}.json").write_text(json.dumps(report, indent=1))
    print(f"HEF -> {hef_path}")


if __name__ == "__main__":
    main()
