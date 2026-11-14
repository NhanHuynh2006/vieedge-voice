"""Real-time / CPU placement helpers (Linux). All functions degrade to no-ops when not permitted."""
from __future__ import annotations

import ctypes
import logging
import os

log = logging.getLogger(__name__)

MCL_CURRENT, MCL_FUTURE = 1, 2


def pin_current_thread(cpus: set[int]) -> bool:
    """Pin the calling thread (Linux TID) to `cpus`. Threads started afterwards inherit it."""
    try:
        os.sched_setaffinity(0, cpus)  # pid 0 = calling thread on Linux
        return True
    except (OSError, AttributeError) as e:
        log.debug("sched_setaffinity(%s) failed: %s", cpus, e)
        return False


def set_fifo(priority: int) -> bool:
    """SCHED_FIFO for the calling thread (needs CAP_SYS_NICE / root / rtprio limit)."""
    try:
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(priority))
        return True
    except (OSError, AttributeError, PermissionError) as e:
        log.warning("SCHED_FIFO %d not granted (%s); running SCHED_OTHER", priority, e)
        return False


def mlockall() -> bool:
    """Lock pages so the audio process never page-faults (avoids xruns under memory pressure)."""
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        if libc.mlockall(MCL_CURRENT | MCL_FUTURE) != 0:
            raise OSError(ctypes.get_errno(), "mlockall")
        return True
    except OSError as e:
        log.debug("mlockall failed: %s", e)
        return False


def current_policy() -> str:
    try:
        pol = os.sched_getscheduler(0)
        return {os.SCHED_OTHER: "OTHER", os.SCHED_FIFO: "FIFO", os.SCHED_RR: "RR"}.get(pol, str(pol))
    except (OSError, AttributeError):
        return "?"
