"""Place suggestions endpoint (no network: the core function is faked)."""

import pytest
from fastapi.testclient import TestClient

from gasolineras_api.main import create_app
from gasolineras_api.ratelimit import Budget, RateLimiter
from gasolineras_core.ingestion import geocoder
from gasolineras_core.ingestion.geocoder import PlaceSuggestion

VALENCIA = PlaceSuggestion("València", "Comarca de València, Comunitat Valenciana", 39.47, -0.376, "city")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(warm_up=False))


def test_returns_suggestions_for_the_typed_text(client, monkeypatch):
    seen: list[str] = []

    def suggest(q: str) -> list[PlaceSuggestion]:
        seen.append(q)
        return [VALENCIA]

    monkeypatch.setattr(geocoder, "suggest_places", suggest)

    response = client.get("/places/suggest", params={"q": "Valen"})

    assert response.status_code == 200
    assert response.json() == {
        "places": [
            {
                "name": "València",
                "context": "Comarca de València, Comunitat Valenciana",
                "lat": 39.47,
                "lon": -0.376,
                "kind": "city",
            }
        ]
    }
    assert seen == ["Valen"]


def test_photon_down_is_503_with_a_message(client, monkeypatch):
    def down(q: str) -> list[PlaceSuggestion]:
        raise geocoder.RoutingServiceError("El servicio de búsqueda de lugares no está disponible ahora mismo.")

    monkeypatch.setattr(geocoder, "suggest_places", down)

    response = client.get("/places/suggest", params={"q": "Valen"})

    assert response.status_code == 503
    assert "no está disponible" in response.json()["detail"]


def test_has_its_own_rate_limit_budget(monkeypatch):
    monkeypatch.setattr(geocoder, "suggest_places", lambda q: [])
    limiter = RateLimiter({"suggest": Budget(2, 60), "external": Budget(10, 60), "default": Budget(60, 60)})
    client = TestClient(create_app(warm_up=False, rate_limiter=limiter))

    codes = [client.get("/places/suggest", params={"q": "Val"}).status_code for _ in range(3)]

    assert codes == [200, 200, 429]


def test_query_is_required_and_bounded(client):
    assert client.get("/places/suggest").status_code == 422
    assert client.get("/places/suggest", params={"q": "x" * 101}).status_code == 422
