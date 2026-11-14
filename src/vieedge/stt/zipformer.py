"""Vietnamese Zipformer-30M RNN-T (hynt/Zipformer-30M-RNNT-6000h, 6000 h, int8) via sherpa-onnx on the CPU.

On VIVOS it makes ~4x fewer errors than PhoWhisper-tiny (WER 0.041 vs 0.158), stays at 0.059 at 5 dB SNR (PhoWhisper
0.224) and decodes an utterance in ~30 ms on a laptop core (RTF ~0.008). Model licence: CC BY-NC-ND 4.0 (research /
competition use). `confidence` = mean token log-probability, the same convention as the Whisper backends.
"""
from __future__ import annotations

import numpy as np

from .base import STT, STTResult, now


class ZipformerVi(STT):
    name = "zipformer-vi"
    window_s = 30.0  # no fixed window: longer audio is cut by IncrementalASR at the quietest frame

    def __init__(self, model_dir: str, threads: int = 3, method: str = "greedy_search"):
        import sherpa_onnx

        d = model_dir.rstrip("/")
        self.rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=f"{d}/encoder-epoch-20-avg-10.int8.onnx", decoder=f"{d}/decoder-epoch-20-avg-10.int8.onnx",
            joiner=f"{d}/joiner-epoch-20-avg-10.int8.onnx", tokens=f"{d}/tokens.txt", num_threads=threads,
            sample_rate=16000, feature_dim=80, decoding_method=method, modeling_unit="bpe", bpe_vocab=f"{d}/bpe.model")

    def transcribe(self, audio: np.ndarray, beam_size: int | None = None) -> STTResult:
        t0 = now()
        st = self.rec.create_stream()
        st.accept_waveform(16000, np.asarray(audio, dtype=np.float32))
        self.rec.decode_stream(st)
        r = st.result
        t1 = now()
        lp = list(getattr(r, "ys_log_probs", []) or [])
        conf = float(np.mean(lp)) if lp else None
        return STTResult(r.text.strip().lower(), t0, t1, {"encdec_ms": (t1 - t0) * 1e3}, len(r.tokens), confidence=conf)

    def info(self) -> dict:
        return {"name": self.name, "where": "cpu", "precision": "int8", "window_s": self.window_s}
