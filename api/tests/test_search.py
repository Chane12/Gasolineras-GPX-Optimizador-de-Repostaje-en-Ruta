"""Tests for /search and /fuels (no network: in-memory catalogue with synthetic stations)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import get_args

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gasolineras_api.catalogue import PriceCatalogue
from gasolineras_api.main import create_app
from gasolineras_api.schemas import FuelId, LineStringGeometry
from gasolineras_core.config import FUEL_TYPES
from gasolineras_core.ingestion.gpx_parser import load_gpx_track
from gasolineras_core.ingestion.miteco import MitecoResult

SAMPLE_GPX = Path(__file__).resolve().parents[2] / "core" / "tests" / "fixtures" / "sample_track.gpx"

STATIONS = pd.DataFrame(
    {
        "IDEESS": ["1", "2", "3", "4", "5"],
        "Latitud": [40.665, 40.700, 40.740, 40.790, 40.820],
        "Longitud (WGS84)": [-4.660, -4.580, -4.500, -4.400, -4.340],
        "Rótulo": ["Repsol Ávila", "Cepsa N-110", "BP Villacastín", "Shell Segovia", "Galp Segovia"],
        "Municipio": ["Ávila", "Mediana", "Villacastín", "Segovia", "Segovia"],
        "Provincia": ["ÁVILA", "ÁVILA", "SEGOVIA", "SEGOVIA", "SEGOVIA"],
        "Dirección": ["N-110 km 5", "N-110 km 15", "N-110 km 25", "N-110 km 35", "N-110 km 42"],
        "Horario": ["L-D: 24H", "L-V: 07:00-22:00", "L-D: 24H", "L-D: 24H", "L-D: 24H"],
        "C.P.": ["05001", "05100", "40100", "40001", "40002"],
        "Precio Gasoleo A": [1.459, 1.389, 1.519, 1.399, 1.479],
        "Precio Gasolina 95 E5": [1.559, 1.499, 1.619, 1.509, 1.579],
    }
)


def catalogue_with(age: timedelta = timedelta(minutes=5)) -> PriceCatalogue:
    result = MitecoResult(df=STATIONS, fetched_at=datetime.now(UTC) - age)

    def fetch() -> MitecoResult:
        return result

    return PriceCatalogue(fetch=fetch)


@pytest.fixture(scope="module")
def track_json() -> dict:
    return LineStringGeometry.from_shapely(load_gpx_track(SAMPLE_GPX)).model_dump()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(catalogue_with(), warm_up=False))


def test_fuel_ids_in_the_contract_match_the_core():
    assert list(get_args(FuelId)) == list(FUEL_TYPES)


def test_fuels_lists_ids_and_spanish_labels(client):
    fuels = client.get("/fuels").json()

    assert fuels[0] == {"id": "gasolina_95", "label": "Gasolina 95"}
    assert {"id": "glp", "label": "GLP / Autogas"} in fuels


def test_search_returns_cheapest_stations_in_route_order(client, track_json):
    response = client.post("/search", json={"track": track_json, "fuel": "diesel", "max_detour_km": 10, "top_n": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["fuel"] == {"id": "diesel", "label": "Diésel (Gasoil A)"}
    assert body["prices"]["status"] == "fresh"
    names = [s["name"] for s in body["stations"]]
    assert {"Cepsa N-110", "Shell Segovia"} <= set(names)  # the two cheapest
    kms = [s["km_on_route"] for s in body["stations"]]
    assert kms == sorted(kms)
    assert body["route_km"] > 0
    assert body["autonomy"] is None


def test_station_fields(client, track_json):
    body = client.post("/search", json={"track": track_json, "fuel": "diesel", "max_detour_km": 10}).json()

    cepsa = next(s for s in body["stations"] if s["name"] == "Cepsa N-110")
    assert cepsa["id"] == "2"
    assert cepsa["price"] == 1.389
    assert cepsa["open_24h"] is False
    assert (cepsa["lat"], cepsa["lon"]) == pytest.approx((40.700, -4.580), abs=1e-5)
    assert cepsa["savings_vs_max"] == pytest.approx(body["max_price_in_corridor"] - 1.389, abs=1e-3)


def test_only_24h(client, track_json):
    body = client.post(
        "/search", json={"track": track_json, "fuel": "diesel", "max_detour_km": 10, "only_24h": True}
    ).json()

    assert all(s["open_24h"] for s in body["stations"])
    assert "Cepsa N-110" not in [s["name"] for s in body["stations"]]


def test_autonomy_radar(client, track_json):
    body = client.post(
        "/search", json={"track": track_json, "fuel": "diesel", "max_detour_km": 10, "autonomy_km": 300}
    ).json()

    radar = body["autonomy"]
    assert radar[0]["start_km"] == 0
    assert radar[-1]["end_km"] == pytest.approx(body["route_km"], abs=0.01)
    assert {seg["level"] for seg in radar} <= {"safe", "warning", "critical"}


def test_fuel_nobody_sells_returns_empty_list(client, track_json):
    body = client.post("/search", json={"track": track_json, "fuel": "glp", "max_detour_km": 10}).json()

    assert body["stations"] == []
    assert body["corridor_station_count"] > 0


def test_stale_prices_are_reported(track_json):
    client = TestClient(create_app(catalogue_with(age=timedelta(hours=30)), warm_up=False))

    body = client.post("/search", json={"track": track_json, "fuel": "diesel"}).json()

    assert body["prices"]["status"] == "very_stale"


def test_route_outside_spain_is_400(client):
    london = {"type": "LineString", "coordinates": [[-0.1, 51.5], [-0.2, 51.6]]}

    response = client.post("/search", json={"track": london})

    assert response.status_code == 400
    assert "territorio español" in response.json()["detail"]


def test_no_prices_is_503(track_json):
    def down() -> MitecoResult:
        raise ConnectionError("MITECO down")

    client = TestClient(create_app(PriceCatalogue(fetch=down), warm_up=False))

    response = client.post("/search", json={"track": track_json})

    assert response.status_code == 503


@pytest.mark.parametrize(
    "overrides",
    [{"fuel": "keroseno"}, {"top_n": 0}, {"max_detour_km": 50}, {"segment_km": 5}, {"autonomy_km": -1}],
)
def test_invalid_parameters_are_422(client, track_json, overrides):
    assert client.post("/search", json={"track": track_json, **overrides}).status_code == 422


def test_track_with_a_single_point_is_422(client):
    assert (
        client.post("/search", json={"track": {"type": "LineString", "coordinates": [[-4.6, 40.6]]}}).status_code == 422
    )
