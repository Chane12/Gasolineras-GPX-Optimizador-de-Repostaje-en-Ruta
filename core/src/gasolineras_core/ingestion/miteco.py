"""
gasolineras_core.ingestion.miteco
=================================
Data acquisition from the MITECO API (Ministerio para la Transición Ecológica).
Downloads the complete catalogue of Spanish fuel stations and cleans the data.
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd
import requests

from gasolineras_core.config import COORD_COLUMNS, DATA_DIR, MITECO_API_URL, PRICE_COLUMNS

FALLBACK_FILE = DATA_DIR / "fallback_miteco.parquet"

# Combustibles sin tope superior de precio (se venden por kg, no por litro)
_FUELS_NO_UPPER_BOUND = {
    "Precio Hidrogeno",
    "Precio Gas Natural Comprimido",
    "Precio Gas Natural Licuado",
}
_MAX_PRICE_EUR_L = 5.0


@dataclass(frozen=True)
class MitecoResult:
    """Encapsula los datos del MITECO junto con el timestamp de descarga."""

    df: pd.DataFrame
    fetched_at: datetime
    from_fallback: bool = False


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
        print(f"[MITECO] Error leyendo el fallback local: {e}")
        return None


def fetch_gasolineras(timeout: int = 30) -> MitecoResult:
    """
    Descarga el catálogo completo de gasolineras desde la API REST del MITECO.
    Retorna un MitecoResult con el DataFrame y la hora de descarga.
    """
    print("[MITECO] Descargando datos via requests...")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9",
    }

    # ----------------------------------------------------------------
    # Intento 1 — conexión directa al MITECO
    # ----------------------------------------------------------------
    data = None
    _err_direct: Exception | None = None
    try:
        response = requests.get(MITECO_API_URL, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        print("[MITECO] Conexión directa exitosa.")
    except (requests.exceptions.RequestException, json.decoder.JSONDecodeError) as exc:
        _err_direct = exc
        print(f"[MITECO] Conexión directa falló ({type(_err_direct).__name__}). Probando proxies públicos...")

    # ----------------------------------------------------------------
    # Intentos 2-4 — proxies de paso en cascada
    # ----------------------------------------------------------------
    if data is None:
        encoded_url = urllib.parse.quote(MITECO_API_URL, safe="")
        proxy_candidates = [
            f"https://corsproxy.io/?{encoded_url}",
            f"https://api.allorigins.win/get?url={encoded_url}",
            f"https://api.codetabs.com/v1/proxy?quest={encoded_url}",
        ]

        last_proxy_err: Exception | None = None
        for proxy_url in proxy_candidates:
            proxy_name = proxy_url.split("//")[1].split("/")[0]
            try:
                print(f"[MITECO] Intentando proxy: {proxy_name}...")
                resp = requests.get(proxy_url, headers=headers, timeout=5)  # Timeout estricto reducido a 5s
                resp.raise_for_status()

                if "allorigins.win/get" in proxy_url:
                    wrapper = resp.json()
                    data = json.loads(wrapper["contents"])
                else:
                    data = resp.json()

                print(f"[MITECO] Datos obtenidos via {proxy_name}.")
                break
            except (requests.exceptions.RequestException, json.decoder.JSONDecodeError) as exc:
                last_proxy_err = exc
                print(f"[MITECO] Proxy {proxy_name} falló: {exc}")

        if data is None:
            print("[MITECO] Todas las conexiones fallaron. Intentando cargar fallback parquet...")
            fallback = _load_fallback()
            if fallback is not None:
                return fallback

            raise ConnectionError(
                "No se pudo conectar con la API del MITECO ni directamente "
                "ni mediante ningún proxy. Comprueba tu conexión a Internet.\n"
                f"Error directo: {_err_direct}\n"
                f"Último error de proxy: {last_proxy_err}"
            )

    records = data.get("ListaEESSPrecio", [])
    if not records:
        print("[MITECO] La API no devolvió registros. Intentando cargar fallback parquet...")
        fallback = _load_fallback()
        if fallback is not None:
            return fallback

        raise ValueError("La API del MITECO no devolvió registros. Comprueba el endpoint.")

    print(f"[MITECO] Registros descargados: {len(records)}")
    df = parse_miteco_records(records)

    # Guardar fallback local
    try:
        df.to_parquet(FALLBACK_FILE)
    except Exception as e:
        print(f"[MITECO] Aviso silencioso: No se pudo guardar el fallback parquet: {e}")

    return MitecoResult(df=df, fetched_at=datetime.now(UTC))


def parse_miteco_records(records: list[dict]) -> pd.DataFrame:
    """
    Limpia los registros crudos de `ListaEESSPrecio` (función pura, sin red).

    - Precios y coordenadas: coma decimal → punto, a float.
    - Precios fuera de rango (<= 0, o >= 5 €/L salvo combustibles por kg) → NA.
    - Descarta estaciones sin coordenadas o con coordenadas 0.
    """
    df = pd.DataFrame(records)

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
