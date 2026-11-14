"""System monitor: per-core CPU %, RAM, SoC temperature, throttling flags, NPU stats, xruns."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable


def _read(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


class CpuSampler:
    def __init__(self):
        self.prev = self._stat()

    @staticmethod
    def _stat() -> dict[str, tuple[int, int]]:
        out = {}
        txt = _read("/proc/stat") or ""
        for line in txt.splitlines():
            if line.startswith("cpu"):
                parts = line.split()
                vals = list(map(int, parts[1:]))
                idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                out[parts[0]] = (sum(vals), idle)
        return out

    def sample(self) -> dict[str, float]:
        cur = self._stat()
        res = {}
        for k, (tot, idle) in cur.items():
            p = self.prev.get(k)
            if p and tot > p[0]:
                res[k] = round(100.0 * (1 - (idle - p[1]) / (tot - p[0])), 1)
        self.prev = cur
        return res


def mem_info() -> dict:
    info = {}
    for line in (_read("/proc/meminfo") or "").splitlines():
        k, v = line.split(":", 1)
        info[k] = int(v.split()[0])
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", 0)
    return {"ram_total_mb": total // 1024, "ram_used_mb": (total - avail) // 1024}


def soc_temp() -> float | None:
    v = _read("/sys/class/thermal/thermal_zone0/temp")
    return round(int(v) / 1000, 1) if v else None


def throttled() -> int | None:
    """Raspberry Pi get_throttled bit field (0 = never throttled / under-voltage)."""
    # explicit locations (a recursive glob over /sys loops forever through symlinks)
    cands = glob.glob("/sys/devices/platform/soc/soc:firmware/get_throttled") + \
        glob.glob("/sys/devices/platform/*firmware*/get_throttled") + glob.glob("/sys/devices/platform/axi/*firmware*/get_throttled")
    for p in cands:
        v = _read(p)
        if v:
            return int(v, 16)
    if shutil.which("vcgencmd"):
        try:
            out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2).stdout
            return int(out.strip().split("=")[1], 16)
        except Exception:
            return None
    return None


def cpu_freq_mhz() -> list[int]:
    out = []
    for p in sorted(glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq")):
        v = _read(p)
        if v:
            out.append(int(v) // 1000)
    return out


def governor() -> str | None:
    return _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")


def proc_rss_mb(pid: int) -> float | None:
    v = _read(f"/proc/{pid}/status")
    if not v:
        return None
    for line in v.splitlines():
        if line.startswith("VmRSS:"):
            return round(int(line.split()[1]) / 1024, 1)
    return None


class SysMon:
    """Background sampler; `extra` callbacks add NPU / xrun / power fields."""

    def __init__(self, period_s: float = 1.0, extra: list[Callable[[], dict]] | None = None,
                 on_sample: Callable[[dict], None] | None = None):
        self.period = period_s
        self.extra = extra or []
        self.on_sample = on_sample
        self.cpu = CpuSampler()
        self.last: dict = {}
        self.max_temp = 0.0
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, daemon=True, name="sysmon")

    def start(self) -> None:
        self._th.start()

    def stop(self) -> None:
        self._stop.set()

    def snapshot(self) -> dict:
        c = self.cpu.sample()
        s = {"t": time.time(), "cpu_total": c.get("cpu"),
             "cpu_cores": [c[k] for k in sorted(c) if k != "cpu"],
             "freq_mhz": cpu_freq_mhz(), "temp_c": soc_temp(), "throttled": throttled(),
             "load1": os.getloadavg()[0], **mem_info()}
        if s["temp_c"]:
            self.max_temp = max(self.max_temp, s["temp_c"])
        for fn in self.extra:
            try:
                s.update(fn() or {})
            except Exception:
                pass
        self.last = s
        return s

    def _run(self) -> None:
        while not self._stop.wait(self.period):
            s = self.snapshot()
            if self.on_sample:
                self.on_sample(s)
