"""Tests for the API skeleton (no network)."""

from fastapi.testclient import TestClient

from gasolineras_api.main import API_VERSION, create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": API_VERSION}


def test_openapi_schema_is_published() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Gasolineras en Ruta API"
    assert "/health" in schema["paths"]
