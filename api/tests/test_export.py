"""Tests for /export (no network: OSRM requests fail fast, sleeps are skipped)."""

import urllib.parse

import gpxpy
import pytest
import requests
from fastapi.testclient import TestClient

from gasolineras_api.main import create_app
from gasolineras_core.optimizer import export

TRACK = {"type": "LineString", "coordinates": [[-4.70, 40.60], [-4.50, 40.70], [-4.30, 40.80]]}


@pytest.fixture
def client(monkeypatch) -> TestClient:
    def no_network(*_a, **_k):
        raise requests.ConnectionError("no network in tests")

    monkeypatch.setattr(export.requests, "get", no_network)
    monkeypatch.setattr(export.time, "sleep", lambda _s: None)
    return TestClient(create_app(warm_up=False))


def test_gmaps_url_has_origin_destination_and_stops(client):
    body = client.post(
        "/export/gmaps-url",
        json={"origin": [-4.7, 40.6], "destination": [-4.3, 40.8], "stops": [{"lat": 40.7, "lon": -4.5}]},
    ).json()

    query = urllib.parse.parse_qs(urllib.parse.urlparse(body["url"]).query)
    assert query["origin"] == ["40.600000,-4.700000"]
    assert query["destination"] == ["40.800000,-4.300000"]
    assert query["waypoints"] == ["40.700000,-4.500000"]
    assert body["truncated"] == 0


def test_gmaps_url_truncates_beyond_nine_stops(client):
    stops = [{"lat": 40.6 + i * 0.01, "lon": -4.6} for i in range(12)]

    body = client.post(
        "/export/gmaps-url", json={"origin": [-4.7, 40.6], "destination": [-4.3, 40.8], "stops": stops}
    ).json()

    assert body["truncated"] == 3


def test_gpx_contains_track_and_stop_waypoints(client):
    response = client.post(
        "/export/gpx",
        json={
            "track": TRACK,
            "stops": [{"name": "Repsol Ávila", "lat": 40.7, "lon": -4.5, "price": 1.559, "liters": 20, "cost": 31.18}],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/gpx+xml")
    assert "attachment" in response.headers["content-disposition"]
    gpx = gpxpy.parse(response.text)
    assert len(gpx.waypoints) == 1
    name = gpx.waypoints[0].name or ""
    assert "Repsol Ávila" in name
    assert "1.559" in name
    points = [p for t in gpx.tracks for s in t.segments for p in s.points]
    # OSRM unavailable: the track still goes through the station
    assert any(abs(p.latitude - 40.7) < 1e-9 and abs(p.longitude + 4.5) < 1e-9 for p in points)


def test_gpx_without_stops_is_just_the_route(client):
    gpx = gpxpy.parse(client.post("/export/gpx", json={"track": TRACK}).text)

    assert gpx.waypoints == []
    assert len(gpx.tracks[0].segments[0].points) == 3


def test_too_many_gpx_stops_is_422(client):
    stops = [{"name": f"G{i}", "lat": 40.7, "lon": -4.5} for i in range(11)]
    assert client.post("/export/gpx", json={"track": TRACK, "stops": stops}).status_code == 422
