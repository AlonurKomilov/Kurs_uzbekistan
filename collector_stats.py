"""In-memory collector metrics tracker."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class CollectorRun:
    slug: str
    rates_count: int
    duration_ms: float
    success: bool
    error: str = ""
    timestamp: float = field(default_factory=time.time)


# Last run per collector slug
_last_runs: dict[str, CollectorRun] = {}
_lock = threading.Lock()
# Boot timestamp
_started_at: float = time.time()


def record(slug: str, rates_count: int, duration_ms: float, success: bool, error: str = "") -> None:
    with _lock:
        _last_runs[slug] = CollectorRun(
            slug=slug,
            rates_count=rates_count,
            duration_ms=duration_ms,
            success=success,
            error=error,
        )


def get_all() -> dict[str, CollectorRun]:
    with _lock:
        return dict(_last_runs)


def uptime_seconds() -> float:
    return time.time() - _started_at
