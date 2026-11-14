"""Push-to-talk button + status LEDs (listening / thinking / speaking) via libgpiod v2.

Wiring (BCM numbering, Pi 5 header): button GPIO17 -> GND (internal pull-up), LEDs GPIO22/23/24
through 330 Ohm to GND. Falls back to a no-op (laptop) and to the keyboard: press Enter = toggle PTT.
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Callable

log = logging.getLogger(__name__)


class StatusIO:
    def __init__(self, cfg: dict, on_press: Callable[[], None], on_release: Callable[[], None]):
        self.cfg = cfg
        self.on_press, self.on_release = on_press, on_release
        self.req = None
        self.leds = {"listening": cfg["led_listen"], "thinking": cfg["led_think"], "speaking": cfg["led_speak"]}
        self._stop = threading.Event()
        if cfg.get("enabled"):
            try:
                self._open()
            except Exception as e:
                log.warning("GPIO unavailable (%s) — keyboard PTT only", e)
                self.req = None

    def _open(self) -> None:
        import gpiod
        from gpiod.line import Bias, Direction, Edge, Value

        chip = self.cfg.get("chip", "auto")
        if chip == "auto":
            import glob

            chip = None
            for p in sorted(glob.glob("/dev/gpiochip*")):
                with gpiod.Chip(p) as c:
                    if "rp1" in c.get_info().label or "pinctrl-rp1" in c.get_info().label:
                        chip = p
                        break
            chip = chip or "/dev/gpiochip0"
        self.gpiod, self.Value = gpiod, Value
        cfg = {
            self.cfg["button"]: gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP, edge_detection=Edge.BOTH,
                                                   debounce_period=__import__("datetime").timedelta(milliseconds=20)),
        }
        for pin in self.leds.values():
            cfg[pin] = gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)
        self.req = gpiod.request_lines(chip, consumer="vieedge", config=cfg)
        log.info("GPIO on %s: button %d, LEDs %s", chip, self.cfg["button"], self.leds)

    def set_state(self, state: str) -> None:
        if self.req is None:
            return
        for name, pin in self.leds.items():
            self.req.set_value(pin, self.Value.ACTIVE if name == state else self.Value.INACTIVE)

    def start(self) -> None:
        if self.req is not None:
            threading.Thread(target=self._gpio_loop, daemon=True, name="gpio").start()
        if sys.stdin and sys.stdin.isatty():
            threading.Thread(target=self._kbd_loop, daemon=True, name="kbd").start()

    def _gpio_loop(self) -> None:
        from gpiod.edge_event import EdgeEvent

        while not self._stop.is_set():
            if self.req.wait_edge_events(0.2):
                for ev in self.req.read_edge_events():
                    if ev.line_offset != self.cfg["button"]:
                        continue
                    if ev.event_type == EdgeEvent.Type.FALLING_EDGE:
                        self.on_press()
                    else:
                        self.on_release()

    def _kbd_loop(self) -> None:
        held = False
        for _ in sys.stdin:
            held = not held
            (self.on_press if held else self.on_release)()
            time.sleep(0.01)

    def close(self) -> None:
        self._stop.set()
        if self.req is not None:
            self.set_state("off")
            self.req.release()
