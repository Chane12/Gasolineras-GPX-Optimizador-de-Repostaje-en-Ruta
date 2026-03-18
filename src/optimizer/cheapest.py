"""
src/optimizer/cheapest.py
=========================
Fuel station filtering logic: Top-N cheapest, segment-based, and España Vaciada mode.
"""

from __future__ import annotations

import math

import geopandas as gpd
import pandas as pd
import shapely
import shapely.ops
from shapely.geometry import LineString

from src.config import PRICE_COLUMNS


def filter_cheapest_stations(
    gdf: gpd.GeoDataFrame,
    fuel_column: str = "Precio Gasoleo A",
    top_n: int = 5,
    track_utm: LineString | None = None,
    segment_km: float = 0.0,
) -> gpd.GeoDataFrame:
    """
    Filtra las gasolineras con precio válido para el combustible elegido
    y devuelve las top_n más baratas, opcionalmente añadiendo la más barata
    por sub-tramo de ruta.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Gasolineras dentro del buffer del recorrido (EPSG:25830).
    fuel_column : str
        Nombre exacto de la columna de precio a usar.
    top_n : int
        Número de gasolineras más baratas a devolver.
    track_utm : Optional[LineString]
        Track en EPSG:25830 para calcular km en ruta.
    segment_km : float
        Intervalo en km para buscar la más barata por tramo (0 = desactivado).

    Returns
    -------
    gpd.GeoDataFrame
        Top N gasolineras más baratas, ordenadas por km en ruta.
    """
    if fuel_column not in gdf.columns:
        available = [c for c in PRICE_COLUMNS if c in gdf.columns]
        raise ValueError(
            f"Columna '{fuel_column}' no encontrada.\n"
            f"Columnas de precio disponibles: {available}"
        )

    gdf = gdf.copy()
    gdf[fuel_column] = pd.to_numeric(gdf[fuel_column], errors="coerce")

    mask = gdf[fuel_column].notna() & (gdf[fuel_column] > 0)
    gdf_valid = gdf[mask].copy()

    if gdf_valid.empty:
        print(f"[Filtrado] [WARN] No hay gasolineras con precio para '{fuel_column}'.")
        return gdf_valid

    gdf_valid["precio_seleccionado"] = gdf_valid[fuel_column]
    gdf_valid["combustible"] = fuel_column

    # 1. Top N global
    gdf_top_global = gdf_valid.nsmallest(top_n, fuel_column).copy()

    if track_utm is not None and segment_km > 0:
        dist_total_km = track_utm.length / 1000.0
        num_tramos = max(1, math.ceil(dist_total_km / segment_km))

        top_segment_indices = []
        for i in range(num_tramos):
            start_dist = i * segment_km * 1000.0
            end_dist = min((i + 1) * segment_km * 1000.0, track_utm.length)
            segment_line = shapely.ops.substring(track_utm, start_dist, end_dist)

            possible_matches_index = list(gdf_valid.sindex.intersection(segment_line.bounds))
            if possible_matches_index:
                subset = gdf_valid.iloc[possible_matches_index]
                idx_cheapest = subset[fuel_column].idxmin()
                if pd.notna(idx_cheapest):
                    top_segment_indices.append(idx_cheapest)

        all_indices = list(set(gdf_top_global.index.tolist() + top_segment_indices))
        gdf_top = gdf_valid.loc[all_indices].copy()
        gdf_top["km_ruta"] = shapely.line_locate_point(track_utm, gdf_top.geometry) / 1000.0
        gdf_top = gdf_top.sort_values("km_ruta").reset_index(drop=True)

        print(f"\n[Filtrado] Top {top_n} global + 1 obligatoria cada {segment_km} km para '{fuel_column}':")
        for _i, row in gdf_top.iterrows():
            nombre = row.get("Rótulo", row.get("C.P.", "N/A"))
            municipio = row.get("Municipio", "")
            precio = row["precio_seleccionado"]
            km = row["km_ruta"]
            print(f"  Km {km:.1f} | {nombre} ({municipio}) --> {precio:.3f} EUR/L")
    else:
        gdf_top = gdf_top_global.copy()
        if track_utm is not None:
            gdf_top["km_ruta"] = shapely.line_locate_point(track_utm, gdf_top.geometry) / 1000.0

        gdf_top = gdf_top.reset_index(drop=True)

        print(f"\n[Filtrado] Top {top_n} más baratas para '{fuel_column}':")
        for i, row in gdf_top.iterrows():
            nombre = row.get("Rótulo", row.get("C.P.", "N/A"))
            municipio = row.get("Municipio", "")
            precio = row["precio_seleccionado"]
            km_str = f" (Km {row['km_ruta']:.1f})" if "km_ruta" in row else ""
            print(f"  #{i + 1} {nombre}{km_str} ({municipio}) --> {precio:.3f} EUR/L")

    return gdf_top


def filter_all_stations_on_route(
    gdf: gpd.GeoDataFrame,
    fuel_column: str,
    track_utm: LineString | None = None,
) -> gpd.GeoDataFrame:
    """
    Modo España Vaciada: devuelve TODAS las gasolineras dentro del corredor
    de la ruta, ordenadas geográficamente por su posición en la ruta.

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Gasolineras dentro del buffer estrecho (EPSG:25830).
    fuel_column : str
        Columna de precio para coerción numérica.
    track_utm : Optional[LineString]
        Track en EPSG:25830 para calcular el km en ruta.

    Returns
    -------
    gpd.GeoDataFrame
        Todas las gasolineras del corredor, ordenadas por km_ruta.
    """
    gdf = gdf.copy()

    if fuel_column in gdf.columns:
        gdf[fuel_column] = pd.to_numeric(gdf[fuel_column], errors="coerce")
        gdf["precio_seleccionado"] = gdf[fuel_column]
        gdf = gdf[gdf[fuel_column].notna() & (gdf[fuel_column] > 0)].copy()
    else:
        return gpd.GeoDataFrame(columns=gdf.columns, crs=gdf.crs)

    gdf["combustible"] = fuel_column

    if track_utm is not None:
        gdf["km_ruta"] = shapely.line_locate_point(track_utm, gdf.geometry) / 1000.0
        gdf = gdf.sort_values("km_ruta").reset_index(drop=True)
    else:
        gdf = gdf.reset_index(drop=True)

    print(f"[España Vaciada] {len(gdf)} gasolineras en corredor estricto para '{fuel_column}'.")
    return gdf
