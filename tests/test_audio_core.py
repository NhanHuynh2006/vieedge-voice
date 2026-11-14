import numpy as np

from vieedge.audio.ring import SharedRing
from vieedge.audio.vad import Endpointer


def test_ring_wraparound():
    r = SharedRing(1000)
    try:
        for k in range(5):
            r.write(np.arange(300, dtype=np.int16) + k)
            x, idx = r.read()
            assert len(x) == 300 and x[0] == k and idx == 300 * k
    finally:
        r.close()


def test_ring_overflow_drops_oldest():
    r = SharedRing(100)
    try:
        r.write(np.arange(150, dtype=np.int16))
        x, _ = r.read()
        assert len(x) == 100 and x[-1] == 149
    finally:
        r.close()


def _run(ep, probs):
    evs = []
    t = 0.0
    for p in probs:
        t += 0.032
        evs += [e.kind for e in ep.push(np.zeros(512, np.float32), p, t)]
    return evs


def test_endpointer_sequence():
    ep = Endpointer(threshold=0.5, endpoint_ms=320, min_speech_ms=96, pre_roll_ms=96)
    evs = _run(ep, [0.0] * 5 + [0.9] * 20 + [0.1] * 3 + [0.9] * 5 + [0.0] * 15)
    assert evs == ["start", "pause", "resume", "pause", "end"]


def test_endpointer_ignores_blips():
    ep = Endpointer(threshold=0.5, endpoint_ms=320, min_speech_ms=200)
    assert _run(ep, [0.9, 0.0] * 20) == []


def test_ptt_never_ends_on_silence():
    ep = Endpointer(endpoint_ms=100)
    ep.force_start(0.0)
    assert "end" not in _run(ep, [0.0] * 50)
    assert ep.force_end(2.0).kind == "end"
