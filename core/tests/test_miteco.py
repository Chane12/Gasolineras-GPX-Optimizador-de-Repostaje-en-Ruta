"""
Tests offline de la ingesta MITECO: limpieza de datos, descarga simulada y fallback local.
Nunca tocan la red: `requests.get` se sustituye por un doble de pruebas.
"""

import json
import os
import socket
import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest
import requests

from gasolineras_core.config import MITECO_API_URL, USER_AGENT
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

    def test_lpg_column_with_accent_is_parsed_as_a_price(self):
        """Bug: config used "petroleo" without accent, so GLP was never parsed nor found."""
        records = [
            {"Latitud": "40,1", "Longitud (WGS84)": "-4,1", "Precio Gases licuados del petróleo": "0,989"},
            {"Latitud": "40,2", "Longitud (WGS84)": "-4,2", "Precio Gases licuados del petróleo": ""},
        ]
        df = miteco.parse_miteco_records(records)
        assert df["Precio Gases licuados del petróleo"].tolist()[0] == pytest.approx(0.989)
        assert pd.isna(df["Precio Gases licuados del petróleo"].tolist()[1])

    def test_old_column_names_are_renamed(self):
        records = [{"Latitud": "40,1", "Longitud (WGS84)": "-4,1", "Precio Gases licuados del petroleo": "0,989"}]
        df = miteco.parse_miteco_records(records)
        assert df["Precio Gases licuados del petróleo"].tolist() == [pytest.approx(0.989)]

    def test_index_is_reset(self, miteco_payload):
        df = miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"])
        assert list(df.index) == [0, 1, 2]


# ---------------------------------------------------------------------------
# fetch_gasolineras — red simulada
# ---------------------------------------------------------------------------


class FakeNetwork:
    """Replaces both the MITECO session (direct download) and requests.get (proxies). Records the calls."""

    def __init__(self, monkeypatch, direct, proxies=_always_fail) -> None:
        self.direct_calls: list[dict] = []
        self.proxy_calls: list[str] = []

        def fake_direct(url, **kwargs):
            self.direct_calls.append({"url": url, **kwargs})
            return direct(url, **kwargs)

        def fake_proxy(url, **kwargs):
            self.proxy_calls.append(url)
            return proxies(url, **kwargs)

        monkeypatch.setattr(miteco._SESSION, "get", fake_direct)
        monkeypatch.setattr(miteco.requests, "get", fake_proxy)


class TestFetchGasolineras:
    def test_direct_success_returns_fresh_result_and_saves_fallback(self, miteco_payload, fallback_file, monkeypatch):
        net = FakeNetwork(monkeypatch, direct=lambda *a, **k: _FakeResponse(miteco_payload))

        result = miteco.fetch_gasolineras()

        assert len(result.df) == 3
        assert result.from_fallback is False
        assert (datetime.now(UTC) - result.fetched_at).total_seconds() < 60
        assert fallback_file.exists()
        assert net.proxy_calls == []

    def test_direct_download_identifies_itself(self, miteco_payload, fallback_file, monkeypatch):
        net = FakeNetwork(monkeypatch, direct=lambda *a, **k: _FakeResponse(miteco_payload))

        miteco.fetch_gasolineras()

        headers = net.direct_calls[0]["headers"]
        assert headers["User-Agent"] == USER_AGENT
        assert net.direct_calls[0]["timeout"] is not None

    def test_proxies_are_tried_when_direct_fails(self, miteco_payload, fallback_file, monkeypatch):
        net = FakeNetwork(monkeypatch, direct=_always_fail, proxies=lambda *a, **k: _FakeResponse(miteco_payload))

        result = miteco.fetch_gasolineras()

        assert result.from_fallback is False
        assert len(net.proxy_calls) == 1

    def test_without_proxies_goes_straight_to_fallback(self, miteco_payload, fallback_file, monkeypatch):
        miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"]).to_parquet(fallback_file)
        net = FakeNetwork(monkeypatch, direct=_always_fail, proxies=lambda *a, **k: _FakeResponse(miteco_payload))

        result = miteco.fetch_gasolineras(use_proxies=False)

        assert result.from_fallback is True
        assert net.proxy_calls == []

    def test_all_sources_down_uses_fallback_with_its_real_age(self, miteco_payload, fallback_file, monkeypatch):
        miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"]).to_parquet(fallback_file)
        two_hours_ago = datetime.now(UTC).timestamp() - 2 * 3600
        os.utime(fallback_file, (two_hours_ago, two_hours_ago))
        FakeNetwork(monkeypatch, direct=_always_fail)

        result = miteco.fetch_gasolineras()

        assert result.from_fallback is True
        assert len(result.df) == 3
        age_h = (datetime.now(UTC) - result.fetched_at).total_seconds() / 3600
        assert age_h == pytest.approx(2, abs=0.1)

    def test_all_sources_down_without_fallback_raises(self, fallback_file, monkeypatch):
        FakeNetwork(monkeypatch, direct=_always_fail)

        with pytest.raises(ConnectionError, match="MITECO"):
            miteco.fetch_gasolineras()

    def test_empty_api_response_uses_fallback(self, miteco_payload, fallback_file, monkeypatch):
        miteco.parse_miteco_records(miteco_payload["ListaEESSPrecio"]).to_parquet(fallback_file)
        FakeNetwork(monkeypatch, direct=lambda *a, **k: _FakeResponse({"ListaEESSPrecio": []}))

        result = miteco.fetch_gasolineras()

        assert result.from_fallback is True

    def test_empty_api_response_without_fallback_raises_value_error(self, fallback_file, monkeypatch):
        FakeNetwork(monkeypatch, direct=lambda *a, **k: _FakeResponse({"ListaEESSPrecio": []}))

        with pytest.raises(ValueError, match="no devolvió registros"):
            miteco.fetch_gasolineras(use_proxies=False)


# ---------------------------------------------------------------------------
# TLS con el MITECO (ADR 0007)
# ---------------------------------------------------------------------------


class TestMitecoTLS:
    def test_context_adds_the_miteco_cipher_and_keeps_verification(self):
        ctx = miteco.miteco_ssl_context()

        names = {c["name"] for c in ctx.get_ciphers()}
        assert "AES256-GCM-SHA384" in names
        assert "ECDHE-RSA-AES256-GCM-SHA384" in names  # modern defaults are kept
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_session_uses_the_tls_adapter_only_for_the_miteco_host(self):
        miteco_adapter = miteco._SESSION.get_adapter(MITECO_API_URL)
        other_adapter = miteco._SESSION.get_adapter("https://corsproxy.io/")
        assert isinstance(miteco_adapter, miteco._MitecoTLSAdapter)
        assert not isinstance(other_adapter, miteco._MitecoTLSAdapter)

    @pytest.mark.network
    def test_real_tls_handshake_with_miteco(self):
        host = MITECO_API_URL.split("/")[2]
        with (
            socket.create_connection((host, 443), timeout=15) as sock,
            miteco.miteco_ssl_context().wrap_socket(sock, server_hostname=host) as tls,
        ):
            assert tls.version() is not None


# ---------------------------------------------------------------------------
# Antigüedad de los precios
# ---------------------------------------------------------------------------


class TestPriceFreshness:
    NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

    @pytest.mark.parametrize(
        ("age", "expected"),
        [
            (timedelta(minutes=0), miteco.PriceFreshness.FRESH),
            (timedelta(minutes=30), miteco.PriceFreshness.FRESH),
            (timedelta(minutes=31), miteco.PriceFreshness.STALE),
            (timedelta(hours=24), miteco.PriceFreshness.STALE),
            (timedelta(hours=24, minutes=1), miteco.PriceFreshness.VERY_STALE),
        ],
    )
    def test_thresholds(self, age, expected):
        assert miteco.price_freshness(self.NOW - age, now=self.NOW) == expected
