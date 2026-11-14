"""Piper (VITS) text-to-speech on the CPU with ONNX Runtime, voices vi_VN-* (T0/T1).

normalize (vi_normalize) -> espeak-ng IPA -> Piper phoneme ids -> VITS ONNX -> float32 PCM.
`synthesize` works per sentence so the pipeline can start playing the first sentence while the
LLM is still generating the rest (P1).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

import numpy as np

from .phonemizer import EspeakPhonemizer
from .vi_normalize import normalize

BOS, EOS, PAD = "^", "$", "_"


@dataclass
class TTSResult:
    audio: np.ndarray  # float32 [-1, 1]
    sample_rate: int
    t_start: float
    t_end: float
    text_norm: str
    n_phonemes: int

    @property
    def synth_ms(self) -> float:
        return (self.t_end - self.t_start) * 1e3

    @property
    def rtf(self) -> float:
        dur = len(self.audio) / self.sample_rate
        return (self.t_end - self.t_start) / dur if dur else 0.0


class PiperTTS:
    def __init__(self, model_path: str, threads: int = 1, normalize_text: bool = True,
                 length_scale: float | None = None, noise_scale: float | None = None, noise_w: float | None = None,
                 espeak_data: str | None = None):
        import onnxruntime as ort

        with open(model_path + ".json", encoding="utf-8") as f:
            self.config = json.load(f)
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.sess = ort.InferenceSession(model_path, sess_options=so, providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.sess.get_inputs()}
        self.sample_rate = int(self.config["audio"]["sample_rate"])
        self.id_map: dict[str, list[int]] = self.config["phoneme_id_map"]
        inf = self.config.get("inference", {})
        self.scales = np.array([
            noise_scale if noise_scale is not None else inf.get("noise_scale", 0.667),
            length_scale if length_scale is not None else inf.get("length_scale", 1.0),
            noise_w if noise_w is not None else inf.get("noise_w", 0.8),
        ], dtype=np.float32)
        self.phonemizer = EspeakPhonemizer(self.config.get("espeak", {}).get("voice", "vi"), espeak_data)
        self.normalize_text = normalize_text
        self.name = model_path.rsplit("/", 1)[-1].replace(".onnx", "")

    def phonemes_to_ids(self, phonemes: str) -> list[int]:
        ids = list(self.id_map[BOS]) + list(self.id_map[PAD])
        for ph in phonemes:
            if ph in self.id_map:
                ids.extend(self.id_map[ph])
                ids.extend(self.id_map[PAD])
        ids.extend(self.id_map[EOS])
        return ids

    def _infer(self, ids: list[int]) -> np.ndarray:
        x = np.array([ids], dtype=np.int64)
        feeds = {"input": x, "input_lengths": np.array([len(ids)], dtype=np.int64), "scales": self.scales}
        if "sid" in self.input_names:
            feeds["sid"] = np.array([0], dtype=np.int64)
        return self.sess.run(None, feeds)[0].reshape(-1).astype(np.float32)

    def synthesize(self, text: str, normalize_text: bool | None = None) -> TTSResult:
        t0 = time.monotonic()
        norm = normalize(text) if (self.normalize_text if normalize_text is None else normalize_text) else text
        chunks = []
        n_ph = 0
        for sent in self.phonemizer.phonemize(norm):
            ids = self.phonemes_to_ids(sent)
            n_ph += len(sent)
            if len(ids) > 3:
                chunks.append(self._infer(ids))
        audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak > 1.0:
            audio = audio / peak
        return TTSResult(audio, self.sample_rate, t0, time.monotonic(), norm, n_ph)

    def warmup(self) -> None:
        self.synthesize("Xin chào.")
