"""Tests for OSRM detours (no network: requests.get is faked, sleeps are skipped)."""

import threading
from typing import Any

import pytest
import requests
from shapely.geometry import LineString

from gasolineras_core.config import OSRM_MAX_CONCURRENCY, USER_AGENT
from gasolineras_core.optimizer import export

TRACK = LineString([(-4.70, 40.60), (-4.50, 40.70), (-4.30, 40.80)])


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._payload


def osrm_leg(distance_m: float, duration_s: float) -> FakeResponse:
    return FakeResponse({"code": "Ok", "routes": [{"legs": [{"distance": distance_m, "duration": duration_s}]}]})


@pytest.fixture(autouse=True)
def fast_and_isolated(monkeypatch):
    monkeypatch.setattr(export.time, "sleep", lambda _s: None)
    export._leg_cache.clear()
    yield
    export._leg_cache.clear()


def test_detour_is_way_there_plus_way_back(monkeypatch):
    calls: list[dict] = []

    def fake_get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        return osrm_leg(1500, 120)

    monkeypatch.setattr(export.requests, "get", fake_get)

    [detour] = export.compute_detours(TRACK, [(-4.51, 40.71)])

    assert detour == {"distance_km": pytest.approx(3.0), "duration_min": pytest.approx(4.0)}
    assert len(calls) == 2
    assert calls[0]["headers"]["User-Agent"] == USER_AGENT
    assert calls[0]["timeout"] is not None


def test_results_keep_the_input_order_and_failures_are_none(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        if "-4.4" in url:  # the second station is unreachable
            return FakeResponse({"code": "NoRoute"}, status_code=400)
        return osrm_leg(1000, 60)

    monkeypatch.setattr(export.requests, "get", fake_get)

    detours = export.compute_detours(TRACK, [(-4.6, 40.65), (-4.4, 40.75), (-4.35, 40.78)])

    assert detours[0] is not None
    assert detours[1] is None
    assert detours[2] is not None


def test_legs_are_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(export.requests, "get", lambda url, **_k: calls.append(url) or osrm_leg(1000, 60))

    export.compute_detours(TRACK, [(-4.51, 40.71)])
    export.compute_detours(TRACK, [(-4.51, 40.71)])

    assert len(calls) == 2  # second call fully served from cache


def test_cached_detours_skip_the_courtesy_pauses(monkeypatch):
    monkeypatch.setattr(export.requests, "get", lambda url, **_k: osrm_leg(1000, 60))
    export.compute_detours(TRACK, [(-4.51, 40.71)])

    sleeps: list[float] = []
    monkeypatch.setattr(export.time, "sleep", sleeps.append)
    export.compute_detours(TRACK, [(-4.51, 40.71)])

    assert sleeps == []


def test_concurrent_requests_to_osrm_are_bounded(monkeypatch):
    in_flight = 0
    peak = 0
    lock = threading.Lock()

    def fake_get(url, headers=None, timeout=None):
        nonlocal in_flight, peak
        with lock:
            in_flight += 1
            peak = max(peak, in_flight)
        threading.Event().wait(0.01)
        with lock:
            in_flight -= 1
        return osrm_leg(1000, 60)

    monkeypatch.setattr(export.requests, "get", fake_get)
    stations = [(-4.6 + i * 0.01, 40.65) for i in range(8)]

    threads = [threading.Thread(target=export.compute_detours, args=(TRACK, stations)) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert peak <= OSRM_MAX_CONCURRENCY


def test_no_stations_means_no_requests(monkeypatch):
    monkeypatch.setattr(export.requests, "get", lambda *a, **k: pytest.fail("no request expected"))
    assert export.compute_detours(TRACK, []) == []
