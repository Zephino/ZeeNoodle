"""Trim process memory and report RSS for small hosts."""

from __future__ import annotations

import ctypes
import gc
from pathlib import Path

_libc: ctypes.CDLL | None | bool = None


def current_rss_mb() -> float | None:
    """Return this process RSS in MB, or None if /proc is unavailable."""
    path = Path("/proc/self/status")
    if not path.is_file():
        return None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                return float(parts[1]) / 1024.0
    except OSError:
        return None
    return None


def _load_libc() -> ctypes.CDLL | None:
    global _libc
    if _libc is False:
        return None
    if _libc is not None:
        return _libc
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim.argtypes = [ctypes.c_size_t]
        libc.malloc_trim.restype = ctypes.c_int
        _libc = libc
        return libc
    except (OSError, AttributeError):
        _libc = False
        return None


def trim_memory() -> None:
    """Collect garbage, then ask glibc to return free heap pages if possible."""
    gc.collect()
    libc = _load_libc()
    if libc is None:
        return
    try:
        libc.malloc_trim(0)
    except Exception:  # noqa: BLE001
        pass
