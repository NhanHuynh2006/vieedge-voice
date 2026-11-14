"""S0/S1: PhoWhisper entirely on the CPU with CTranslate2 (FP32 = S0, INT8 = S1).

`window_s` = 30 reproduces the standard Whisper/faster-whisper setup (audio padded to 30 s);
`window_s` = 10 feeds a 10 s mel (CTranslate2 slices the positional embedding) — same window
as the Hailo encoder, so CPU and NPU are compared on equal input.
"""
from __future__ import annotations

import numpy as np

from .base import STT, STTResult, now
from .mel import window_mel
from .tokens import prompt_tokens, tokens_to_text


class CT2Whisper(STT):
    name = "ct2"

    def __init__(self, model_dir: str, compute_type: str = "int8", threads: int = 2, beam_size: int = 1,
                 language: str = "vi", window_s: float = 30.0, max_new_tokens: int = 96,
                 repetition_penalty: float = 1.1, no_repeat_ngram_size: int = 3):
        import ctranslate2

        self.ct2 = ctranslate2
        self.model = ctranslate2.models.Whisper(model_dir, device="cpu", compute_type=compute_type,
                                                inter_threads=1, intra_threads=threads)
        self.n_mels = self.model.n_mels if hasattr(self.model, "n_mels") else 80
        self.prompt = prompt_tokens(language)
        self.beam_size = beam_size
        self.window_s = window_s
        self.max_new_tokens = max_new_tokens
        self.repetition_penalty = repetition_penalty
        self.no_repeat_ngram_size = no_repeat_ngram_size
        self.compute_type = compute_type
        self.name = f"ct2-{compute_type}-{int(window_s)}s"

    def _generate(self, features, beam_size: int):
        return self.model.generate(
            features, [self.prompt], beam_size=beam_size, max_length=len(self.prompt) + self.max_new_tokens,
            repetition_penalty=self.repetition_penalty, no_repeat_ngram_size=self.no_repeat_ngram_size,
            suppress_blank=True, return_scores=True,
        )[0]

    def transcribe(self, audio: np.ndarray, beam_size: int | None = None) -> STTResult:
        t0 = now()
        mel = window_mel(audio, self.window_s, self.n_mels)
        t1 = now()
        res = self._generate(self.ct2.StorageView.from_array(mel[None]), beam_size or self.beam_size)
        t2 = now()
        toks = res.sequences[0]
        return STTResult(tokens_to_text(toks), t0, t2, {"mel_ms": (t1 - t0) * 1e3, "encdec_ms": (t2 - t1) * 1e3}, len(toks),
                         confidence=_conf(res))

    def info(self) -> dict:
        return {"name": self.name, "where": "cpu", "precision": self.compute_type, "window_s": self.window_s}


def _conf(res) -> float | None:
    try:
        return float(res.scores[0])
    except (AttributeError, IndexError, TypeError):
        return None
