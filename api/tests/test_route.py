"""Tests for /route endpoints (no network: geocoder functions are faked)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from shapely.geometry import LineString

from gasolineras_api.main import create_app
from gasolineras_api.routers import route as route_module
from gasolineras_core.ingestion import geocoder
from gasolineras_core.ingestion.geocoder import GeocodedPlace, RoadRoute

SAMPLE_GPX = Path(__file__).resolve().parents[2] / "core" / "tests" / "fixtures" / "sample_track.gpx"

PLACES = {
    "Ávila": GeocodedPlace("Ávila", 40.6572, -4.6627, "nominatim"),
    "Segovia": GeocodedPlace("Segovia", 40.9481, -4.1172, "nominatim"),
}
ROAD = LineString([(-4.6627, 40.6572), (-4.4, 40.8), (-4.1172, 40.9481)])


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(warm_up=False))


@pytest.fixture
def fake_services(monkeypatch):
    def geocode_place(place: str) -> GeocodedPlace:
        if place not in PLACES:
            raise geocoder.PlaceNotFoundError(f"No encontramos la ubicación «{place}».")
        return PLACES[place]

    monkeypatch.setattr(geocoder, "geocode_place", geocode_place)
    monkeypatch.setattr(geocoder, "fetch_road_route_details", lambda origin, destination: RoadRoute(ROAD, 7200.0))


class TestRouteFromText:
    def test_returns_geojson_track_and_places(self, client, fake_services):
        response = client.post("/route/text", json={"origin": "Ávila", "destination": "Segovia"})

        assert response.status_code == 200
        body = response.json()
        assert body["track"]["type"] == "LineString"
        assert body["track"]["coordinates"][0] == [-4.6627, 40.6572]  # [lon, lat]
        assert body["point_count"] == 3
        assert body["origin"] == {"query": "Ávila", "lat": 40.6572, "lon": -4.6627}
        assert body["destination"]["query"] == "Segovia"
        assert body["duration_min"] == 120.0

    def test_unknown_place_is_400_with_message_for_the_user(self, client, fake_services):
        response = client.post("/route/text", json={"origin": "Ávila", "destination": "Villarriba"})

        assert response.status_code == 400
        assert response.json() == {"detail": "No encontramos la ubicación «Villarriba»."}

    def test_no_road_route_is_400(self, client, fake_services, monkeypatch):
        def no_route(origin, destination):
            raise geocoder.NoRouteError("No hay ruta por carretera entre esos dos puntos.")

        monkeypatch.setattr(geocoder, "fetch_road_route_details", no_route)

        response = client.post("/route/text", json={"origin": "Ávila", "destination": "Segovia"})

        assert response.status_code == 400
        assert "carretera" in response.json()["detail"]

    def test_external_service_down_is_503(self, client, fake_services, monkeypatch):
        def down(place):
            raise geocoder.RoutingServiceError("El servicio de búsqueda de lugares no está disponible ahora mismo.")

        monkeypatch.setattr(geocoder, "geocode_place", down)

        response = client.post("/route/text", json={"origin": "Ávila", "destination": "Segovia"})

        assert response.status_code == 503
        assert "no está disponible" in response.json()["detail"]

    def test_route_outside_spain_is_400(self, client, fake_services, monkeypatch):
        monkeypatch.setattr(
            geocoder, "fetch_road_route_details", lambda o, d: RoadRoute(LineString([(-0.1, 51.5), (-0.2, 51.6)]), None)
        )

        response = client.post("/route/text", json={"origin": "Ávila", "destination": "Segovia"})

        assert response.status_code == 400
        assert "territorio español" in response.json()["detail"]

    @pytest.mark.parametrize("body", [{"origin": "Ávila"}, {"origin": "", "destination": "Segovia"}])
    def test_invalid_body_is_422(self, client, fake_services, body):
        assert client.post("/route/text", json=body).status_code == 422

    def test_uses_the_points_picked_from_suggestions_without_geocoding(self, client, monkeypatch):
        def no_geocoding(place: str) -> GeocodedPlace:
            raise AssertionError("should not geocode")

        routed: list[tuple] = []
        monkeypatch.setattr(geocoder, "geocode_place", no_geocoding)
        monkeypatch.setattr(
            geocoder, "fetch_road_route_details", lambda o, d: routed.append((o, d)) or RoadRoute(ROAD, None)
        )

        response = client.post(
            "/route/text",
            json={
                "origin": "Ávila",
                "destination": "Segovia",
                "origin_point": {"lat": 40.6572, "lon": -4.6627},
                "destination_point": {"lat": 40.9481, "lon": -4.1172},
            },
        )

        assert response.status_code == 200
        assert routed == [((40.6572, -4.6627), (40.9481, -4.1172))]
        assert response.json()["origin"] == {"query": "Ávila", "lat": 40.6572, "lon": -4.6627}


class TestRouteFromGpx:
    def test_returns_track_from_uploaded_file(self, client):
        with SAMPLE_GPX.open("rb") as f:
            response = client.post("/route/gpx", files={"file": ("ruta.gpx", f, "application/gpx+xml")})

        assert response.status_code == 200
        body = response.json()
        assert body["point_count"] == 20
        assert len(body["track"]["coordinates"]) == 20
        assert body["origin"] is None

    def test_invalid_gpx_is_400_naming_the_file(self, client):
        response = client.post("/route/gpx", files={"file": ("mi_ruta.gpx", b"no soy un gpx", "text/plain")})

        assert response.status_code == 400
        assert "mi_ruta.gpx" in response.json()["detail"]

    def test_too_large_file_is_413(self, client, monkeypatch):
        monkeypatch.setattr(route_module, "MAX_GPX_BYTES", 100)

        with SAMPLE_GPX.open("rb") as f:
            response = client.post("/route/gpx", files={"file": ("ruta.gpx", f, "application/gpx+xml")})

        assert response.status_code == 413

    def test_missing_file_is_422(self, client):
        assert client.post("/route/gpx").status_code == 422


class TestRouteDemo:
    def test_returns_the_gredos_track(self, client):
        response = client.get("/route/demo")

        assert response.status_code == 200
        body = response.json()
        assert body["point_count"] == len(body["track"]["coordinates"]) > 100
        lon, lat = body["track"]["coordinates"][0]
        assert -6 < lon < -4 and 39.5 < lat < 41  # Sierra de Gredos
        assert body["origin"] is None


def test_openapi_documents_route_endpoints_and_errors(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert set(paths["/route/text"]["post"]["responses"]) >= {"200", "400", "422", "503"}
    assert "413" in paths["/route/gpx"]["post"]["responses"]
    assert "200" in paths["/route/demo"]["get"]["responses"]
