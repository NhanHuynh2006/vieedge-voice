import time
import wave

import numpy as np

from vieedge.audio.rt_engine import AudioEngine


def test_file_backend_roundtrip(tmp_path):
    wav = tmp_path / "tone.wav"
    x = (0.3 * np.sin(2 * np.pi * 440 * np.arange(8000) / 16000) * 32767).astype("<i2")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(x.tobytes())
    eng = AudioEngine({"backend": "file", "sample_rate": 16000, "period_ms": 20, "periods": 4, "rt_core": None,
                       "rt_priority": 0, "ring_seconds": 5, "capture_device": None, "playback_device": None}, playback_rate=22050)
    try:
        assert eng.start()["ready"]
        eng.inject(str(wav))
        got = []
        t0 = time.monotonic()
        while time.monotonic() - t0 < 2.0:
            s, _ = eng.read()
            got.append(s)
            time.sleep(0.02)
        cap = np.concatenate(got)
        assert np.abs(cap).max() > 5000  # the tone arrived through the "microphone"
        eng.arm_first_audio()
        eng.play(np.full(2205, 1000, dtype=np.int16))
        t0 = time.monotonic()
        while eng.first_audio_time() is None and time.monotonic() - t0 < 2:
            time.sleep(0.01)
        assert eng.first_audio_time() is not None
        assert eng.xruns()["playback"] == 0
    finally:
        eng.stop()
