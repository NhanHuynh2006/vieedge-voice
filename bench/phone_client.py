#!/usr/bin/env python3
"""Pretends to be the phone: streams WAV questions to /audio as a microphone in real time and listens to the answer.

  phone_client.py --url ws://192.168.196.114:8000/audio data/e2e/cmd/q000.wav [more.wav ...]

Prints, per question, the time from the last spoken sample (not the padding after it) to the first audible sample received (what a person waits for, minus the phone's own
60 ms playback buffer), and saves the reply as WAV. Use `wss://host:8443/audio` with --insecure for the self-signed certificate.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import time
import wave

import numpy as np


def load16k(path: str) -> np.ndarray:
    with wave.open(path) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)
        if ch > 1:
            x = x.reshape(-1, ch).mean(axis=1)
    if sr != 16000:
        from vieedge.audio.resample import resample

        x = resample(x / 32768, sr, 16000) * 32768
    return np.clip(x, -32768, 32767).astype(np.int16)


async def ask(url: str, wav: str, ssl_ctx, tail_s: float, listen_s: float, out: str | None):
    import websockets

    x = load16k(wav)
    async with websockets.connect(url, ssl=ssl_ctx, max_size=None) as ws:
        hello = json.loads(await ws.recv())
        rate = hello["rate"]
        got: list[bytes] = []
        t_first = None
        t_end = None
        speech_end_idx = int(np.nonzero(np.abs(x) > 500)[0][-1]) // 320 if np.any(np.abs(x) > 500) else len(x) // 320 - 1

        async def rx():
            nonlocal t_first
            async for m in ws:
                if isinstance(m, bytes):
                    pcm = np.frombuffer(m, dtype=np.int16)
                    got.append(m)
                    if t_first is None and np.abs(pcm).max() > 300:
                        t_first = time.monotonic()

        task = asyncio.create_task(rx())
        t0 = time.monotonic()
        frames = list(x[: len(x) // 320 * 320].reshape(-1, 320)) + [np.zeros(320, np.int16)] * int(tail_s / 0.02)
        for i, f in enumerate(frames):                    # real-time pacing, 20 ms per frame
            await ws.send(f.tobytes())
            if i == speech_end_idx:
                t_end = time.monotonic()
            await asyncio.sleep(max(0.0, t0 + (i + 1) * 0.02 - time.monotonic()))
        await asyncio.sleep(listen_s)
        task.cancel()
    if out and got:
        with wave.open(out, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"".join(got))
    return None if t_first is None or t_end is None else (t_first - t_end) * 1000, sum(len(g) for g in got) / 2 / rate


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://localhost:8000/audio")
    ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--tail", type=float, default=1.0, help="seconds of silence after the question")
    ap.add_argument("--listen", type=float, default=10.0)
    ap.add_argument("--save", help="prefix for the reply WAVs")
    ap.add_argument("wav", nargs="+")
    a = ap.parse_args()
    ctx = None
    if a.url.startswith("wss"):
        ctx = ssl.create_default_context()
        if a.insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
    for i, w in enumerate(a.wav):
        ms, secs = await ask(a.url, w, ctx, a.tail, a.listen, f"{a.save}{i}.wav" if a.save else None)
        print(f"{w}: first audible sample {'none' if ms is None else f'{ms:.0f} ms'} after the question ended; {secs:.1f} s of audio received")


if __name__ == "__main__":
    asyncio.run(main())
