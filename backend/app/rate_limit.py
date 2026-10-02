"""Tiny dependency-free sliding-window rate limiter (plan section 23).

Keyed by client IP. For the local single-user MVP this throttles automated
hammering of the oracle without needing Redis or external services. State lives
in-process and resets on restart, which is fine for local-first use.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def _parse_rate(spec: str) -> tuple[int, float]:
    """Parse a '120/minute' style spec into (count, seconds)."""
    count_str, _, unit = spec.partition("/")
    count = int(count_str.strip())
    unit = unit.strip().lower()
    seconds = {
        "second": 1.0,
        "sec": 1.0,
        "minute": 60.0,
        "min": 60.0,
        "hour": 3600.0,
    }.get(unit, 60.0)
    return count, seconds


def build_limiter(spec: str) -> SlidingWindowRateLimiter:
    count, seconds = _parse_rate(spec)
    return SlidingWindowRateLimiter(count, seconds)
