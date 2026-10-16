"""Cross-cutting behaviour of the app: CORS, compression and unexpected errors (no network)."""

import pytest
from fastapi.testclient import TestClient

from gasolineras_api.main import DEFAULT_CORS_ORIGINS, cors_origins_from_env, create_app
from gasolineras_core.config import DEMO_GPX_PATH
from gasolineras_core.optimizer import export

WEB = "https://gasolineras.example"


def test_cors_allows_the_configured_web_origin():
    client = TestClient(create_app(warm_up=False, cors_origins=[WEB]))

    preflight = client.options(
        "/search",
        headers={
            "Origin": WEB,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    response = client.get("/health", headers={"Origin": WEB})

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == WEB
    assert response.headers["access-control-allow-origin"] == WEB


def test_cors_rejects_other_origins():
    client = TestClient(create_app(warm_up=False, cors_origins=[WEB]))

    response = client.get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_from_env(monkeypatch):
    monkeypatch.setenv("GASOLINERAS_CORS_ORIGINS", " https://a.example/ , https://b.example ")
    assert cors_origins_from_env() == ["https://a.example", "https://b.example"]

    monkeypatch.delenv("GASOLINERAS_CORS_ORIGINS")
    assert cors_origins_from_env() == DEFAULT_CORS_ORIGINS


def test_large_responses_are_compressed():
    client = TestClient(create_app(warm_up=False))

    with DEMO_GPX_PATH.open("rb") as f:  # ~10,700 points
        response = client.post(
            "/route/gpx", files={"file": ("r.gpx", f, "application/gpx+xml")}, headers={"Accept-Encoding": "gzip"}
        )

    assert response.status_code == 200
    assert response.headers.get("content-encoding") == "gzip"
    assert response.json()["point_count"] > 10_000


def test_unexpected_errors_are_500_with_a_spanish_message(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("bug")

    monkeypatch.setattr(export, "compute_detours", boom)
    client = TestClient(create_app(warm_up=False), raise_server_exceptions=False)

    response = client.post(
        "/detours",
        json={
            "track": {"type": "LineString", "coordinates": [[-4.7, 40.6], [-4.3, 40.8]]},
            "stations": [{"lat": 40.7, "lon": -4.5}],
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Ha ocurrido un error inesperado. Inténtalo de nuevo y, si se repite, avísanos."
    }


@pytest.mark.parametrize("path", ["/fuels", "/health"])
def test_small_responses_are_not_compressed(path):
    response = TestClient(create_app(warm_up=False)).get(path, headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in response.headers
