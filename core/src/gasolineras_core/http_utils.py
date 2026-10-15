"""
gasolineras_core.http_utils
===========================
Process-wide helpers for polite use of external services (ADR 0005): a rate limiter and a TTL cache.

Both are thread-safe: Streamlit and FastAPI serve concurrent users from threads of the same process,
so a single instance per external service is shared by all of them.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

V = TypeVar("V")


class RateLimitBusyError(RuntimeError):
    """Raised when waiting for a rate-limit slot would take longer than allowed."""


class RateLimiter:
    """Guarantees at least ``min_interval_s`` between consecutive calls to :meth:`wait`.

    Callers reserve the next free slot under a lock and then sleep outside it, so concurrent
    callers are spaced out in arrival order. If the reserved slot is more than ``max_wait_s``
    away, :class:`RateLimitBusyError` is raised instead of queueing indefinitely.
    """

    def __init__(
        self,
        min_interval_s: float,
        max_wait_s: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval_s = min_interval_s
        self.max_wait_s = max_wait_s
        self._clock = clock
        self._sleep = sleep
        self._next_free = float("-inf")
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self._clock()
            slot = max(now, self._next_free)
            delay = slot - now
            if delay > self.max_wait_s:
                raise RateLimitBusyError(f"rate limit queue too long ({delay:.1f} s)")
            self._next_free = slot + self.min_interval_s
        if delay > 0:
            self._sleep(delay)


class TTLCache(Generic[V]):
    """Small LRU cache whose entries expire ``ttl_s`` seconds after being stored."""

    def __init__(self, max_items: int, ttl_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.max_items = max_items
        self.ttl_s = ttl_s
        self._clock = clock
        self._data: OrderedDict[Hashable, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> V | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if self._clock() >= expires_at:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: Hashable, value: V) -> None:
        with self._lock:
            self._data[key] = (self._clock() + self.ttl_s, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)
