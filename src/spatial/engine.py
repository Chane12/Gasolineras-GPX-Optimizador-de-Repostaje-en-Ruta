"""
src/spatial/engine.py
=====================
Core GIS operations: route buffer, station GeoDataFrame construction,
and spatial join (R-Tree accelerated).
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from src.config import CRS_UTM30N, CRS_WGS84


def build_route_buffer(
    track: LineString,
    buffer_meters: float = 5000.0,
) -> gpd.GeoDataFrame:
    """
    Transforma el track de WGS84 a UTM 30N, aplica un buffer en metros y
    devuelve el polígono resultante en un GeoDataFrame en EPSG:25830.

    Parameters
    ----------
    track : LineString
        Ruta simplificada en EPSG:4326.
    buffer_meters : float
        Radio del buffer en metros.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame con una única fila: el polígono del buffer en EPSG:25830.
    """
    gdf_track = gpd.GeoDataFrame(geometry=[track], crs=CRS_WGS84)
    gdf_track_utm = gdf_track.to_crs(CRS_UTM30N)

    # Simplificamos el track original geométrico ANTES de aplicar el .buffer()
    # para evitar "salchichones" inflados con miles de vértices geométricos
    track_simplified = gdf_track_utm.simplify(tolerance=50)

    gdf_buffer = gdf_track_utm.copy()
    gdf_buffer["geometry"] = track_simplified.buffer(buffer_meters, resolution=3)
    print(
        f"[Buffer] Buffer de {buffer_meters:.0f}m aplicado sobre track simplificado "
        f"(Area aprox: {gdf_buffer.geometry.area.iloc[0] / 1e6:.1f} km2)"
    )
    return gdf_buffer


def build_stations_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Convierte el DataFrame de gasolineras del MITECO a un GeoDataFrame
    proyectado en EPSG:25830 (UTM 30N) con índice espacial R-Tree.

    Mejora vs. monolito: usa gpd.points_from_xy() (vectorizado en C)
    en lugar de un list comprehension de Point() en Python.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame limpio con columnas 'Latitud' y 'Longitud (WGS84)' como float.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame en EPSG:25830 con índice espacial R-Tree.
    """
    geometry = gpd.points_from_xy(df["Longitud (WGS84)"], df["Latitud"])
    gdf_stations = gpd.GeoDataFrame(df.copy(), geometry=geometry, crs=CRS_WGS84)
    gdf_stations_utm = gdf_stations.to_crs(CRS_UTM30N)

    print(f"[Estaciones] GeoDataFrame en {CRS_UTM30N}: {len(gdf_stations_utm)} estaciones")
    print(f"[Estaciones] Índice espacial R-Tree: {gdf_stations_utm.sindex}")

    return gdf_stations_utm


def spatial_join_within_buffer(
    gdf_stations: gpd.GeoDataFrame,
    gdf_buffer: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Realiza un Spatial Join (intersección) para filtrar las gasolineras que
    caen dentro del polígono del buffer de la ruta.

    GeoPandas usa internamente el índice R-Tree para pre-filtrar candidatos
    antes de la comprobación geométrica exacta (within).

    Parameters
    ----------
    gdf_stations : gpd.GeoDataFrame
        Gasolineras en EPSG:25830.
    gdf_buffer : gpd.GeoDataFrame
        Buffer de la ruta en EPSG:25830.

    Returns
    -------
    gpd.GeoDataFrame
        Subconjunto de gasolineras dentro del buffer.
    """
    assert gdf_stations.crs == gdf_buffer.crs, (
        f"CRS mismatch: estaciones={gdf_stations.crs}, buffer={gdf_buffer.crs}"
    )

    gdf_joined = gpd.sjoin(
        gdf_stations,
        gdf_buffer[["geometry"]],
        how="inner",
        predicate="within",
    )
    gdf_joined = gdf_joined.drop_duplicates(subset=["geometry"])
    print(f"[SpatialJoin] Gasolineras dentro del buffer: {len(gdf_joined)}")
    return gdf_joined
