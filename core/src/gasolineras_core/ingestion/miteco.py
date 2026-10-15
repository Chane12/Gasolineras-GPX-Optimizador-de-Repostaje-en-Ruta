"""
gasolineras_core.ingestion.miteco
=================================
Data acquisition from the MITECO API (Ministerio para la Transición Ecológica).
Downloads the complete catalogue of Spanish fuel stations and cleans the data.
"""

from __future__ import annotations

import json
import logging
import ssl
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

from gasolineras_core.config import (
    COORD_COLUMNS,
    DATA_DIR,
    MITECO_API_URL,
    MITECO_COLUMN_ALIASES,
    MITECO_EXTRA_TLS_CIPHERS,
    MITECO_HOST_PREFIX,
    PRICE_COLUMNS,
    PRICES_FRESH_MAX_AGE_S,
    PRICES_STRONG_WARNING_AGE_S,
    USER_AGENT,
)

logger = logging.getLogger(__name__)

FALLBACK_FILE = DATA_DIR / "fallback_miteco.parquet"

# Combustibles sin tope superior de precio (se venden por kg, no por litro)
_FUELS_NO_UPPER_BOUND = {
    "Precio Hidrogeno",
    "Precio Gas Natural Comprimido",
    "Precio Gas Natural Licuado",
}
_MAX_PRICE_EUR_L = 5.0

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9",
}


@dataclass(frozen=True)
class MitecoResult:
    """Encapsula los datos del MITECO junto con el timestamp de descarga."""

    df: pd.DataFrame
    fetched_at: datetime
    from_fallback: bool = False


class PriceFreshness(StrEnum):
    FRESH = "fresh"  # <= 30 min
    STALE = "stale"  # <= 24 h: aviso visible
    VERY_STALE = "very_stale"  # > 24 h: aviso fuerte


def price_freshness(fetched_at: datetime, now: datetime | None = None) -> PriceFreshness:
    """Clasifica la antigüedad de los precios según la decisión de producto (ver config.py)."""
    age_s = ((now or datetime.now(UTC)) - fetched_at).total_seconds()
    if age_s <= PRICES_FRESH_MAX_AGE_S:
        return PriceFreshness.FRESH
    if age_s <= PRICES_STRONG_WARNING_AGE_S:
        return PriceFreshness.STALE
    return PriceFreshness.VERY_STALE


def miteco_ssl_context() -> ssl.SSLContext:
    """Contexto TLS por defecto (verifica certificado y host) más el único cifrado que acepta el MITECO."""
    ctx = ssl.create_default_context()
    default_ciphers = ":".join(c["name"] for c in ctx.get_ciphers())
    ctx.set_ciphers(f"{default_ciphers}:{MITECO_EXTRA_TLS_CIPHERS}")
    return ctx


class _MitecoTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args: Any, **kwargs: Any) -> None:
        kwargs["ssl_context"] = miteco_ssl_context()
        super().init_poolmanager(*args, **kwargs)


def _build_session() -> requests.Session:
    session = requests.Session()
    session.mount(MITECO_HOST_PREFIX, _MitecoTLSAdapter())
    return session


_SESSION = _build_session()


def _load_fallback() -> MitecoResult | None:
    """
    Carga la copia local del último catálogo descargado.
    El timestamp es la fecha de modificación del archivo (no "ahora"),
    para que la UI muestre la antigüedad real de los precios.
    """
    if not FALLBACK_FILE.exists():
        return None
    try:
        df = pd.read_parquet(FALLBACK_FILE)
        fetched_at = datetime.fromtimestamp(FALLBACK_FILE.stat().st_mtime, tz=UTC)
        return MitecoResult(df=df, fetched_at=fetched_at, from_fallback=True)
    except Exception as e:
        logger.warning("Could not read the MITECO fallback file: %s", e)
        return None


def _fetch_via_proxies(timeout: float) -> dict | None:
    """Proxies públicos de terceros. Solo los usa la app Streamlit; la API no (ADR 0005)."""
    encoded_url = urllib.parse.quote(MITECO_API_URL, safe="")
    proxy_candidates = [
        f"https://corsproxy.io/?{encoded_url}",
        f"https://api.allorigins.win/get?url={encoded_url}",
        f"https://api.codetabs.com/v1/proxy?quest={encoded_url}",
    ]
    for proxy_url in proxy_candidates:
        proxy_name = proxy_url.split("//")[1].split("/")[0]
        try:
            resp = requests.get(proxy_url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            data = json.loads(resp.json()["contents"]) if "allorigins.win/get" in proxy_url else resp.json()
            logger.info("MITECO data obtained via proxy %s", proxy_name)
            return data
        except (requests.exceptions.RequestException, json.decoder.JSONDecodeError, KeyError) as exc:
            logger.warning("MITECO proxy %s failed: %s", proxy_name, exc)
    return None


def fetch_gasolineras(timeout: int = 30, use_proxies: bool = True) -> MitecoResult:
    """
    Descarga el catálogo completo de gasolineras desde la API REST del MITECO.

    Si la conexión directa falla, prueba los proxies públicos (si ``use_proxies``) y, por último,
    la copia local (``from_fallback=True``, con su antigüedad real).

    Raises
    ------
    ConnectionError
        Si no se puede descargar y no hay copia local.
    ValueError
        Si la API responde sin registros y no hay copia local.
    """
    data = None
    err_direct: Exception | None = None
    try:
        response = _SESSION.get(MITECO_API_URL, headers=_HEADERS, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        logger.info("MITECO direct download OK")
    except (requests.exceptions.RequestException, json.decoder.JSONDecodeError) as exc:
        err_direct = exc
        logger.warning("MITECO direct download failed: %s", exc)

    if data is None and use_proxies:
        data = _fetch_via_proxies(timeout=5)

    records = data.get("ListaEESSPrecio", []) if isinstance(data, dict) else []
    if not records:
        fallback = _load_fallback()
        if fallback is not None:
            logger.warning("Using the MITECO fallback file from %s", fallback.fetched_at.isoformat())
            return fallback
        if data is None:
            raise ConnectionError(
                "No se pudo conectar con la API del MITECO y no hay copia local de los precios. "
                f"Error de la conexión directa: {err_direct}"
            )
        raise ValueError("La API del MITECO no devolvió registros y no hay copia local de los precios.")

    logger.info("MITECO records downloaded: %d", len(records))
    df = parse_miteco_records(records)

    try:
        df.to_parquet(FALLBACK_FILE)
    except Exception as e:
        logger.warning("Could not save the MITECO fallback file: %s", e)

    return MitecoResult(df=df, fetched_at=datetime.now(UTC))


def parse_miteco_records(records: list[dict]) -> pd.DataFrame:
    """
    Limpia los registros crudos de `ListaEESSPrecio` (función pura, sin red).

    - Precios y coordenadas: coma decimal → punto, a float.
    - Precios fuera de rango (<= 0, o >= 5 €/L salvo combustibles por kg) → NA.
    - Descarta estaciones sin coordenadas o con coordenadas 0.
    """
    df = pd.DataFrame(records).rename(columns=MITECO_COLUMN_ALIASES)

    for col in PRICE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False).str.strip(), errors="coerce")
            if col in _FUELS_NO_UPPER_BOUND:
                df[col] = df[col].where(df[col].isna() | (df[col] > 0.0), pd.NA)
            else:
                df[col] = df[col].where(df[col].isna() | ((df[col] > 0.0) & (df[col] < _MAX_PRICE_EUR_L)), pd.NA)

    for col in COORD_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False).str.strip(), errors="coerce")

    lat_col, lon_col = COORD_COLUMNS
    filas_antes = len(df)
    df = df.dropna(subset=[lat_col, lon_col])
    df = df.loc[(df[lat_col] != 0.0) & (df[lon_col] != 0.0)]
    print(f"[MITECO] Filas eliminadas por falta de coordenadas: {filas_antes - len(df)} -- Válidas: {len(df)}")

    return df.reset_index(drop=True)
