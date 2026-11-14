"""Power measurement (PLAN §9: external meter + PMIC estimate).

* PMIC (Pi 5): `vcgencmd pmic_read_adc` reports per-rail voltage and current; sum(V*I) estimates
  SoC/board power (not USB peripherals or the Hailo HAT -> the external meter is the reference).
* INA226 on I2C (optional, in series with the 5 V supply): bus voltage * current, read via /dev/i2c-N.
* External USB-C logger CSV: `load_meter_csv` + `energy_per_turn` align it with the turn log offline.
"""
from __future__ import annotations

import csv
import fcntl
import os
import re
import shutil
import subprocess

I2C_SLAVE = 0x0703


def pmic_power_w() -> float | None:
    if not shutil.which("vcgencmd"):
        return None
    try:
        out = subprocess.run(["vcgencmd", "pmic_read_adc"], capture_output=True, text=True, timeout=2).stdout
    except Exception:
        return None
    amps, volts = {}, {}
    for line in out.splitlines():
        m = re.match(r"\s*(\S+)_([AV])\s+\w+\(\d+\)=([\d.]+)", line)
        if m:
            (amps if m.group(2) == "A" else volts)[m.group(1)] = float(m.group(3))
    p = sum(amps[k] * volts[k] for k in amps if k in volts)
    return round(p, 3) if p else None


class INA226:
    REG_BUS, REG_CURRENT, REG_CAL, REG_CONFIG = 0x02, 0x04, 0x05, 0x00

    def __init__(self, bus: int = 1, addr: int = 0x40, shunt_ohm: float = 0.01, max_a: float = 8.0):
        self.fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, addr)
        self.current_lsb = max_a / 32768
        cal = int(0.00512 / (self.current_lsb * shunt_ohm))
        self._w(self.REG_CONFIG, 0x4527)  # 16 avg, 1.1 ms conv, continuous shunt+bus
        self._w(self.REG_CAL, cal)

    def _w(self, reg: int, val: int) -> None:
        os.write(self.fd, bytes([reg, (val >> 8) & 0xFF, val & 0xFF]))

    def _r(self, reg: int) -> int:
        os.write(self.fd, bytes([reg]))
        b = os.read(self.fd, 2)
        return (b[0] << 8) | b[1]

    def read(self) -> tuple[float, float, float]:
        v = self._r(self.REG_BUS) * 1.25e-3
        raw = self._r(self.REG_CURRENT)
        if raw > 32767:
            raw -= 65536
        i = raw * self.current_lsb
        return v, i, v * i


class PowerMeter:
    def __init__(self, mode: str = "auto", bus: int = 1, addr: int = 0x40, shunt: float = 0.01):
        self.ina = None
        self.mode = mode
        if mode in ("auto", "ina226"):
            try:
                self.ina = INA226(bus, addr, shunt)
                self.mode = "ina226"
            except OSError:
                self.mode = "pmic" if mode == "auto" else "none"

    def read(self) -> dict:
        if self.ina is not None:
            v, i, p = self.ina.read()
            return {"power_w": round(p, 3), "power_src": "ina226", "bus_v": round(v, 3)}
        p = pmic_power_w() if self.mode in ("auto", "pmic") else None
        return {"power_w": p, "power_src": "pmic" if p is not None else "none"}


def load_meter_csv(path: str, t_col: str = "time", p_col: str = "power") -> list[tuple[float, float]]:
    """Load (unix_time_s, watts) rows from a USB-C logger export."""
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append((float(r[t_col]), float(r[p_col])))
    return rows


def energy_j(samples: list[tuple[float, float]], t0: float, t1: float) -> float:
    """Trapezoidal integral of power over [t0, t1] (unix seconds)."""
    pts = [(t, p) for t, p in samples if t0 <= t <= t1]
    return sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(pts, pts[1:]))
