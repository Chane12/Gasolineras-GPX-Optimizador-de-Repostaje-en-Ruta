"""
src/optimizer/autonomy.py
=========================
Autonomy radar calculation — analysis of gaps between fuel stations
relative to vehicle range.
"""

from __future__ import annotations

import geopandas as gpd
import pyproj
from shapely.geometry import LineString


def calculate_autonomy_radar(
    track: LineString,
    gdf_top: gpd.GeoDataFrame,
    autonomia_km: float,
) -> tuple[list[dict], float]:
    """
    Calcula los intervalos y segmentos geográficos en función de la autonomía.

    Parameters
    ----------
    track : LineString
        Ruta original completa en WGS84.
    gdf_top : gpd.GeoDataFrame
        Gasolineras identificadas (con columna km_ruta).
    autonomia_km : float
        Límite del depósito del usuario en km.

    Returns
    -------
    tuple[list[dict], float]
        Lista de diccionarios representando los tramos y la longitud total.
    """
    _geod_radar = pyproj.Geod(ellps="WGS84")
    _track_coords = list(track.coords)
    _lons = [c[0] for c in _track_coords]
    _lats = [c[1] for c in _track_coords]
    _, _, _dists_m = _geod_radar.inv(_lons[:-1], _lats[:-1], _lons[1:], _lats[1:])
    route_total_km = sum(_dists_m) / 1000.0

    station_km_list: list[float] = []
    if not gdf_top.empty and "km_ruta" in gdf_top.columns:
        station_km_list = sorted(gdf_top["km_ruta"].dropna().tolist())

    checkpoints = [0.0] + station_km_list + [route_total_km]
    tramos: list[dict] = []

    for j in range(len(checkpoints) - 1):
        km_inicio = checkpoints[j]
        km_fin = checkpoints[j + 1]
        gap_km = km_fin - km_inicio

        if autonomia_km > 0:
            pct = gap_km / autonomia_km
            if gap_km > autonomia_km:
                nivel = "critico"
                emoji = "🔴"
                label = "CRÍTICO (Imposible)"
            elif gap_km > (autonomia_km * 0.8):
                nivel = "atencion"
                emoji = "🟡"
                label = "ATENCIÓN (Riesgo alto)"
            else:
                nivel = "seguro"
                emoji = "🟢"
                label = "SEGURO"
        else:
            pct = 0.0
            nivel = "seguro"
            emoji = "🟢"
            label = "—"

        if j == 0 and station_km_list:
            nombre_origen = "Inicio de ruta"
            nombre_destino = gdf_top.sort_values("km_ruta").iloc[0].get("Rótulo", f"Gasolinera #{j + 1}")
        elif j == len(checkpoints) - 2 and station_km_list:
            nombre_origen = (
                gdf_top.sort_values("km_ruta").iloc[j - 1].get("Rótulo", f"Gasolinera #{j}")
                if j > 0
                else "Inicio"
            )
            nombre_destino = "Fin de ruta"
        elif station_km_list and 0 < j < len(station_km_list):
            sorted_gdf = gdf_top.sort_values("km_ruta")
            nombre_origen = sorted_gdf.iloc[j - 1].get("Rótulo", f"Gasolinera #{j}") if j > 0 else "Inicio"
            nombre_destino = sorted_gdf.iloc[j].get("Rótulo", f"Gasolinera #{j + 1}")
        else:
            nombre_origen = f"Km {km_inicio:.0f}"
            nombre_destino = f"Km {km_fin:.0f}"

        tramos.append(
            {
                "km_inicio": km_inicio,
                "km_fin": km_fin,
                "gap_km": gap_km,
                "nivel": nivel,
                "pct": pct,
                "emoji": emoji,
                "label": label,
                "origen": nombre_origen,
                "destino": nombre_destino,
            }
        )

    return tramos, route_total_km
