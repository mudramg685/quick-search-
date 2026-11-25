"""Token-bucket rate limiter for the public API (one bucket per client IP).

Each bucket holds up to ``capacity`` tokens and refills continuously at ``rate`` tokens
per second. A request spends one token; with an empty bucket the API answers
``429 Too Many Requests`` plus a ``Retry-After`` header. Bursts up to ``capacity`` are
allowed while the long-run average is capped at ``rate``. O(1) per request (hash map).
"""
from __future__ import annotations

import math
import threading
import time


class TokenBucketLimiter:
    def __init__(self, rate: float, capacity: int, max_clients: int = 10_000):
        self.rate = rate
        self.capacity = capacity
        self.max_clients = max_clients
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, float, int]:
        """Return (allowed, retry_after_seconds, remaining_tokens)."""
        now = time.monotonic()
        with self._lock:
            if len(self._buckets) > self.max_clients:
                self._buckets.clear()  # crude memory bound against IP churn
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return True, 0.0, int(tokens - 1.0)
            self._buckets[key] = (tokens, now)
            return False, (1.0 - tokens) / self.rate, 0

    @staticmethod
    def retry_header(seconds: float) -> str:
        return str(max(1, math.ceil(seconds)))
