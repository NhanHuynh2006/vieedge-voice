"""Realtime dashboard (FastAPI + WebSocket), served from the device itself — no internet needed.

  /            live view: transcript while speaking, answer, latency waterfall per turn, CPU per core,
               NPU, RAM, temperature, power, xruns, history; hold-to-talk button for the phone
  /compare     side-by-side view of two devices (e.g. Pi OS vs Yocto-RT), ?a=<ip:port>&b=<ip:port>
  /ws          event stream (JSON) + commands {"cmd": "ptt", "down": bool} | {"cmd": "set_stt", "backend": "ct2"|"hybrid"} | {"cmd": "ask", "text": str}
  /api/status  last system sample, config summary, last turns
  /phone       the phone as microphone + speaker (https only: browsers refuse the microphone on plain http)
  /audio       binary WebSocket for /phone: phone -> Pi int16 mono at `audio.sample_rate`; Pi -> phone int16 at the playback rate
"""
from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger(__name__)
STATIC = Path(__file__).parent / "static"


def create_app(assistant) -> FastAPI:
    app = FastAPI(title="VieEdge-Voice")
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    bus = assistant.bus

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/compare")
    def compare():
        return FileResponse(STATIC / "compare.html")

    @app.get("/favicon.ico")
    def favicon():
        return FileResponse(STATIC / "icon-192.png")

    @app.get("/phone")
    def phone():
        return FileResponse(STATIC / "phone.html")

    audio_clients: set = set()
    loop_ref: dict[str, Any] = {}
    active: dict[str, Any] = {}   # the newest phone: only its microphone frames are used (two senders would interleave into garbage)

    def _drain_speech() -> None:
        """Speech produced by the remote audio backend -> every connected phone (dropped when none is connected)."""
        q = assistant.engine.audio_out
        while True:
            try:
                data = q.get(timeout=1.0)
            except queue.Empty:
                continue
            except (OSError, ValueError):
                return
            loop = loop_ref.get("loop")
            if loop is None or not audio_clients:
                continue
            for c in list(audio_clients):
                loop.call_soon_threadsafe(_offer, c, data)

    def _offer(c: asyncio.Queue, data: bytes) -> None:
        if c.qsize() > 100:  # a stalled phone must not grow memory
            return
        c.put_nowait(data)

    if assistant.engine.remote:
        threading.Thread(target=_drain_speech, daemon=True, name="phone-audio-out").start()

    @app.websocket("/audio")
    async def audio_ws(sock: WebSocket):
        await sock.accept()
        if not assistant.engine.remote:
            await sock.send_text(json.dumps({"type": "error", "message": "audio.backend is not 'remote' (a USB sound card is in use)"}))
            await sock.close()
            return
        loop_ref["loop"] = asyncio.get_running_loop()
        for old in list(audio_clients):  # one phone at a time: the newest connection wins
            old.put_nowait(None)
        mine: asyncio.Queue = asyncio.Queue()
        audio_clients.add(mine)
        active["q"] = mine
        await sock.send_text(json.dumps({"type": "hello", "rate": assistant.engine.pb_rate, "mic_rate": assistant.engine.cap_rate}))

        async def sender():
            while True:
                data = await mine.get()
                if data is None:
                    await sock.close()
                    return
                await sock.send_bytes(data)

        task = asyncio.create_task(sender())
        try:
            while True:
                msg = await sock.receive()
                if msg.get("type") == "websocket.disconnect":
                    break
                if msg.get("bytes") and active.get("q") is mine:
                    assistant.engine.remote_in(msg["bytes"])
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            task.cancel()
            audio_clients.discard(mine)

    @app.get("/api/status")
    def status():
        cfg = assistant.cfg
        return JSONResponse({
            "state": assistant.state, "stt": assistant.stt_name, "stt_available": list(assistant.stt_backends), "rag": assistant.rag_on and assistant.kb is not None,
            "os_cfg": cfg["os_cfg"], "llm": cfg["llm"]["model"], "tts": assistant.tts.name,
            "sys": assistant.sysmon.last, "history": list(bus.history)[-30:], "audio": assistant.audio_info,
        })

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        q = bus.subscribe()
        await sock.send_text(json.dumps({"type": "hello", "state": assistant.state, "stt": assistant.stt_name,
                                         "stt_available": list(assistant.stt_backends), "rag": assistant.rag_on and assistant.kb is not None,
                                         "os_cfg": assistant.cfg["os_cfg"],
                                         "history": list(bus.history)[-30:]}, ensure_ascii=False))

        async def pump():
            while True:
                try:
                    ev = await asyncio.to_thread(q.get, True, 1.0)
                except queue.Empty:
                    continue
                await sock.send_text(json.dumps(ev, ensure_ascii=False, default=str))

        task = asyncio.create_task(pump())
        try:
            while True:
                msg = json.loads(await sock.receive_text())
                cmd = msg.get("cmd")
                if cmd == "ptt":
                    (assistant.ptt_press if msg.get("down") else assistant.ptt_release)()
                elif cmd == "set_stt":
                    assistant.set_stt_backend(msg.get("backend", ""))
                elif cmd == "set_rag":
                    assistant.set_rag(bool(msg.get("on")))
                elif cmd == "barge_in":
                    assistant.barge_in()
                elif cmd == "ask":
                    assistant.ask_text(str(msg.get("text", ""))[:300])
                elif cmd == "stress":
                    _stress(bool(msg.get("on")), assistant)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            task.cancel()
            bus.unsubscribe(q)

    return app


_STRESS: dict = {}


def _stress(on: bool, assistant) -> None:
    """Stage demo: heavy background load on the 'thinking' cores (0-2) to show that audio stays clean
    on the RT image (Pi OS vs Yocto-RT side by side)."""
    import shutil
    import subprocess

    p = _STRESS.get("proc")
    if p is not None and p.poll() is None:
        p.terminate()
        _STRESS.pop("proc", None)
    if on and shutil.which("stress-ng"):
        cmd = ["stress-ng", "--cpu", "3", "--vm", "1", "--vm-bytes", "256M", "--timeout", "180s"]
        if shutil.which("taskset"):
            cmd = ["taskset", "-c", str(assistant.cfg["cpu"]["main_cores"] or "0-2")] + cmd
        _STRESS["proc"] = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assistant.bus.publish("stress", on=bool(on and "proc" in _STRESS))


def start_web(assistant, host: str = "0.0.0.0", port: int = 8000, https_port: int | None = None,
              cert: str | None = None, key: str | None = None) -> threading.Thread:
    """http on `port` for the dashboard; the same app on `https_port` (self-signed) so a phone browser may open the microphone."""
    import uvicorn

    app = create_app(assistant)
    th = threading.Thread(target=uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning", ws="auto")).run,
                          daemon=True, name="web")
    th.start()
    log.info("dashboard on http://%s:%d", host, port)
    if https_port and cert and key and Path(cert).exists() and Path(key).exists():
        cfg = uvicorn.Config(app, host=host, port=https_port, log_level="warning", ws="auto", ssl_certfile=cert, ssl_keyfile=key)
        threading.Thread(target=uvicorn.Server(cfg).run, daemon=True, name="web-https").start()
        log.info("phone page on https://%s:%d/phone (self-signed certificate: accept the browser warning once)", host, https_port)
    elif https_port:
        log.warning("no TLS certificate at %s: the phone page needs https for the microphone", cert)
    return th
