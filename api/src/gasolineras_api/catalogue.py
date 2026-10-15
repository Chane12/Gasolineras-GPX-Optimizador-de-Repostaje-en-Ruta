"""In-memory MITECO price catalogue shared by every request (ADR 0005).

- Downloaded at most once per ``ttl_s`` (30 min) for all users; refreshed on demand, one thread at a time.
- While a refresh is running, other requests keep getting the current data instead of waiting.
- If MITECO is down, the last data is kept (with its real age) and retries are spaced by ``retry_after_s``.
- Never uses third-party proxies.
"""

import logging
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

import geopandas as gpd

from gasolineras_core.config import PRICES_FRESH_MAX_AGE_S
from gasolineras_core.ingestion.miteco import MitecoResult, fetch_gasolineras
from gasolineras_core.spatial.engine import build_stations_geodataframe

logger = logging.getLogger(__name__)

RETRY_AFTER_FAILURE_S = 5 * 60


def fetch_without_proxies() -> MitecoResult:
    return fetch_gasolineras(use_proxies=False)


class CatalogueUnavailableError(RuntimeError):
    """There are no prices at all: MITECO is unreachable and there is no local copy."""


class PriceCatalogue:
    def __init__(
        self,
        fetch: Callable[[], MitecoResult] = fetch_without_proxies,
        ttl_s: float = PRICES_FRESH_MAX_AGE_S,
        retry_after_s: float = RETRY_AFTER_FAILURE_S,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._ttl_s = ttl_s
        self._retry_after_s = retry_after_s
        self._now = now
        self._monotonic = monotonic
        self._result: MitecoResult | None = None
        self._last_failure: float | None = None
        self._refresh_lock = threading.Lock()
        self._stations: tuple[MitecoResult, gpd.GeoDataFrame] | None = None
        self._stations_lock = threading.Lock()

    @property
    def current(self) -> MitecoResult | None:
        """Data in memory right now, without triggering a download (for /health)."""
        return self._result

    @property
    def is_refreshing(self) -> bool:
        return self._refresh_lock.locked()

    def get(self) -> MitecoResult:
        """Current prices, refreshing them first if they are older than the TTL.

        Raises CatalogueUnavailableError if there are no prices at all.
        """
        result = self._result
        if result is not None and not self._needs_refresh(result):
            return result

        if result is not None:
            # Someone else is already refreshing: don't make this user wait.
            if not self._refresh_lock.acquire(blocking=False):
                return result
        else:
            self._refresh_lock.acquire()  # nothing to serve yet: wait for the first download

        try:
            result = self._result
            if (result is None and not self._in_backoff()) or (result is not None and self._needs_refresh(result)):
                self._refresh()
        finally:
            self._refresh_lock.release()

        if self._result is None:
            raise CatalogueUnavailableError("Los precios del MITECO no están disponibles ahora mismo.")
        return self._result

    def get_stations(self) -> tuple[MitecoResult, gpd.GeoDataFrame]:
        """Current prices plus their spatial index (EPSG:25830), built once per catalogue version."""
        result = self.get()
        with self._stations_lock:
            if self._stations is None or self._stations[0] is not result:
                self._stations = (result, build_stations_geodataframe(result.df))
            return self._stations

    def warm_up(self) -> None:
        """First download at startup (run it in a background thread so the API starts at once)."""
        try:
            self.get_stations()
        except CatalogueUnavailableError:
            logger.error("MITECO catalogue unavailable at startup")

    def _needs_refresh(self, result: MitecoResult) -> bool:
        age_s = (self._now() - result.fetched_at).total_seconds()
        return age_s >= self._ttl_s and not self._in_backoff()

    def _in_backoff(self) -> bool:
        return self._last_failure is not None and self._monotonic() - self._last_failure < self._retry_after_s

    def _refresh(self) -> None:
        try:
            new = self._fetch()
        except Exception as exc:  # ConnectionError/ValueError from MITECO, or anything unexpected
            logger.error("MITECO refresh failed: %s", exc)
            self._last_failure = self._monotonic()
            return

        if new.from_fallback:
            # MITECO is down; the local copy only helps if it is newer than what we hold.
            self._last_failure = self._monotonic()
            logger.warning("MITECO down; fallback copy from %s", new.fetched_at.isoformat())
        else:
            self._last_failure = None
        if self._result is None or new.fetched_at > self._result.fetched_at:
            self._result = new
            logger.info("MITECO catalogue updated: %d stations (fallback=%s)", len(new.df), new.from_fallback)
