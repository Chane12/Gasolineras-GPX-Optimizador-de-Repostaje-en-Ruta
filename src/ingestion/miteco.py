"""
src/ingestion/miteco.py
=======================
Data acquisition from the MITECO API (Ministerio para la Transición Ecológica).
Downloads the complete catalogue of Spanish fuel stations and cleans the data.
"""

from __future__ import annotations

import json
import urllib.parse

import pandas as pd
import requests

from src.config import COORD_COLUMNS, MITECO_API_URL, PRICE_COLUMNS, PROJECT_ROOT


def fetch_gasolineras(timeout: int = 30) -> pd.DataFrame:
    """
    Descarga el catálogo completo de gasolineras desde la API REST del MITECO.
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
        response = requests.get(MITECO_API_URL, headers=headers, timeout=10) # Timeout reducido a 10s
        response.raise_for_status()
        data = response.json()
        print("[MITECO] Conexión directa exitosa.")
    except (requests.exceptions.RequestException, json.decoder.JSONDecodeError) as exc:
        _err_direct = exc
        print(
            f"[MITECO] Conexión directa falló ({type(_err_direct).__name__}). "
            "Probando proxies públicos..."
        )

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
                resp = requests.get(proxy_url, headers=headers, timeout=5) # Timeout estricto reducido a 5s
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
            fallback_file = PROJECT_ROOT / "fallback_miteco.parquet"
            if fallback_file.exists():
                print("[MITECO] Todas las conexiones fallaron. Intentando cargar fallback parquet...")
                try:
                    return pd.read_parquet(fallback_file)
                except Exception as e:
                    print(f"[MITECO] Error leyendo el fallback local: {e}")

            raise ConnectionError(
                "No se pudo conectar con la API del MITECO ni directamente "
                "ni mediante ningún proxy. Comprueba tu conexión a Internet.\n"
                f"Error directo: {_err_direct}\n"
                f"Último error de proxy: {last_proxy_err}"
            )

    records = data.get("ListaEESSPrecio", [])
    if not records:
        fallback_file = PROJECT_ROOT / "fallback_miteco.parquet"
        if fallback_file.exists():
            print("[MITECO] La API no devolvió registros. Intentando cargar fallback parquet...")
            try:
                return pd.read_parquet(fallback_file)
            except Exception as e:
                print(f"[MITECO] Error leyendo el fallback local: {e}")

        raise ValueError("La API del MITECO no devolvió registros. Comprueba el endpoint.")

    df = pd.DataFrame(records)
    print(f"[MITECO] Registros descargados: {len(df)}")

    # --- Limpieza de campos numéricos (coma → punto) ---
    for col in PRICE_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", ".", regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce")

            _FUELS_SPECIAL = {
                "Precio Hidrogeno",
                "Precio Gas Natural Comprimido",
                "Precio Gas Natural Licuado",
            }
            if col in _FUELS_SPECIAL:
                df[col] = df[col].where((df[col].isna()) | (df[col] > 0.0), pd.NA)
            else:
                df[col] = df[col].where((df[col].isna()) | ((df[col] > 0.0) & (df[col] < 5.0)), pd.NA)

    for col in COORD_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", ".", regex=False).str.strip()
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- Eliminar filas sin coordenadas ---
    lat_col = "Latitud"
    lon_col = "Longitud (WGS84)"
    filas_antes = len(df)
    df = df.dropna(subset=[lat_col, lon_col])
    df = df[(df[lat_col] != 0.0) & (df[lon_col] != 0.0)]
    print(f"[MITECO] Filas eliminadas por falta de coordenadas: {filas_antes - len(df)} -- Válidas: {len(df)}")

    df = df.reset_index(drop=True)

    # Guardar fallback local
    try:
        df.to_parquet(PROJECT_ROOT / "fallback_miteco.parquet")
    except Exception as e:
        print(f"[MITECO] Aviso silencioso: No se pudo guardar el fallback parquet: {e}")

    return df
