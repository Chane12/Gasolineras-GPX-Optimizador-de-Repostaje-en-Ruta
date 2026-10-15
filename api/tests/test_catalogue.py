"""Tests for the in-memory MITECO catalogue (fake fetcher and clocks, no network)."""

import threading
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from gasolineras_api.catalogue import CatalogueUnavailableError, PriceCatalogue
from gasolineras_core.ingestion.miteco import MitecoResult

T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def advance(self, **kwargs: float) -> None:
        self.now += timedelta(**kwargs)

    def wall(self) -> datetime:
        return self.now

    def monotonic(self) -> float:
        return (self.now - T0).total_seconds()


class FakeFetch:
    """Each call returns the next item: a MitecoResult, or an exception to raise."""

    def __init__(self, clock: Clock, *outcomes) -> None:
        self.clock = clock
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self) -> MitecoResult:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def stations_df(n: int) -> pd.DataFrame:
    return pd.DataFrame({"Latitud": [40.0 + i * 0.01 for i in range(n)], "Longitud (WGS84)": [-4.0] * n})


def fresh(clock: Clock, stations: int = 3) -> MitecoResult:
    return MitecoResult(df=stations_df(stations), fetched_at=clock.now)


def fallback(fetched_at: datetime) -> MitecoResult:
    return MitecoResult(df=stations_df(1), fetched_at=fetched_at, from_fallback=True)


def make(clock: Clock, fetch: FakeFetch) -> PriceCatalogue:
    return PriceCatalogue(fetch=fetch, ttl_s=30 * 60, retry_after_s=5 * 60, now=clock.wall, monotonic=clock.monotonic)


def test_downloads_once_and_reuses_within_ttl():
    clock = Clock()
    fetch = FakeFetch(clock, fresh(clock))
    catalogue = make(clock, fetch)

    first = catalogue.get()
    clock.advance(minutes=29)
    assert catalogue.get() is first
    assert fetch.calls == 1


def test_after_ttl_serves_current_data_and_refreshes_in_the_background():
    clock = Clock()
    fetch = FakeFetch(clock, fresh(clock, 3), None)
    catalogue = make(clock, fetch)
    catalogue.get()

    clock.advance(minutes=31)
    fetch.outcomes[0] = fresh(clock, 5)

    assert len(catalogue.get().df) == 3  # nobody waits for MITECO
    assert catalogue.wait_for_refresh(5)
    assert len(catalogue.get().df) == 5
    assert fetch.calls == 2


def test_background_refresh_also_prepares_the_spatial_index():
    clock = Clock()
    fetch = FakeFetch(clock, fresh(clock, 3), None)
    catalogue = make(clock, fetch)
    catalogue.get()
    clock.advance(minutes=31)
    fetch.outcomes[0] = fresh(clock, 5)

    catalogue.get()
    catalogue.wait_for_refresh(5)

    assert catalogue._stations is not None and len(catalogue._stations[1]) == 5


def test_keeps_old_data_when_miteco_fails_and_waits_before_retrying():
    clock = Clock()
    fetch = FakeFetch(clock, fresh(clock), ConnectionError("down"), ConnectionError("down"))
    catalogue = make(clock, fetch)
    original = catalogue.get()

    clock.advance(minutes=40)
    assert catalogue.get() is original
    catalogue.wait_for_refresh(5)
    assert catalogue.get() is original  # refresh failed: old data, real age
    clock.advance(minutes=4)
    catalogue.get()
    catalogue.wait_for_refresh(5)
    assert fetch.calls == 2  # within the 5 min backoff: no new attempt

    clock.advance(minutes=2)
    catalogue.get()  # backoff over: tries again
    catalogue.wait_for_refresh(5)
    assert fetch.calls == 3


def test_fallback_copy_is_used_only_if_newer_than_memory():
    clock = Clock()
    fetch = FakeFetch(clock, fresh(clock), fallback(T0 - timedelta(hours=3)))
    catalogue = make(clock, fetch)
    original = catalogue.get()

    clock.advance(minutes=31)
    catalogue.get()
    catalogue.wait_for_refresh(5)
    assert catalogue.get() is original


def test_fallback_copy_is_served_when_there_is_nothing_else():
    clock = Clock()
    old = fallback(T0 - timedelta(hours=30))
    catalogue = make(clock, FakeFetch(clock, old))

    assert catalogue.get() is old


def test_no_data_at_all_raises_and_backs_off():
    clock = Clock()
    fetch = FakeFetch(clock, ConnectionError("down"), ConnectionError("down"))
    catalogue = make(clock, fetch)

    with pytest.raises(CatalogueUnavailableError):
        catalogue.get()
    with pytest.raises(CatalogueUnavailableError):
        catalogue.get()  # within backoff: does not try again
    assert fetch.calls == 1


def test_requests_during_a_refresh_get_current_data_without_waiting():
    clock = Clock()
    release = threading.Event()
    started = threading.Event()
    calls = []

    def slow_fetch() -> MitecoResult:
        calls.append(1)
        if len(calls) == 2:
            started.set()
            release.wait(5)
        return fresh(clock)

    catalogue = make(clock, slow_fetch)  # type: ignore[arg-type]
    original = catalogue.get()
    clock.advance(minutes=31)

    assert catalogue.get() is original  # starts the background refresh and returns at once
    assert started.wait(5)

    assert catalogue.is_refreshing
    assert catalogue.get() is original  # does not block on the running refresh, nor starts another one
    release.set()
    assert catalogue.wait_for_refresh(5)
    assert len(calls) == 2


def test_warm_up_does_not_raise_when_miteco_is_down():
    clock = Clock()
    catalogue = make(clock, FakeFetch(clock, ConnectionError("down")))

    catalogue.warm_up()

    assert catalogue.current is None
