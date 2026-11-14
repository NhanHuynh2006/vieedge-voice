import json
from pathlib import Path

import numpy as np
import pytest

from vieedge.fastpath import FastPath

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def fp():
    return FastPath(str(ROOT / "data" / "fastpath" / "faq.jsonl"))


@pytest.mark.parametrize("q,intent", [("đi thẳng 2 mét", "di thang"), ("dừng lại", "dung lai"), ("nằm xuống", "nam xuong"),
                                        ("chào đi", "chao"), ("xoay phải 90 độ", "xoay_do")])
def test_reflex_commands(fp, q, intent):
    h = fp.lookup(q)
    assert h is not None and h.source == "reflex" and h.intent == intent and h.actions


def test_combo_and_goto(fp):
    assert fp.lookup("qua trái rồi tiến lên 3 mét").source == "combo"
    assert fp.lookup("đi tới góc phòng").source == "goto"


@pytest.mark.parametrize("q", ["tiền Việt Nam là gì", "mưa là hiện tượng gì", "Hà Nội có bao nhiêu quận", "tại sao bầu trời màu xanh",
                               "thủ đô của Nhật Bản ở đâu"])
def test_information_questions_are_not_hijacked(fp, q):
    assert fp.lookup(q) is None


def test_faq_exact_and_fuzzy(fp):
    row = json.loads(next(open(ROOT / "data" / "fastpath" / "faq.jsonl", encoding="utf-8")))
    h = fp.lookup(row["q"])
    assert h is not None and h.say == row["say"]
    assert fp.lookup(row["q"].upper()).say == row["say"]  # normalisation


def test_audio_cache_roundtrip(tmp_path):
    class T:
        name = "t"
        calls = 0

        def synthesize(self, s):
            T.calls += 1
            return type("R", (), {"audio": np.ones(160, np.float32) * 0.5, "sample_rate": 16000})()

    f = FastPath(None)
    a, sr = f.audio("Dạ", T(), tmp_path)
    assert sr == 16000 and len(a) == 160 and T.calls == 1
    g = FastPath(None)  # fresh memory, same disk cache -> no new synthesis
    b, _ = g.audio("Dạ", T(), tmp_path)
    assert T.calls == 1 and np.allclose(a, b, atol=1e-3)


def test_punctuation_is_ignored(fp):
    assert fp.lookup("Tiến về phía trước sáu giây giúp mình.").source == "reflex"
    assert fp.lookup("Xoay trái hai vòng, nhé!").intent == "xoay_vong"


def test_noise_gate():
    import numpy as np

    from vieedge.pipeline import looks_like_noise

    quiet = np.random.default_rng(0).normal(0, 0.003, 16000).astype(np.float32)
    loud = np.random.default_rng(0).normal(0, 0.08, 16000).astype(np.float32)
    assert looks_like_noise(quiet, "", 0.012, 0)
    assert not looks_like_noise(loud, "xin chào các bạn", 0.012, 2)
    assert looks_like_noise(loud, "ừ", 0.012, 2)                    # one word, not a prepared command
    assert not looks_like_noise(loud, "dừng", 0.012, 2, prepared=True)
