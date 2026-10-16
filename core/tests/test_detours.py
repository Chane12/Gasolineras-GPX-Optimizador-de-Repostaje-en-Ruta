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


def osrm_route(*legs_m: float) -> FakeResponse:
    """OSRM answer with one leg per pair of consecutive points (distance in m; 1 m = 0.1 s)."""
    return FakeResponse({"code": "Ok", "routes": [{"legs": [{"distance": d, "duration": d / 10} for d in legs_m]}]})


def points_in(url: str) -> list[tuple[float, float]]:
    path = url.split("/driving/")[1].split("?")[0]
    return [tuple(float(c) for c in p.split(",")) for p in path.split(";")]  # type: ignore[misc]


def test_detour_is_the_extra_distance_of_stopping_on_the_way(monkeypatch):
    calls: list[dict] = []

    def fake_get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers, "timeout": timeout})
        # Through the station: 2 + 2.5 km; straight on: 4 km. Detour: 0.5 km.
        return osrm_route(2000, 2500) if len(points_in(url)) == 3 else osrm_route(4000)

    monkeypatch.setattr(export.requests, "get", fake_get)

    [detour] = export.compute_detours(TRACK, [(-4.51, 40.71)])

    assert detour == {"distance_km": pytest.approx(0.5), "duration_min": pytest.approx(500 / 10 / 60)}
    assert len(calls) == 2
    assert calls[0]["headers"]["User-Agent"] == USER_AGENT
    assert calls[0]["timeout"] is not None


def test_detour_is_measured_in_the_direction_of_travel(monkeypatch):
    urls: list[str] = []
    monkeypatch.setattr(export.requests, "get", lambda url, **_k: urls.append(url) or osrm_route(1000, 1000))

    export.compute_detours(TRACK, [(-4.51, 40.71)])

    before, station, after = points_in(next(u for u in urls if len(points_in(u)) == 3))
    assert station == pytest.approx((-4.51, 40.71))
    # The track goes west → east: "before" is west of the station and "after" east of it, ~2 km away.
    assert before[0] < station[0] < after[0]


def test_anchors_stay_on_the_track_near_its_ends():
    import geopandas as gpd
    from shapely.geometry import Point

    stations = gpd.GeoSeries([Point(-4.70, 40.60), Point(-4.50, 40.70)], crs="EPSG:4326")

    [(start_before, start_after), (mid_before, mid_after)] = export.detour_anchors(TRACK, stations, anchor_m=2000)

    assert start_before == pytest.approx((-4.70, 40.60), abs=1e-6)  # nothing before the start
    assert start_after[0] > -4.70
    # On the track (within ~10 m: anchors are computed in UTM and the track segments are straight in degrees).
    assert TRACK.distance(Point(mid_before)) < 1e-4 and TRACK.distance(Point(mid_after)) < 1e-4


def test_detour_is_never_negative(monkeypatch):
    # OSRM may find a slightly shorter way through the station (e.g. a service road): that is 0, not < 0.
    monkeypatch.setattr(
        export.requests, "get", lambda url, **_k: osrm_route(900, 900) if len(points_in(url)) == 3 else osrm_route(2000)
    )

    [detour] = export.compute_detours(TRACK, [(-4.51, 40.71)])

    assert detour == {"distance_km": 0.0, "duration_min": 0.0}


def test_results_keep_the_input_order_and_failures_are_none(monkeypatch):
    def fake_get(url, headers=None, timeout=None):
        if "-4.400000,40.750000" in url:  # the second station is unreachable
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


def test_detours_out_of_time_return_none_without_asking_osrm(monkeypatch):
    monkeypatch.setattr(export.requests, "get", lambda *a, **k: pytest.fail("no request expected"))

    assert export.compute_detours(TRACK, [(-4.51, 40.71), (-4.4, 40.75)], max_seconds=0) == [None, None]


def test_busy_osrm_slot_gives_up_instead_of_waiting_forever(monkeypatch):
    monkeypatch.setattr(export, "OSRM_SEMAPHORE_WAIT_S", 0.01)
    monkeypatch.setattr(export.requests, "get", lambda *a, **k: pytest.fail("no request expected"))
    for _ in range(OSRM_MAX_CONCURRENCY):
        export.OSRM_SEMAPHORE.acquire()
    try:
        assert export.get_real_distance_osrm(-4.5, 40.7, -4.4, 40.8) is None
    finally:
        for _ in range(OSRM_MAX_CONCURRENCY):
            export.OSRM_SEMAPHORE.release()


def test_gpx_splicing_out_of_time_still_passes_through_the_stations(monkeypatch):
    import geopandas as gpd
    import gpxpy

    monkeypatch.setattr(export.requests, "get", lambda *a, **k: pytest.fail("no request expected"))
    stops = gpd.GeoDataFrame({"Rótulo": ["Repsol"]}, geometry=gpd.points_from_xy([-4.5], [40.7]), crs="EPSG:4326")

    xml = export.enrich_gpx_with_stops(export.build_gpx_from_track(TRACK), stops, max_seconds=0)

    gpx = gpxpy.parse(xml)
    assert len(gpx.waypoints) == 1
    points = [(p.longitude, p.latitude) for p in gpx.tracks[0].segments[0].points]
    assert (-4.5, 40.7) in points
