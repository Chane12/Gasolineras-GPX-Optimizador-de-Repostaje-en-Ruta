"""
Tests offline de la ingesta MITECO: limpieza de datos, descarga simulada y fallback local.
Nunca tocan la red: `requests.get` se sustituye por un doble de pruebas.
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
import requests

from gasolineras_core.ingestion import miteco

FIXTURE = Path(__file__).parent / "fixtures" / "miteco_sample.json"


@pytest.fixture
def miteco_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def fallback_file(tmp_path, monkeypatch) -> Path:
    """Redirige el fallback parquet a un directorio temporal."""
    path = tmp_path / "fallback_miteco.parquet"
    monkeypatch.setattr(miteco, "FALLBACK_FILE", path)
    return path


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


def _always_fail(*_args, **_kwargs):
    raise requests.exceptions.ConnectionError("sin red (test)")


# ---------------------------------------------------------------------------
# parse_miteco_records — función pura
# ---------------------------------------------------------------------------


class TestParseMitecoRecords:
    def test_drops_rows_without_or_with_zero_coordinates(self, miteco_payload):
        df = miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"])
        assert list(df["Rótulo"]) == ["REPSOL", "BP", "HIDROGENERA"]

    def test_converts_comma_decimals_to_float(self, miteco_payload):
        df = miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"])
        assert df.loc[0, "Latitud"] == pytest.approx(40.665)
        assert df.loc[0, "Longitud (WGS84)"] == pytest.approx(-4.66)
        assert df.loc[0, "Precio Gasoleo A"] == pytest.approx(1.459)

    def test_empty_and_out_of_range_prices_become_na(self, miteco_payload):
        df = miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"]).set_index("Rótulo")
        assert pd.isna(df.loc["BP", "Precio Gasoleo A"])  # cadena vacía
        assert pd.isna(df.loc["HIDROGENERA", "Precio Gasoleo A"])  # 0,000
        assert pd.isna(df.loc["HIDROGENERA", "Precio Gasolina 95 E5"])  # 9,999 >= 5 €/L

    def test_fuels_sold_by_kg_have_no_upper_bound(self, miteco_payload):
        df = miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"]).set_index("Rótulo")
        assert df.loc["HIDROGENERA", "Precio Hidrogeno"] == pytest.approx(12.5)
        assert df.loc["BP", "Precio Gas Natural Comprimido"] == pytest.approx(1.299)

    def test_index_is_reset(self, miteco_payload):
        df = miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"])
        assert list(df.index) == [0, 1, 2]


# ---------------------------------------------------------------------------
# fetch_gasolineras — red simulada
# ---------------------------------------------------------------------------


class TestFetchGasolineras:
    def test_direct_success_returns_fresh_result_and_saves_fallback(
        self, miteco_payload, fallback_file, monkeypatch
    ):
        monkeypatch.setattr(miteco.requests, "get", lambda *a, **k: _FakeResponse(miteco_payload))

        result = miteco.fetch_gasolineras()

        assert len(result.df) == 3
        assert result.from_fallback is False
        assert (datetime.now(UTC) - result.fetched_at).total_seconds() < 60
        assert fallback_file.exists()

    def test_all_sources_down_uses_fallback_with_its_real_age(self, miteco_payload, fallback_file, monkeypatch):
        miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"]).to_parquet(fallback_file)
        two_hours_ago = datetime.now(UTC).timestamp() - 2 * 3600
        os.utime(fallback_file, (two_hours_ago, two_hours_ago))
        monkeypatch.setattr(miteco.requests, "get", _always_fail)

        result = miteco.fetch_gasolineras()

        assert result.from_fallback is True
        assert len(result.df) == 3
        age_h = (datetime.now(UTC) - result.fetched_at).total_seconds() / 3600
        assert age_h == pytest.approx(2, abs=0.1)

    def test_all_sources_down_without_fallback_raises(self, fallback_file, monkeypatch):
        monkeypatch.setattr(miteco.requests, "get", _always_fail)

        with pytest.raises(ConnectionError, match="MITECO"):
            miteco.fetch_gasolineras()

    def test_empty_api_response_uses_fallback(self, miteco_payload, fallback_file, monkeypatch):
        miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"]).to_parquet(fallback_file)
        monkeypatch.setattr(miteco.requests, "get", lambda *a, **k: _FakeResponse({"ListaEESSPrecio": []}))

        result = miteco.fetch_gasolineras()

        assert result.from_fallback is True
