#!/usr/bin/env python3
"""Count ALSA xruns of the real-time audio process for a fixed time, optionally while a load runs
(used by os_bench.sh for O0-O4). Uses the same AudioEngine as the assistant: full-duplex capture
+ continuous playback (a short beep every 2 s so the speaker path is really exercised).

  xrun_test.py -c /etc/vieedge/config.yaml --minutes 30
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np

from common import results_dir
from vieedge.audio.rt_engine import AudioEngine
from vieedge.config import load_config


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config")
    ap.add_argument("--minutes", type=float, default=10)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    cfg = load_config(a.config)
    eng = AudioEngine(cfg["audio"], playback_rate=22050)
    info = eng.start()
    beep = (0.2 * np.sin(2 * np.pi * 880 * np.arange(int(0.1 * eng.pb_rate)) / eng.pb_rate) * 32767).astype(np.int16)
    t0 = time.monotonic()
    x0 = eng.xruns()
    n_read = 0
    while time.monotonic() - t0 < a.minutes * 60:
        x, _ = eng.read()
        n_read += len(x)
        if int(time.monotonic() - t0) % 2 == 0 and eng.playback_pending_s() < 0.05:
            eng.play(beep)
        time.sleep(0.02)
    x1 = eng.xruns()
    eng.stop()
    hours = (time.monotonic() - t0) / 3600
    res = {"os_cfg": cfg["os_cfg"], "tag": a.tag, "minutes": a.minutes, "audio": info,
           "capture_xruns": x1["capture"] - x0["capture"], "playback_xruns": x1["playback"] - x0["playback"],
           "ring_overruns": x1["ring_overruns"] - x0["ring_overruns"], "captured_s": n_read / eng.cap_rate}
    res["xruns_per_h"] = (res["capture_xruns"] + res["playback_xruns"]) / hours
    print(json.dumps(res))
    (results_dir() / "os").mkdir(exist_ok=True)
    with open(results_dir() / "os" / "xruns.jsonl", "a") as f:
        f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
