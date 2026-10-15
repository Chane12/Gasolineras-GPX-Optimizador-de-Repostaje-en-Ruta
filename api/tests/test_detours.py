"""Tests for /detours (no network: the core function is faked)."""

import pytest
from fastapi.testclient import TestClient

from gasolineras_api.main import create_app
from gasolineras_api.schemas import MAX_DETOUR_STATIONS
from gasolineras_core.optimizer import export

TRACK = {"type": "LineString", "coordinates": [[-4.70, 40.60], [-4.50, 40.70], [-4.30, 40.80]]}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(warm_up=False))


def test_returns_detours_in_request_order(client, monkeypatch):
    received = {}

    def fake(track, stations):
        received["stations"] = stations
        return [{"distance_km": 3.456, "duration_min": 4.44}, None]

    monkeypatch.setattr(export, "compute_detours", fake)

    response = client.post(
        "/detours",
        json={
            "track": TRACK,
            "stations": [{"id": "a", "lat": 40.7, "lon": -4.5}, {"id": "b", "lat": 40.8, "lon": -4.3}],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert received["stations"] == [(-4.5, 40.7), (-4.3, 40.8)]  # lon, lat
    assert body["detours"][0] == {"id": "a", "lat": 40.7, "lon": -4.5, "detour_km": 3.46, "detour_min": 4.4}
    assert body["detours"][1]["detour_km"] is None
    assert body["complete"] is False


def test_complete_when_every_station_has_a_detour(client, monkeypatch):
    monkeypatch.setattr(export, "compute_detours", lambda t, s: [{"distance_km": 1.0, "duration_min": 1.0}] * len(s))

    body = client.post("/detours", json={"track": TRACK, "stations": [{"lat": 40.7, "lon": -4.5}]}).json()

    assert body["complete"] is True


@pytest.mark.parametrize(
    "stations",
    [[], [{"lat": 40.7, "lon": -4.5}] * (MAX_DETOUR_STATIONS + 1), [{"lat": 140.7, "lon": -4.5}]],
)
def test_invalid_station_lists_are_422(client, stations):
    assert client.post("/detours", json={"track": TRACK, "stations": stations}).status_code == 422
