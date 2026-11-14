"""CLI.

  python -m vieedge run   [-c config.yaml] [--set stt.backend=ct2 ...]   # full assistant + dashboard
  python -m vieedge stt   -c cfg.yaml file.wav                            # transcribe a file
  python -m vieedge ask   -c cfg.yaml "câu hỏi"                           # LLM only (streams to stdout)
  python -m vieedge say   -c cfg.yaml "văn bản" [-o out.wav]              # TTS only
  python -m vieedge devices                                              # list audio devices
"""
from __future__ import annotations

import argparse
import logging
import sys


def _cfg(args):
    from .config import load_config, set_override

    over: dict = {}
    for kv in args.set or []:
        k, v = kv.split("=", 1)
        set_override(over, k, v)
    return load_config(args.config, over)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="vieedge")
    ap.add_argument("cmd", choices=["run", "stt", "ask", "say", "devices"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("-c", "--config")
    ap.add_argument("--set", action="append", help="dotted override, e.g. stt.backend=ct2")
    ap.add_argument("-o", "--out")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if a.cmd == "devices":
        try:
            import alsaaudio

            print("capture:", alsaaudio.pcms(alsaaudio.PCM_CAPTURE))
            print("playback:", alsaaudio.pcms(alsaaudio.PCM_PLAYBACK))
        except ImportError:
            import sounddevice as sd

            print(sd.query_devices())
        return
    cfg = _cfg(a)
    if a.cmd == "run":
        from .pipeline import Assistant

        asst = Assistant(cfg)
        if cfg["web"]["enabled"]:
            from .web.server import start_web

            start_web(asst, cfg["web"]["host"], cfg["web"]["port"], cfg["web"].get("https_port"), cfg["web"].get("cert"), cfg["web"].get("key"))
        asst.run()
    elif a.cmd == "stt":
        import soundfile as sf

        from .stt import make_stt

        stt = make_stt(cfg)
        for path in a.args:
            x, sr = sf.read(path, dtype="float32", always_2d=True)
            x = x.mean(1)
            if sr != 16000:
                from .audio.resample import resample

                x = resample(x, sr, 16000)
            r = stt.transcribe(x[: int(stt.window_s * 16000)])
            print(f"{path}\t{r.text}\t{r.latency_ms:.0f} ms\t{r.timings}")
    elif a.cmd == "ask":
        from .llm.llamacpp_stream import LLMStats, client_from_config, server_from_config
        from .llm.prompts import build_messages

        srv = None
        url = cfg["llm"].get("url")
        if not url:
            srv = server_from_config(cfg)
            srv.start()
            url = srv.url
        cl = client_from_config(cfg, url)
        st = LLMStats()
        for piece in cl.stream_chat(build_messages(" ".join(a.args)), st):
            sys.stdout.write(piece)
            sys.stdout.flush()
        print(f"\n[TTFT {st.ttft_ms:.0f} ms, {st.tok_s:.1f} tok/s, prompt {st.n_prompt} (cached {st.n_cached})]")
        if srv:
            srv.stop()
    elif a.cmd == "say":
        from .tts.piper_tts import PiperTTS

        t = cfg["tts"]
        tts = PiperTTS(cfg.model_path(t["voice"]), t["threads"], t["normalize"])
        r = tts.synthesize(" ".join(a.args))
        print(f"[{r.text_norm}] synth {r.synth_ms:.0f} ms RTF {r.rtf:.3f}")
        if a.out:
            import wave

            import numpy as np

            with wave.open(a.out, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(r.sample_rate)
                w.writeframes((np.clip(r.audio, -1, 1) * 32767).astype("<i2").tobytes())


if __name__ == "__main__":
    main()
