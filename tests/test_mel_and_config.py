import numpy as np
import pytest

from vieedge.config import load_config, parse_cpuset
from vieedge.stt.mel import window_mel


def test_mel_shape():
    assert window_mel(np.zeros(16000, np.float32), 10).shape == (80, 1000)
    assert window_mel(np.zeros(16000, np.float32), 5).shape == (80, 500)


def test_mel_matches_hf_feature_extractor():
    tr = pytest.importorskip("transformers")
    fe = tr.WhisperFeatureExtractor(feature_size=80)
    rng = np.random.default_rng(0)
    x = (rng.standard_normal(16000 * 3) * 0.1).astype(np.float32)
    ref = fe(x, sampling_rate=16000, return_tensors="np").input_features[0]  # 30 s padded
    ours = window_mel(x, 30)
    assert ours.shape == ref.shape
    assert np.abs(ours - ref).max() < 2e-3


def test_cpuset():
    assert parse_cpuset("0-1") <= {0, 1}
    assert parse_cpuset("") == set(range(__import__("os").cpu_count()))


def test_rt_policy_by_os_level():
    c = load_config("deploy/config/vieedge-pi.yaml", {"os_cfg": "O2"})
    assert c["audio"]["rt_core"] is None and c["audio"]["rt_priority"] == 0
    c = load_config("deploy/config/vieedge-pi.yaml", {"os_cfg": "O4"})
    assert c["audio"]["rt_core"] == 3 and c["audio"]["rt_priority"] == 80
