"""End-to-end assistant: mic -> VAD -> incremental ASR (NPU encoder / CPU decoder) -> LLM (CPU, streaming)
-> sentence segmenter -> Vietnamese normaliser -> Piper TTS -> speaker.  (PLAN §4)

Threads in the main process (pinned to cpu.main_cores, i.e. cores 0-2 in O4):
  listen   : reads 32 ms frames from the RT audio process, echo guard, VAD/endpointing, feeds ASR
  asr      : IncrementalASR worker (partials, speculative final)
  respond  : question -> LLM stream -> chunks
  speak    : chunks -> TTS -> playback ring
  sysmon   : telemetry; web server runs in its own thread (vieedge.web.server)
The audio process itself lives on the isolated core with SCHED_FIFO (audio/rt_engine.py).
"""
from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
from pathlib import Path

from .audio.capture import MicStream
from .audio.echo_guard import EchoGuard
from .audio.playback import Speaker
from .audio.rt_engine import AudioEngine, resolve_backend
from .audio.vad import Endpointer, make_vad
from .config import Config, parse_cpuset
from .events import EventBus
from .fastpath import FastPath, Hit
from .llm.llamacpp_stream import LLMStats, client_from_config, server_from_config
from .llm.prompts import build_messages
from .rag import KnowledgeBase, build_prompt_context
from .rt import pin_current_thread
from .stt import make_stt
from .stt.incremental import IncrementalASR
from .telemetry.sysmon import SysMon, proc_rss_mb
from .telemetry.timeline import Turn, TurnLog
from .textproc import normalize_question
from .tts.piper_tts import PiperTTS
from .tts.segmenter import SentenceSegmenter

log = logging.getLogger(__name__)


def looks_like_noise(audio, text: str, min_rms: float, min_words: int, prepared: bool = False) -> bool:
    """Background noise that passed the VAD: too quiet to be speech, or a transcript too short to be a question."""
    import numpy as np

    x = np.asarray(audio, dtype=np.float32)
    if x.size and float(np.sqrt(np.mean(np.square(x)))) < min_rms:
        return True
    return bool(text) and len(text.split()) < min_words and not prepared


class Assistant:
    def __init__(self, cfg: Config, bus: EventBus | None = None):
        self.cfg = cfg
        self.bus = bus or EventBus()
        self.state = "booting"
        self.t_boot = time.monotonic()
        pin_current_thread(parse_cpuset(cfg["cpu"]["main_cores"]))
        self.results = cfg.results_dir()
        self.turn_log = TurnLog(self.results / cfg["telemetry"]["turn_log"])

        # --- TTS first: its sample rate fixes the playback rate
        t = cfg["tts"]
        self.tts = PiperTTS(cfg.model_path(t["voice"]), t["threads"], t["normalize"], t["length_scale"],
                            t["noise_scale"], t["noise_w"], t["espeak_data"])

        # --- RT audio process
        acfg = dict(cfg["audio"])
        acfg["backend"] = resolve_backend(acfg)
        self.engine = AudioEngine(acfg, playback_rate=self.tts.sample_rate)
        self.audio_info = self.engine.start()
        self.speaker = Speaker(self.engine)
        eg = cfg["echo_guard"]
        self.mic = MicStream(self.engine, 512, EchoGuard(eg["mode"], eg["tail_ms"]))

        # --- VAD / endpointing
        v = cfg["vad"]
        self.vad = make_vad(v, cfg.model_path(v["model"]))
        self.endpointer = Endpointer(v["threshold"], v["endpoint_ms"], v["min_speech_ms"], v["pre_roll_ms"], v["max_utterance_s"])

        # --- STT (one or more backends preloaded for the on-stage CPU vs NPU comparison)
        self.stt_backends = {}
        for b in dict.fromkeys([cfg["stt"]["backend"]] + list(cfg["pipeline"].get("preload_stt", []))):
            try:
                self.stt_backends[b] = make_stt(cfg, b)
                self.stt_backends[b].warmup()
            except Exception as e:
                if b == cfg["stt"]["backend"]:
                    raise
                log.warning("could not preload STT backend %s: %s", b, e)
        self.stt_name = cfg["stt"]["backend"]
        inc = cfg["stt"]["incremental"]
        self.asr = IncrementalASR(self.stt_backends[self.stt_name], inc["interval_ms"], inc["speculative_final"],
                                  self._final_beam(self.stt_name), inc["enabled"],
                                  on_partial=lambda s: self.bus.publish("partial", text=s))

        # --- offline knowledge base
        self.kb = None
        self.rag_on = bool(cfg["rag"]["enabled"])
        rg = cfg["rag"]
        if rg["enabled"]:
            try:
                self.kb = KnowledgeBase(cfg.model_path(rg["db"]))
                self.kb.search("xin chào")  # warm the page cache
            except Exception as e:
                log.warning("RAG disabled (%s)", e)

        # --- LLM
        l = cfg["llm"]
        self.llm_server = None
        url = l.get("url")
        if l["manage_server"] and not url:
            self.llm_server = server_from_config(cfg, str(self.results))
            self.llm_server.start(l["startup_timeout_s"])
            url = self.llm_server.url
        self.llm = client_from_config(cfg, url)
        self.history: list[tuple[str, str]] = []
        if l["warmup"]:
            st = self.llm.warmup(build_messages("Xin chào"))
            log.info("LLM warm-up: prompt %d tok in %.0f ms", st.n_prompt, st.prompt_ms)
        self.tts.warmup()
        self._acks = self._prepare_acks()
        self._ack_i = 0
        self.fast = None
        fc = cfg["fastpath"]
        if fc["enabled"]:
            self.fast = FastPath(cfg.model_path(fc["faq"]), fc["fuzzy"], fc["robot_commands"], safety_path=cfg.model_path(fc.get("safety")))
            self._fast_cache = self.results / "fastpath_cache"
            ph = Path(cfg.model_path(fc["phrases"]))
            self.fast.prewarm(self.tts, [cfg["pipeline"]["no_answer_text"]]
                              + ([x for x in ph.read_text(encoding="utf-8").split("\n") if x] if ph.exists() else [])
                              + (self.fast.safety.phrases() if self.fast.safety else []),
                              self._fast_cache)

        # --- runtime state
        self._q_questions: queue.Queue = queue.Queue()
        self._q_chunks: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._busy = threading.Event()  # thinking or speaking
        self._ptt = False
        self._turn: Turn | None = None
        self._active_turn = 0
        self._turn_done = threading.Condition()
        self._last_turn: dict | None = None
        self._stop = threading.Event()
        self.sysmon = SysMon(cfg["telemetry"]["sysmon_period_s"], extra=[self._extra_metrics],
                             on_sample=lambda s: self.bus.publish("sys", **s))
        self._power = None
        try:
            from .telemetry.power import PowerMeter

            tl = cfg["telemetry"]
            self._power = PowerMeter(tl["power"], tl["ina226_bus"], tl["ina226_addr"], tl["ina226_shunt_ohm"])
        except Exception:
            self._power = None
        self.t_ready = time.monotonic()

    # ------------------------------------------------------------------ helpers
    def _final_beam(self, backend: str) -> int:
        s = self.cfg["stt"]
        return int((s["hybrid"] if backend == "hybrid" else s["ct2"]).get("final_beam_size", 1))

    def _extra_metrics(self) -> dict:
        d = {"xruns": self.engine.xruns(), "state": self.state, "stt": self.stt_name, "rag": self.rag_on and self.kb is not None,
             "os_cfg": self.cfg["os_cfg"]}
        stt = self.stt_backends.get(self.stt_name)
        enc = getattr(stt, "encoder", None)
        if enc is not None:
            d["enc_where"] = enc.where
            d["npu_calls"] = enc.calls
            d["npu_busy_s"] = round(enc.busy_s, 3)
            d["npu_temp_c"] = enc.chip_temperature()
        if self.llm_server and self.llm_server.proc:
            d["llm_rss_mb"] = proc_rss_mb(self.llm_server.proc.pid)
        d["app_rss_mb"] = proc_rss_mb(os.getpid())
        if self._power is not None:
            d.update(self._power.read())
        return d

    def set_state(self, s: str) -> None:
        if s != self.state:
            self.state = s
            self.bus.publish("state", state=s)
            if hasattr(self, "io"):
                self.io.set_state(s)

    def set_rag(self, on: bool) -> bool:
        if self.kb is None:
            return False
        self.rag_on = bool(on)
        self.bus.publish("config", rag=self.rag_on)
        return True

    def set_stt_backend(self, name: str) -> bool:
        if name not in self.stt_backends:
            return False
        self.stt_name = name
        self.asr.stt = self.stt_backends[name]
        self.asr.final_beam = self._final_beam(name)
        self.bus.publish("config", stt=name)
        return True

    # ------------------------------------------------------------------ input events
    def ptt_press(self) -> None:
        if self._busy.is_set():
            self.barge_in()
        self._ptt = True
        t = time.monotonic()
        self._begin_turn(t)
        self.endpointer.force_start(t)
        self.asr.start()
        self.set_state("listening")

    def ptt_release(self) -> None:
        self._ptt = False
        ev = self.endpointer.force_end(time.monotonic())
        if ev is not None:
            self._on_end(ev.audio, ev.t_speech_end, ev.t, ptt=True)

    def barge_in(self) -> None:
        self._cancel.set()
        self.asr.cancel()
        keep = []  # drop pending sentences but keep end-of-turn markers so the turn is still logged/closed
        while True:
            try:
                item = self._q_chunks.get_nowait()
            except queue.Empty:
                break
            if item[1] is None:
                keep.append(item)
        for item in keep:
            self._q_chunks.put(item)
        self.speaker.stop()
        self.bus.publish("barge_in")

    def _prepare_acks(self) -> list:
        """Pre-synthesise the acknowledgement phrases once (they cost TTS time only at start-up)."""
        a = self.cfg["pipeline"].get("ack") or {}
        out = []
        if not a.get("enabled"):
            return out
        for ph in a.get("phrases", []):
            r = self.tts.synthesize(ph)
            ms = len(r.audio) / r.sample_rate * 1e3
            if ms <= a.get("max_ms", 700):
                out.append((ph, r.audio, r.sample_rate, ms))
        return out

    def ask_text(self, text: str) -> None:
        """A typed question (phone app or dashboard): same path as a spoken one from the fast path on, no STT."""
        q = normalize_question(text)
        if not q:
            return
        self.barge_in()
        now = time.monotonic()
        self._begin_turn(now)
        turn, self._turn = self._turn, None
        turn.t["speech_end"] = now
        turn.mark("stt_final", now)
        turn.meta["typed"] = True
        turn.question = q
        self.bus.publish("final", text=q, raw=text, speculative=False)
        self._q_questions.put((turn, q))

    def _begin_turn(self, t: float) -> None:
        self._turn = self.turn_log.new_turn(stt=self.stt_name, os_cfg=self.cfg["os_cfg"], llm=self.cfg["llm"]["model"],
                                            tts=self.tts.name, wall_minus_mono=time.time() - time.monotonic())
        self._turn.mark("speech_start", t)

    # ------------------------------------------------------------------ threads
    def run(self, block: bool = True) -> None:
        from .gpio import StatusIO

        self.io = StatusIO(self.cfg["gpio"], self.ptt_press, self.ptt_release)
        self.io.start()
        self.sysmon.start()
        threads = [threading.Thread(target=self._listen_loop, daemon=True, name="listen"),
                   threading.Thread(target=self._respond_loop, daemon=True, name="respond"),
                   threading.Thread(target=self._speak_loop, daemon=True, name="speak")]
        for th in threads:
            th.start()
        self.set_state("idle")
        ready_ms = (time.monotonic() - self.t_boot) * 1e3
        self.bus.publish("ready", init_ms=round(ready_ms), audio=self.audio_info)
        log.info("VieEdge ready (init %.0f ms) — listening", ready_ms)
        _mark_ready()
        if block:
            try:
                while not self._stop.wait(0.5):
                    pass
            except KeyboardInterrupt:
                pass
            finally:
                self.close()

    def _listen_loop(self) -> None:
        mode = self.cfg["input_mode"]
        for fr in self.mic.frames():
            if self._stop.is_set():
                break
            if self._busy.is_set() and not self._ptt:
                continue  # thinking/speaking: only the button can interrupt
            prob = self.vad(fr.pcm)
            if mode == "ptt" and not self._ptt:
                self.endpointer._pre.append(fr.pcm)  # keep pre-roll for the button press
                continue
            for ev in self.endpointer.push(fr.pcm, prob, fr.t_end):
                if ev.kind == "start" and not self._ptt:
                    self._begin_turn(ev.t)
                    self.asr.start()
                    self.set_state("listening")
                elif ev.kind == "pause":
                    if self._turn:
                        self._turn.t["speech_end"] = ev.t_speech_end
                    self.asr.pause(ev.audio)
                elif ev.kind == "resume":
                    self.asr.resume()
                elif ev.kind == "end" and not self._ptt:
                    self._on_end(ev.audio, ev.t_speech_end, ev.t, ptt=False)
            if self.endpointer.state != "idle":
                self.asr.update(self.endpointer.audio())

    def _on_end(self, audio, t_speech_end: float, t_endpoint: float, ptt: bool) -> None:
        if self._turn is None:
            self._begin_turn(t_speech_end)
        turn = self._turn
        turn.t["speech_end"] = t_speech_end or t_endpoint
        turn.mark("endpoint", t_endpoint)
        vc = self.cfg["vad"]
        if not ptt and looks_like_noise(audio, "", vc["min_rms"], 0):  # too quiet to be speech: ignore, do not even say "please repeat"
            turn.meta["dropped"] = "quiet"
            self._turn = None
            self.set_state("idle")
            return
        self._busy.set()
        self.set_state("thinking")
        fin = self.asr.finish(audio)
        # a speculative hit may be ready before the endpoint fired; it cannot be earlier than speech end
        turn.mark("stt_final", max(fin.t_ready, turn.t["speech_end"]))
        turn.meta.update(stt_speculative_hit=fin.speculative_hit, stt_decode_ms=round(fin.decode_ms, 1),
                         stt_segments=fin.n_segments, utt_s=round(len(audio) / 16000, 2))
        q = normalize_question(fin.text)
        if not ptt and q and looks_like_noise(audio, q, 0.0, vc["min_words"], prepared=self.fast is not None and self.fast.lookup(q) is not None):
            turn.meta["dropped"] = "one word"            # a lone "ừ" / "alo" from noise: not a question
            self._busy.clear()
            self._turn = None
            self.set_state("idle")
            return
        sc = self.cfg["stt"]
        thr = sc.get(self.stt_name, {}).get("min_confidence", sc.get("min_confidence"))  # per-backend calibration
        turn.meta["stt_confidence"] = None if fin.confidence is None else round(fin.confidence, 3)
        if q and thr is not None and fin.confidence is not None and fin.confidence < thr:
            turn.meta["rejected_low_confidence"] = True
            q = ""  # not sure what was said: ask to repeat instead of answering something else
        self.bus.publish("final", text=q, raw=fin.text, speculative=fin.speculative_hit)
        if not q:
            if ptt or turn.meta.get("rejected_low_confidence"):
                self._q_questions.put((turn, None))
            else:
                self._busy.clear()
                self._turn = None
                self.set_state("idle")
            return
        turn.question = q
        self._q_questions.put((turn, q))
        self._turn = None

    def _retrieve(self, q: str, turn: Turn) -> str | None:
        if self.kb is None or not self.rag_on:
            return None
        rg = self.cfg["rag"]
        t0 = time.monotonic()
        hits = self.kb.search(q, rg["k"], rg["title_weight"])
        ctx = build_prompt_context(hits, rg["max_chars"], rg["min_score"], rg["max_docs"])
        turn.meta["rag_ms"] = round((time.monotonic() - t0) * 1e3, 1)
        turn.meta["rag_titles"] = [h["title"] for h in hits[:3]]
        turn.meta["rag_used"] = bool(ctx)
        return ctx or None

    def _respond_loop(self) -> None:
        p = self.cfg["pipeline"]
        while not self._stop.is_set():
            try:
                turn, q = self._q_questions.get(timeout=0.2)
            except queue.Empty:
                continue
            self._cancel.clear()
            self._active_turn = turn.turn_id
            self.speaker.begin_turn()
            stats = LLMStats()
            self._ack_end = 0.0
            if q is not None and self.fast is not None:
                hit = self.fast.lookup(q)
                if hit is not None:
                    self._answer_fast(turn, q, hit)
                    continue
            if q is not None and self._acks:
                ph, audio, sr, ms = self._acks[self._ack_i % len(self._acks)]
                self._ack_i += 1
                self.speaker.play(audio, sr)
                turn.mark("ack_audio")
                turn.meta["ack"] = ph
                self._ack_end = time.monotonic() + ms / 1e3
            if q is None:
                if self.fast is not None:  # "please repeat" is a fixed sentence: play it from the cache instead of synthesising
                    self._answer_fast(turn, "", Hit(p["no_answer_text"], [], "repeat", "static"))
                    continue
                self._q_chunks.put((turn, p["no_answer_text"], True))
                self._q_chunks.put((turn, None, True))
                continue
            seg = SentenceSegmenter(p["first_chunk_min_chars"], p["min_sentence_chars"], p["max_chunk_chars"],
                                    p.get("first_chunk_max_words", 0))
            hist = self.history[-self.cfg["llm"]["history_turns"]:] if self.cfg["llm"]["history_turns"] else []
            context = self._retrieve(q, turn)
            msgs = build_messages(q, hist, context=context)
            turn.mark("llm_request")
            full = []
            try:
                for piece in self.llm.stream_chat(msgs, stats, self._cancel):
                    turn.mark("llm_first_token", stats.t_first_token or None)
                    self.bus.publish("token", text=piece)
                    full.append(piece)
                    if p["stream_sentences"]:
                        for chunk in seg.push(piece):
                            turn.mark("first_chunk")
                            self._q_chunks.put((turn, chunk, False))
            except Exception as e:
                log.exception("LLM error: %s", e)
                self._q_chunks.put((turn, "Xin lỗi, mình gặp lỗi khi suy nghĩ.", False))
            turn.mark("llm_done")
            rest = seg.flush() if p["stream_sentences"] else ["".join(full)]
            for chunk in rest:
                turn.mark("first_chunk")
                self._q_chunks.put((turn, chunk, False))
            answer = "".join(full).strip()
            turn.answer = answer
            turn.meta.update(llm_prompt_n=stats.n_prompt, llm_cached_n=stats.n_cached, llm_pred_n=stats.n_predicted,
                             llm_tok_s=round(stats.tok_s, 2), llm_prompt_ms=round(stats.prompt_ms, 1),
                             llm_draft_n=stats.draft_n, llm_draft_acc=stats.draft_accepted, cancelled=stats.cancelled)
            self.bus.publish("answer_done", text=answer)
            if answer and not stats.cancelled:
                self.history.append((q, answer))
            self._q_chunks.put((turn, None, False))  # end-of-turn marker

    def _answer_fast(self, turn: Turn, q: str, hit) -> None:
        """Prepared answer: play the pre-synthesised sentence straight away, publish the robot actions, no RAG/LLM/TTS."""
        t0 = time.monotonic()
        audio, sr = self.fast.audio(hit.say, self.tts, self._fast_cache)
        self.set_state("speaking")
        self.speaker.play(audio, sr)
        turn.mark("answer_audio")
        turn.answer = hit.say
        turn.meta.update(fast=hit.source, fast_intent=hit.intent, fast_ms=round((time.monotonic() - t0) * 1e3, 2),
                         n_actions=len(hit.actions))
        self.bus.publish("reflex", text=hit.say, intent=hit.intent, source=hit.source, actions=hit.actions)
        if hit.actions:
            with open(self.results / "reflex_actions.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": time.time(), "q": q, "intent": hit.intent, "say": hit.say, "actions": hit.actions},
                                   ensure_ascii=False) + "\n")
        self._q_chunks.put((turn, None, False))  # end-of-turn marker: logs the turn once playback finishes

    def _speak_loop(self) -> None:
        gap = self.cfg["tts"]["sentence_silence_ms"]
        while not self._stop.is_set():
            try:
                turn, chunk, _ = self._q_chunks.get(timeout=0.2)
            except queue.Empty:
                continue
            if chunk is None:  # end of turn: wait for playback, then log
                self.speaker.wait_done()
                fa = self.speaker.first_audio_time()
                if fa:
                    turn.mark("first_audio", fa)
                turn.mark("audio_done")
                turn.meta["xruns"] = self.engine.xruns()
                rec = self.turn_log.write(turn)
                self.bus.publish("turn", **rec)
                with self._turn_done:
                    self._last_turn = rec
                    self._turn_done.notify_all()
                if self._active_turn == turn.turn_id:  # an interrupted older turn must not release a newer one
                    self._busy.clear()
                    self.set_state("idle")
                continue
            if self._cancel.is_set():
                continue
            self.set_state("speaking")
            r = self.tts.synthesize(chunk)
            turn.mark("tts_first_done")
            turn.meta.setdefault("tts_ms", []).append(round(r.synth_ms, 1))
            if self._cancel.is_set():
                continue
            self.speaker.play(r.audio, r.sample_rate)
            turn.mark("answer_audio", max(time.monotonic(), getattr(self, "_ack_end", 0.0)))
            if gap:
                self.speaker.silence(gap)
            fa = self.speaker.first_audio_time()
            if fa:
                turn.mark("first_audio", fa)

    # ------------------------------------------------------------------ benchmarks / shutdown
    def wait_turn(self, timeout: float = 120.0) -> dict | None:
        with self._turn_done:
            self._last_turn = None
            self._turn_done.wait(timeout)
            return self._last_turn

    def close(self) -> None:
        self._stop.set()
        self.mic.stop()
        self.asr.close()
        self.sysmon.stop()
        if hasattr(self, "io"):
            self.io.close()
        if self.llm_server:
            self.llm_server.stop()
        self.engine.stop()


def _mark_ready() -> None:
    """Boot-time measurement: os_bench.sh reads this file's mtime vs. kernel start."""
    for p in ("/run/vieedge-ready", "/tmp/vieedge-ready"):
        try:
            with open(p, "w") as f:
                f.write(f"{time.time():.3f}\n")
            return
        except OSError:
            continue
