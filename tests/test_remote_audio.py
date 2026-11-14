import queue
import time

import numpy as np

from vieedge.audio.rt_engine import RemoteBackend, resolve_backend

CFG = {"period_ms": 20, "periods": 4, "remote_latency_ms": 150}


def make():
    be = RemoteBackend(CFG, 16000, 22050)
    be.open()
    be.out_q = queue.Queue(maxsize=3)
    return be


def test_mic_chunks_come_out_in_20ms_periods():
    be = make()
    x = (np.arange(960) % 200).astype(np.int16)           # 60 ms from the phone, arriving as one burst
    be.control(("mic", x.tobytes()))
    got = np.concatenate([be.read()[0] for _ in range(3)])
    assert np.array_equal(got, x)


def test_late_microphone_reads_as_silence():
    be = make()
    out, overrun = be.read()
    assert not overrun and len(out) == 320 and not out.any()


def test_backlog_is_trimmed_to_the_newest():
    be = make()
    for i in range(10):                                    # 10 x 100 ms burst: the phone clock ran ahead
        be.control(("mic", np.full(1600, i + 1, np.int16).tobytes()))
    kept = sum(len(c) for c in be._chunks)
    assert kept <= 0.25 * 16000 + 1600 and be._chunks[-1][0] == 10


def test_speech_goes_to_the_queue_and_is_dropped_when_nobody_drains():
    be = make()
    t0 = time.monotonic()
    for _ in range(5):
        be.write(np.ones(441, np.int16))                  # 20 ms at 22.05 kHz
    assert be.out_q.qsize() == 3                          # maxsize reached, the rest dropped without blocking
    assert time.monotonic() - t0 >= 0.08                  # but paced like a sound card


def test_auto_backend(tmp_path):
    usb = tmp_path / "cards"
    usb.write_text(" 0 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0\n 1 [Device         ]: USB-Audio - USB Audio Device\n")
    hdmi = tmp_path / "hdmi"
    hdmi.write_text(" 0 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0\n")
    assert resolve_backend({"backend": "auto"}, str(usb)) == "alsa"
    assert resolve_backend({"backend": "auto"}, str(hdmi)) == "remote"
    assert resolve_backend({"backend": "auto"}, str(tmp_path / "missing")) == "remote"
    assert resolve_backend({"backend": "alsa"}, str(hdmi)) == "alsa"
