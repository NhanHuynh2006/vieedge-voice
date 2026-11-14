"""Configuration: one YAML file (deploy/config/*.yaml) merged over built-in defaults.

Switching CPU <-> NPU, models, threads, VAD timings, etc. is done here, never in code (PLAN §16).
Relative model paths are resolved against `paths.models`.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "profile": "pi",
    "os_cfg": None,  # O0..O4 / laptop; default from $VIEEDGE_OS_CFG or /etc/vieedge/env
    "paths": {"models": "/opt/vieedge/models", "results": "/opt/vieedge/results"},
    "cpu": {"main_cores": "0-2"},
    "audio": {
        "backend": "alsa",  # alsa | sounddevice | file | null | remote (phone over WebSocket) | auto (USB card -> alsa, else remote)
        "capture_device": "default",
        "playback_device": "default",
        "sample_rate": 16000,
        "playback_rate": None,  # None -> TTS voice rate
        "period_ms": 20,
        "periods": 4,
        "rt_core": 3,
        "rt_priority": 80,
        "ring_seconds": 30,
        # auto: isolated core + SCHED_FIFO only in O4 (PLAN §6); "force" keeps rt_core/rt_priority as given
        "rt_policy": "auto",
    },
    "input_mode": "both",  # vad | ptt | both
    "vad": {
        "engine": "silero",  # silero | energy
        "model": "vad/silero_vad.onnx",
        "threshold": 0.5,
        "endpoint_ms": 500,
        "min_speech_ms": 200,
        "pre_roll_ms": 300,
        "max_utterance_s": 20.0,
        # an utterance quieter than this (RMS, full scale = 1) is background noise that slipped past the VAD: dropped silently, not answered
        "min_rms": 0.012,
        "min_words": 2,  # a single recognised word is ignored unless it is a prepared command ("dừng", "chào")
        "energy_db": -42.0,
    },
    "echo_guard": {"mode": "mute", "tail_ms": 300},
    "stt": {
        "backend": "hybrid",  # ct2 | hybrid
        "language": "vi",
        "ct2": {
            "model": "stt/ct2/phowhisper-tiny-int8",
            "compute_type": "int8",
            "threads": 2,
            "beam_size": 1,
            "final_beam_size": 1,
        },
        "zipformer": {"model": "stt/zipformer-vi", "threads": 3, "min_confidence": -0.20},
        "hybrid": {
            "encoder": "hailo",  # hailo | onnx
            "hef": "stt/hef/phowhisper-tiny-encoder-10s_vi_h8l.hef",
            "onnx": "stt/onnx/phowhisper-tiny-encoder-10s.onnx",
            "window_s": 10,
            "decoder": "stt/ct2/phowhisper-tiny-int8",
            "compute_type": "int8",
            "threads": 2,
            "beam_size": 1,
            "final_beam_size": 1,
        },
        # below this mean token log-prob the question is not answered ("please repeat"); None = off.
        # Calibrated on PhoWhisper-tiny INT8 (CT2): rejects ~11-17 % of VIVOS questions whose WER is ~0.5, accepted WER 0.15 -> 0.11.
        # Re-calibrate (bench/bench_confidence.py) for the Hailo-encoder path.
        "min_confidence": -0.15,
        "max_new_tokens": 96,
        "repetition_penalty": 1.1,
        "no_repeat_ngram_size": 3,
        "incremental": {"enabled": True, "interval_ms": 750, "speculative_final": True},
    },
    "llm": {
        "server_bin": "llama-server",
        "manage_server": True,
        "url": None,  # set to use an external server instead
        "model": "llm/gguf/qwen2.5-1.5b-vi-voice-Q4_K_M.gguf",
        "draft_model": None,
        "draft_max": 8,
        "threads": 3,
        "cores": "0-2",
        "ctx": 2048,
        "batch": 256,
        "port": 8088,
        "max_tokens": 160,
        "temperature": 0.3,
        "top_p": 0.9,
        "prompt_cache": True,
        "warmup": True,
        "history_turns": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "extra_args": [],
        "startup_timeout_s": 180,
    },
    # Offline knowledge base (Vietnamese Wikipedia, SQLite FTS5). Adds ~100-150 prompt tokens only when the best hit scores
    # above min_score, because on a CPU every prompt token costs prefill time.
    "rag": {"enabled": False, "db": "rag/wiki_vi.sqlite", "k": 6, "max_chars": 240, "max_docs": 1, "min_score": 0.0,
            "title_weight": 6.0},
    # Fast path: reflex rules + prepared answers (FAQ dataset) answered with pre-synthesised audio, no LLM (see vieedge/fastpath).
    # Robot actions of a hit are published as a "reflex" event and appended to <results>/reflex_actions.jsonl.
    "fastpath": {"enabled": False, "faq": "fastpath/faq.jsonl", "phrases": "fastpath/say_phrases.txt", "fuzzy": 0.85,
                 "robot_commands": True, "safety": "an_toan/the_an_toan.json"},  # vetted first-aid / disaster cards (vieedge/safety)
    "tts": {
        "voice": "tts/piper/vi_VN-vais1000-medium.onnx",
        "threads": 1,
        "length_scale": None,
        "noise_scale": None,
        "noise_w": None,
        "normalize": True,
        "espeak_data": None,
        "sentence_silence_ms": 120,
    },
    "pipeline": {
        "stream_sentences": True,
        "first_chunk_min_chars": 8,
        "first_chunk_max_words": 5,
        "min_sentence_chars": 12,
        "max_chunk_chars": 120,
        # play a short pre-synthesised acknowledgement as soon as the question is accepted, while the LLM thinks (perceived latency).
        # The real answer is never delayed by more than the acknowledgement's remaining length; metrics report both (answer_audio_ms).
        "ack": {"enabled": False, "phrases": ["Dạ.", "Vâng.", "Ừm."], "max_ms": 700},
        "no_answer_text": "Xin lỗi, mình chưa nghe rõ. Bạn nói lại được không?",
    },
    "gpio": {"enabled": True, "chip": "auto", "button": 17, "led_listen": 22, "led_think": 23, "led_speak": 24},
    # https_port: browsers only allow the microphone on https (or localhost); the self-signed demo certificate is in deploy/certs.
    "web": {"enabled": True, "host": "0.0.0.0", "port": 8000, "https_port": 8443,
            "cert": "/etc/vieedge/certs/vieedge.crt", "key": "/etc/vieedge/certs/vieedge.key"},
    "telemetry": {"turn_log": "turns", "sysmon_period_s": 1.0, "power": "auto", "ina226_bus": 1, "ina226_addr": 0x40, "ina226_shunt_ohm": 0.01},
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config(dict):
    """dict with attribute access and model-path resolution."""

    def __getattr__(self, k: str) -> Any:
        try:
            v = self[k]
        except KeyError as e:
            raise AttributeError(k) from e
        return Config(v) if isinstance(v, dict) and not isinstance(v, Config) else v

    def model_path(self, rel: str | None) -> str | None:
        if rel is None:
            return None
        p = Path(os.path.expanduser(str(rel)))
        if p.is_absolute():
            return str(p)
        return str(Path(os.path.expanduser(self["paths"]["models"])) / p)

    def results_dir(self) -> Path:
        p = Path(os.path.expanduser(self["paths"]["results"]))
        p.mkdir(parents=True, exist_ok=True)
        return p


def load_config(path: str | os.PathLike | None = None, overrides: dict | None = None) -> Config:
    cfg = copy.deepcopy(DEFAULTS)
    if path is None:
        path = os.environ.get("VIEEDGE_CONFIG")
    if path:
        with open(path, encoding="utf-8") as f:
            cfg = _merge(cfg, yaml.safe_load(f) or {})
    if overrides:
        cfg = _merge(cfg, overrides)
    if not cfg.get("os_cfg"):
        cfg["os_cfg"] = os.environ.get("VIEEDGE_OS_CFG") or _env_file_os_cfg() or "unknown"
    a = cfg["audio"]
    if a.get("rt_policy", "auto") == "auto" and cfg["os_cfg"] in ("O0", "O1", "O2", "O3"):
        a["rt_core"], a["rt_priority"] = None, 0
    return Config(cfg)


def _env_file_os_cfg(path: str = "/etc/vieedge/env") -> str | None:
    try:
        for line in open(path, encoding="utf-8"):
            if line.startswith("VIEEDGE_OS_CFG="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return None


def parse_cpuset(spec: str | None) -> set[int]:
    """'0-2' / '0,1,3' / '0-1,3' -> {0,1,2,...}; None/'' -> all CPUs."""
    if not spec:
        return set(range(os.cpu_count() or 1))
    cpus: set[int] = set()
    for part in str(spec).split(","):
        if "-" in part:
            a, b = part.split("-")
            cpus.update(range(int(a), int(b) + 1))
        elif part.strip():
            cpus.add(int(part))
    avail = set(range(os.cpu_count() or 1))
    return (cpus & avail) or avail


def set_override(cfg: dict, dotted: str, value: str) -> None:
    """--set stt.backend=ct2 style overrides (value parsed as YAML)."""
    keys = dotted.split(".")
    d = cfg
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = yaml.safe_load(value)
