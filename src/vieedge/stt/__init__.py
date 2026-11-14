"""Speech-to-text backends behind one interface; `make_stt(cfg)` picks CPU or NPU from config."""
from __future__ import annotations

from .base import STT, STTResult


def make_stt(cfg, backend: str | None = None) -> STT:
    s = cfg["stt"]
    backend = backend or s["backend"]
    common = dict(language=s["language"], max_new_tokens=s["max_new_tokens"],
                  repetition_penalty=s["repetition_penalty"], no_repeat_ngram_size=s["no_repeat_ngram_size"])
    if backend == "ct2":
        from .cpu_ct2 import CT2Whisper

        c = s["ct2"]
        return CT2Whisper(cfg.model_path(c["model"]), c["compute_type"], c["threads"], c["beam_size"],
                          window_s=c.get("window_s", 30), **common)
    if backend == "zipformer":
        from .zipformer import ZipformerVi

        z = s["zipformer"]
        return ZipformerVi(cfg.model_path(z["model"]), z["threads"])
    if backend == "hybrid":
        from .cpu_decoder import HybridWhisper

        h = s["hybrid"]
        if h["encoder"] == "hailo":
            from .hailo_encoder import HailoEncoder

            enc = HailoEncoder(cfg.model_path(h["hef"]))
        else:
            from .hailo_encoder import OnnxEncoder

            enc = OnnxEncoder(cfg.model_path(h["onnx"]), threads=h["threads"])
        return HybridWhisper(enc, cfg.model_path(h["decoder"]), h["compute_type"], h["threads"], h["beam_size"], **common)
    raise ValueError(f"unknown stt backend {backend}")


__all__ = ["STT", "STTResult", "make_stt"]
