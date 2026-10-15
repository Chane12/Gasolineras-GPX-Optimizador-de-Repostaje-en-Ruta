"""Tests for /health and the OpenAPI schema (no network)."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from gasolineras_api.catalogue import PriceCatalogue
from gasolineras_api.main import API_VERSION, create_app
from gasolineras_core.ingestion.miteco import MitecoResult


def no_network() -> MitecoResult:
    raise ConnectionError("no network in tests")


def catalogue_with(result: MitecoResult | None) -> PriceCatalogue:
    catalogue = PriceCatalogue(fetch=no_network)
    catalogue._result = result
    return catalogue


def result_aged(age: timedelta, from_fallback: bool = False) -> MitecoResult:
    return MitecoResult(
        df=pd.DataFrame({"id": range(4)}), fetched_at=datetime.now(UTC) - age, from_fallback=from_fallback
    )


def test_health_returns_ok_and_version() -> None:
    client = TestClient(create_app(catalogue_with(result_aged(timedelta(minutes=5))), warm_up=False))

    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["version"] == API_VERSION


@pytest.mark.parametrize(
    ("age", "expected"),
    [(timedelta(minutes=5), "fresh"), (timedelta(hours=3), "stale"), (timedelta(hours=30), "very_stale")],
)
def test_health_reports_price_age(age: timedelta, expected: str) -> None:
    client = TestClient(create_app(catalogue_with(result_aged(age, from_fallback=True)), warm_up=False))

    prices = client.get("/health").json()["prices"]

    assert prices["status"] == expected
    assert prices["age_minutes"] == int(age.total_seconds() // 60)
    assert prices["from_fallback"] is True
    assert prices["station_count"] == 4


def test_health_without_prices_is_still_ok_and_never_downloads() -> None:
    calls = []
    catalogue = PriceCatalogue(fetch=lambda: calls.append(1))  # type: ignore[arg-type,return-value]
    client = TestClient(create_app(catalogue, warm_up=False))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["prices"] == {
        "status": "unavailable",
        "fetched_at": None,
        "age_minutes": None,
        "from_fallback": False,
        "station_count": 0,
    }
    assert calls == []


def test_openapi_schema_is_published() -> None:
    client = TestClient(create_app(catalogue_with(None), warm_up=False))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Gasolineras en Ruta API"
    assert "/health" in schema["paths"]
