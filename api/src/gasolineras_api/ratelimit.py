"""Per-client rate limiting, in memory (one API instance; ADR 0005).

Three budgets per client IP:
- ``external``: endpoints that call the free OSM services (Nominatim, OSRM). One user must not use up
  the share of everybody else.
- ``suggest``: place suggestions while typing (Photon). Many small requests per search, so its own budget.
- ``default``: everything else except /health.

Client IP behind proxies: set ``GASOLINERAS_TRUSTED_PROXY_HOPS`` to the number of proxies in front of
the API (Render: 3 — Cloudflare, Render edge and internal load balancer, checked 2026-10-16; Cloud Run: 1). The client is then the N-th address from the right of ``X-Forwarded-For``;
addresses further left can be forged by the client and are ignored. With 0 (default), the socket
peer address is used.
"""

import math
import os
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import HTTPException, Request, status

from gasolineras_api.schemas import ErrorResponse

TRUSTED_PROXY_HOPS_ENV = "GASOLINERAS_TRUSTED_PROXY_HOPS"
MAX_TRACKED_CLIENTS = 10_000


@dataclass(frozen=True)
class Budget:
    requests: int
    window_s: float


DEFAULT_BUDGETS: dict[str, Budget] = {
    "external": Budget(requests=10, window_s=60),
    "suggest": Budget(requests=60, window_s=60),
    "default": Budget(requests=60, window_s=60),
}


class RateLimiter:
    """Sliding window: at most ``requests`` per ``window_s`` for each (client, budget)."""

    def __init__(self, budgets: dict[str, Budget] | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.budgets = budgets or DEFAULT_BUDGETS
        self._clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, client: str, budget_name: str) -> float | None:
        """Records a request. Returns None if allowed, or the seconds to wait if over budget."""
        budget = self.budgets[budget_name]
        now = self._clock()
        key = (client, budget_name)
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                if len(self._hits) >= MAX_TRACKED_CLIENTS:
                    self._drop_idle(now)
                hits = self._hits[key] = deque()
            while hits and now - hits[0] >= budget.window_s:
                hits.popleft()
            if len(hits) >= budget.requests:
                return budget.window_s - (now - hits[0])
            hits.append(now)
            return None

    def _drop_idle(self, now: float) -> None:
        longest = max(b.window_s for b in self.budgets.values())
        idle = [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= longest]
        for k in idle:
            del self._hits[k]
        if len(self._hits) >= MAX_TRACKED_CLIENTS:  # still full: forget the oldest half
            for k in list(self._hits)[: MAX_TRACKED_CLIENTS // 2]:
                del self._hits[k]


def client_ip(request: Request, trusted_hops: int | None = None) -> str:
    hops = trusted_hops if trusted_hops is not None else int(os.environ.get(TRUSTED_PROXY_HOPS_ENV, "0") or 0)
    if hops > 0:
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if forwarded:
            return forwarded[-hops] if len(forwarded) >= hops else forwarded[0]
    return request.client.host if request.client else "unknown"


RATE_LIMIT_RESPONSE: dict[int | str, dict] = {
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": ErrorResponse, "description": "Demasiadas peticiones"}
}


def rate_limited(budget_name: str) -> Callable[[Request], None]:
    """FastAPI dependency: ``dependencies=[Depends(rate_limited("external"))]``."""

    def dependency(request: Request) -> None:
        limiter: RateLimiter = request.app.state.rate_limiter
        wait_s = limiter.check(client_ip(request), budget_name)
        if wait_s is not None:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Has hecho demasiadas peticiones seguidas. Espera un momento y vuelve a intentarlo.",
                headers={"Retry-After": str(max(1, math.ceil(wait_s)))},
            )

    return dependency
