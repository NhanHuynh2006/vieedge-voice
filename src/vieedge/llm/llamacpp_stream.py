"""LLM on the CPU via llama.cpp's llama-server (GGUF), token streaming over HTTP/SSE.

* The server is started pinned to the "thinking" cores (`taskset -c 0-2` in O4) with a single slot,
  so the fixed system prompt stays in the KV cache and only the question is prefilled (M4).
* Speculative decoding (M3): `draft_model` -> `-md draft.gguf --spec-draft-n-max N`.
* Streaming client uses only the standard library (no requests/httpx on the device); closing the
  connection aborts generation (barge-in).
"""
from __future__ import annotations

import http.client
import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class LLMStats:
    t_request: float = 0.0
    t_first_token: float = 0.0
    t_done: float = 0.0
    n_prompt: int = 0
    n_cached: int = 0
    n_predicted: int = 0
    prompt_ms: float = 0.0
    predicted_ms: float = 0.0
    draft_n: int = 0
    draft_accepted: int = 0
    text: str = ""
    cancelled: bool = False
    raw_timings: dict = field(default_factory=dict)

    @property
    def ttft_ms(self) -> float:
        return (self.t_first_token - self.t_request) * 1e3 if self.t_first_token else 0.0

    @property
    def tok_s(self) -> float:
        return self.n_predicted / (self.predicted_ms / 1e3) if self.predicted_ms else 0.0


class LlamaServer:
    def __init__(self, server_bin: str, model: str, port: int = 8088, threads: int = 3, cores: str | None = "0-2",
                 ctx: int = 2048, batch: int = 256, draft_model: str | None = None, draft_max: int = 8,
                 extra_args: list[str] | None = None, log_path: str | None = None, host: str = "127.0.0.1"):
        self.cmd: list[str] = []
        if cores and shutil.which("taskset"):
            self.cmd += ["taskset", "-c", str(cores)]
        self.cmd += [server_bin, "-m", model, "--host", host, "--port", str(port),
                     "-t", str(threads), "-tb", str(threads), "-c", str(ctx), "-b", str(batch), "-ub", str(batch),
                     "-np", "1", "--jinja", "--no-webui"]
        if draft_model:
            self.cmd += ["-md", draft_model, "--spec-draft-n-max", str(draft_max), "-td", str(threads)]
        self.cmd += list(extra_args or [])
        self.port, self.host = port, host
        self.log_path = log_path
        self.proc: subprocess.Popen | None = None

    def start(self, timeout: float = 180.0) -> None:
        log.info("starting llama-server: %s", " ".join(self.cmd))
        out = open(self.log_path, "ab") if self.log_path else subprocess.DEVNULL
        self.proc = subprocess.Popen(self.cmd, stdout=out, stderr=subprocess.STDOUT, preexec_fn=_die_with_parent)
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server exited with {self.proc.returncode} (see {self.log_path})")
            try:
                c = http.client.HTTPConnection(self.host, self.port, timeout=2)
                c.request("GET", "/health")
                r = c.getresponse()
                r.read()
                if r.status == 200:
                    log.info("llama-server ready in %.1fs", time.monotonic() - t0)
                    return
            except OSError:
                pass
            time.sleep(0.25)
        raise TimeoutError("llama-server did not become healthy")

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def _die_with_parent() -> None:
    """PR_SET_PDEATHSIG(SIGTERM): llama-server must not outlive a crashed/killed assistant."""
    try:
        import ctypes
        import signal

        ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)
    except OSError:
        pass


_THINK = re.compile(r"<think>.*?</think>\s*", re.S)


class LlamaClient:
    def __init__(self, url: str, max_tokens: int = 160, temperature: float = 0.3, top_p: float = 0.9,
                 cache_prompt: bool = True, chat_template_kwargs: dict | None = None, timeout: float = 120.0):
        u = url.replace("http://", "")
        self.host, port = (u.split(":") + ["80"])[:2]
        self.port = int(port.split("/")[0])
        self.max_tokens, self.temperature, self.top_p = max_tokens, temperature, top_p
        self.cache_prompt = cache_prompt
        self.chat_template_kwargs = chat_template_kwargs or {}
        self.timeout = timeout

    def _body(self, messages: list[dict], max_tokens: int | None, stream: bool, **kw) -> bytes:
        body = {
            "messages": messages, "stream": stream, "max_tokens": max_tokens or self.max_tokens,
            "temperature": self.temperature, "top_p": self.top_p, "cache_prompt": self.cache_prompt,
            "chat_template_kwargs": self.chat_template_kwargs, "timings_per_token": False,
        }
        body.update(kw)
        return json.dumps(body, ensure_ascii=False).encode("utf-8")

    def stream_chat(self, messages: list[dict], stats: LLMStats | None = None, cancel: threading.Event | None = None,
                    max_tokens: int | None = None, **kw) -> Iterator[str]:
        """Yield text pieces as they are generated. Fills `stats` (TTFT, tok/s, cache hits)."""
        stats = stats if stats is not None else LLMStats()
        stats.t_request = time.monotonic()
        conn = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        conn.request("POST", "/v1/chat/completions", body=self._body(messages, max_tokens, True, **kw),
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(f"llama-server HTTP {resp.status}: {resp.read()[:300]!r}")
        in_think = False
        pending = ""
        try:
            for raw in resp:
                if cancel is not None and cancel.is_set():
                    stats.cancelled = True
                    break
                line = raw.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                obj = json.loads(data)
                if "timings" in obj:
                    _fill_timings(stats, obj["timings"])
                ch = (obj.get("choices") or [{}])[0]
                piece = (ch.get("delta") or {}).get("content") or ""
                if not piece:
                    continue
                # drop <think>…</think> if a template still emits it
                pending += piece
                if "<think>" in pending:
                    in_think = True
                if in_think:
                    if "</think>" in pending:
                        pending = pending.split("</think>", 1)[1].lstrip()
                        in_think = False
                    else:
                        continue
                if pending.startswith("<") and len(pending) < 8 and "<think>".startswith(pending):
                    continue
                out, pending = pending, ""
                if out:
                    if not stats.t_first_token:
                        stats.t_first_token = time.monotonic()
                    stats.text += out
                    yield out
        finally:
            stats.t_done = time.monotonic()
            try:
                resp.close()
                conn.close()
            except Exception:
                pass

    def complete(self, messages: list[dict], max_tokens: int | None = None, **kw) -> tuple[str, LLMStats]:
        st = LLMStats()
        text = "".join(self.stream_chat(messages, st, max_tokens=max_tokens, **kw))
        return _THINK.sub("", text).strip(), st

    def warmup(self, messages: list[dict]) -> LLMStats:
        """Prefill the system prompt so its KV cache is resident before the first question."""
        _, st = self.complete(messages, max_tokens=1)
        return st


def _fill_timings(st: LLMStats, t: dict) -> None:
    st.raw_timings = t
    st.n_prompt = int(t.get("prompt_n", 0))
    st.n_cached = int(t.get("cache_n", 0))
    st.n_predicted = int(t.get("predicted_n", 0))
    st.prompt_ms = float(t.get("prompt_ms", 0.0))
    st.predicted_ms = float(t.get("predicted_ms", 0.0))
    st.draft_n = int(t.get("draft_n", 0))
    st.draft_accepted = int(t.get("draft_n_accepted", 0))


def server_from_config(cfg, log_dir: str | None = None) -> LlamaServer:
    l = cfg["llm"]
    return LlamaServer(
        os.path.expanduser(l["server_bin"]), cfg.model_path(l["model"]), port=l["port"], threads=l["threads"], cores=l.get("cores"),
        ctx=l["ctx"], batch=l["batch"], draft_model=cfg.model_path(l.get("draft_model")), draft_max=l.get("draft_max", 8),
        extra_args=l.get("extra_args"), log_path=os.path.join(log_dir, "llama-server.log") if log_dir else None,
    )


def client_from_config(cfg, url: str) -> LlamaClient:
    l = cfg["llm"]
    return LlamaClient(url, l["max_tokens"], l["temperature"], l["top_p"], l["prompt_cache"], l.get("chat_template_kwargs"))
