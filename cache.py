"""Simple in-memory TTL cache for rate data."""

from __future__ import annotations

import threading
import time
from typing import Any

_store: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()
_TTL = 60  # seconds


def get(key: str) -> Any | None:
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.monotonic() - ts > _TTL:
            _store.pop(key, None)
            return None
        return value


def put(key: str, value: Any) -> None:
    with _lock:
        _store[key] = (time.monotonic(), value)


def invalidate() -> None:
    with _lock:
        _store.clear()
