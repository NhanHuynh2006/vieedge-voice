"""S2/S3: encoder on the NPU (or its ONNX stand-in), decoder on the CPU (CTranslate2, KV cache, beam 1/3).

The Hailo decoder HEF has no KV cache (fixed sequence, full recompute every token), so the
autoregressive decoder runs on the CPU where CTranslate2 keeps a KV cache — this is the
community-validated fast split (PLAN §0, §2). CTranslate2's `generate` accepts precomputed
encoder states of any length, so the NPU output (500 or 250 frames) is fed straight in.
"""
from __future__ import annotations

import numpy as np

from .base import STT, STTResult, now
from .cpu_ct2 import _conf
from .mel import window_mel
from .tokens import prompt_tokens, tokens_to_text


class HybridWhisper(STT):
    def __init__(self, encoder, decoder_dir: str, compute_type: str = "int8", threads: int = 2,
                 beam_size: int = 1, language: str = "vi", max_new_tokens: int = 96,
                 repetition_penalty: float = 1.1, no_repeat_ngram_size: int = 3):
        import ctranslate2

        self.ct2 = ctranslate2
        self.encoder = encoder
        self.decoder = ctranslate2.models.Whisper(decoder_dir, device="cpu", compute_type=compute_type,
                                                  inter_threads=1, intra_threads=threads)
        self.window_s = encoder.window_s
        self.prompt = prompt_tokens(language)
        self.beam_size = beam_size
        self.max_new_tokens = max_new_tokens
        self.repetition_penalty = repetition_penalty
        self.no_repeat_ngram_size = no_repeat_ngram_size
        self.compute_type = compute_type
        self.name = f"{encoder.where}-enc+ct2-{compute_type}-dec-{self.window_s:g}s"

    def encode(self, audio: np.ndarray) -> tuple[np.ndarray, float, float]:
        t0 = now()
        mel = window_mel(audio, self.window_s)
        t1 = now()
        h = self.encoder.encode(mel)
        return h, (t1 - t0) * 1e3, (now() - t1) * 1e3

    def decode(self, hidden: np.ndarray, beam_size: int | None = None):
        sv = self.ct2.StorageView.from_array(np.ascontiguousarray(hidden, dtype=np.float32))
        return self.decoder.generate(
            sv, [self.prompt], beam_size=beam_size or self.beam_size,
            max_length=len(self.prompt) + self.max_new_tokens,
            repetition_penalty=self.repetition_penalty, no_repeat_ngram_size=self.no_repeat_ngram_size,
            suppress_blank=True, return_scores=True,
        )[0]

    def transcribe(self, audio: np.ndarray, beam_size: int | None = None) -> STTResult:
        t0 = now()
        h, mel_ms, enc_ms = self.encode(audio)
        t1 = now()
        res = self.decode(h, beam_size)
        t2 = now()
        toks = res.sequences[0]
        return STTResult(tokens_to_text(toks), t0, t2,
                         {"mel_ms": mel_ms, "encoder_ms": enc_ms, "decoder_ms": (t2 - t1) * 1e3}, len(toks),
                         confidence=_conf(res))

    def info(self) -> dict:
        return {"name": self.name, "where": f"{self.encoder.where}+cpu", "precision": self.compute_type,
                "window_s": self.window_s}
