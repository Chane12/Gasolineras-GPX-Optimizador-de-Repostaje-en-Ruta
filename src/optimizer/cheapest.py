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

    # 1. Crear una Serie de coerción numérica para evaluar precios sin tocar el DataFrame padre
    precios_num = pd.to_numeric(gdf[fuel_column], errors="coerce")
    mask_precios = precios_num.notna() & (precios_num > 0)

    if not mask_precios.any():
        print(f"[Filtrado] [WARN] No hay gasolineras con precio para '{fuel_column}'.")
        return gdf.iloc[0:0].copy()

    # Construimos el repositorio de índices de ganadores
    top_indices = set()

    # 2. Obtenemos los N índices globales más baratos
    global_indices = precios_num[mask_precios].nsmallest(top_n).index
    top_indices.update(global_indices)

    # 3. Búsqueda iterativa aprovechando la pre-existencia del R-Tree en `gdf` inmutable
    if track_utm is not None and segment_km > 0:
        dist_total_km = track_utm.length / 1000.0
        num_tramos = max(1, math.ceil(dist_total_km / segment_km))

        for i in range(num_tramos):
            start_dist = i * segment_km * 1000.0
            end_dist = min((i + 1) * segment_km * 1000.0, track_utm.length)
            segment_line = shapely.ops.substring(track_utm, start_dist, end_dist)

            # Usamos el índice GEOS nativo sobre el DataFrame original íntegro
            possible_ilocs = gdf.sindex.intersection(segment_line.bounds)
            if len(possible_ilocs) > 0:
                subset_indices = gdf.iloc[possible_ilocs].index
                subset_precios = precios_num.loc[subset_indices]
                valid_subset = subset_precios[subset_precios.notna() & (subset_precios > 0)]
                
                if not valid_subset.empty:
                    idx_cheapest = valid_subset.idxmin()
                    if pd.notna(idx_cheapest):
                        top_indices.add(idx_cheapest)

    # 4. Único .copy() permitido. Desacoplamos estrictamente las N filas vencedoras
    gdf_top = gdf.loc[list(top_indices)].copy()
    
    gdf_top["precio_seleccionado"] = precios_num.loc[list(top_indices)]
    gdf_top["combustible"] = fuel_column

    if track_utm is not None:
        gdf_top["km_ruta"] = shapely.line_locate_point(track_utm, gdf_top.geometry) / 1000.0
        gdf_top = gdf_top.sort_values("km_ruta").reset_index(drop=True)
    else:
        gdf_top = gdf_top.sort_values("precio_seleccionado").reset_index(drop=True)

    print(f"\n[Filtrado] Resultados ({len(gdf_top)} estaciones) para '{fuel_column}':")
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
    """
    if fuel_column not in gdf.columns:
        return gpd.GeoDataFrame(columns=gdf.columns, crs=gdf.crs)

    precios_num = pd.to_numeric(gdf[fuel_column], errors="coerce")
    mask_precios = precios_num.notna() & (precios_num > 0)
    
    # Única copia de los elementos validados de la criba
    gdf_valid = gdf.loc[mask_precios].copy()
    
    if gdf_valid.empty:
        return gdf_valid

    gdf_valid["precio_seleccionado"] = precios_num.loc[mask_precios]
    gdf_valid["combustible"] = fuel_column

    if track_utm is not None:
        gdf_valid["km_ruta"] = shapely.line_locate_point(track_utm, gdf_valid.geometry) / 1000.0
        gdf_valid = gdf_valid.sort_values("km_ruta").reset_index(drop=True)
    else:
        gdf_valid = gdf_valid.reset_index(drop=True)

    print(f"[España Vaciada] {len(gdf_valid)} gasolineras en corredor estricto para '{fuel_column}'.")
    return gdf_valid
