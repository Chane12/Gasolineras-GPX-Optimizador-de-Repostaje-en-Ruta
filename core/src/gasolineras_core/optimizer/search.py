"""
gasolineras_core.optimizer.search
=================================
Full station search along a route: corridor → filters → cheapest (+ per segment) → España Vaciada →
autonomy radar. Same steps as the Streamlit app, as a single UI-free function used by the API.

Distance along the route (``km_ruta``) is computed one way only (``route_positions_km``): the position
of each station projected on the original track in UTM, scaled to the track's geodesic length. That is
the same total the autonomy radar uses, so station positions and radar segments are consistent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import shapely
from shapely.geometry import LineString

from gasolineras_core.config import ALL_ON_ROUTE_BUFFER_M, CRS_UTM30N, CRS_WGS84
from gasolineras_core.ingestion.gpx_parser import simplify_track
from gasolineras_core.optimizer.autonomy import calculate_autonomy_radar
from gasolineras_core.optimizer.cheapest import filter_all_stations_on_route, filter_cheapest_stations
from gasolineras_core.spatial.engine import build_route_buffer, spatial_join_within_buffer

logger = logging.getLogger(__name__)

_GEOD = pyproj.Geod(ellps="WGS84")


@dataclass(frozen=True)
class SearchParams:
    fuel_column: str
    buffer_m: float = 5000.0
    top_n: int = 5
    segment_km: float = 50.0  # 0 = no "cheapest per segment"
    only_24h: bool = False
    include_all_on_route: bool = False  # Modo España Vaciada
    autonomy_km: float = 0.0  # 0 = no autonomy radar


@dataclass(frozen=True)
class SearchResult:
    stations: gpd.GeoDataFrame  # selected stations (EPSG:25830) with precio_seleccionado and km_ruta, by km_ruta
    corridor_count: int  # stations in the corridor (after the 24h filter), with or without this fuel
    max_price_in_corridor: float | None  # most expensive price of this fuel in the corridor (for "savings")
    route_km: float  # geodesic length of the original track
    radar: list[dict] | None  # autonomy segments (calculate_autonomy_radar), None if autonomy_km == 0


def route_length_km(track: LineString) -> float:
    """Geodesic length (WGS84 ellipsoid) of a track in EPSG:4326."""
    return _GEOD.geometry_length(track) / 1000.0


def route_positions_km(track: LineString, stations_utm: gpd.GeoSeries, total_km: float | None = None) -> np.ndarray:
    """Km along the route of each station: projection on the UTM track, scaled to the geodesic length."""
    if stations_utm.empty:
        return np.array([], dtype="float64")
    track_utm = gpd.GeoSeries([track], crs=CRS_WGS84).to_crs(CRS_UTM30N).iloc[0]
    fractions = shapely.line_locate_point(track_utm, stations_utm.values, normalized=True)
    return np.asarray(fractions, dtype="float64") * (total_km if total_km is not None else route_length_km(track))


def _numeric(series: pd.Series) -> pd.Series:
    return pd.Series(pd.to_numeric(series, errors="coerce"), index=series.index, dtype="float64")


def _open_24h(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    if "Horario" not in gdf.columns:
        return gdf.iloc[0:0]
    return gpd.GeoDataFrame(gdf[gdf["Horario"].str.contains("24H|24 H", case=False, na=False)], crs=gdf.crs)


def _with_km(gdf: gpd.GeoDataFrame, track: LineString, total_km: float) -> gpd.GeoDataFrame:
    gdf = gdf.copy()
    gdf["km_ruta"] = route_positions_km(track, gdf.geometry, total_km)
    return gpd.GeoDataFrame(gdf.sort_values("km_ruta").reset_index(drop=True), crs=gdf.crs)


def search_stations(stations: gpd.GeoDataFrame, track: LineString, params: SearchParams) -> SearchResult:
    """
    Searches fuel stations along ``track`` (EPSG:4326, already validated) in the ``stations`` catalogue
    (``build_stations_geodataframe``, EPSG:25830).
    """
    fuel = params.fuel_column
    total_km = route_length_km(track)
    track_simp = simplify_track(track, tolerance_deg=0.0005)
    track_simp_utm = gpd.GeoSeries([track_simp], crs=CRS_WGS84).to_crs(CRS_UTM30N).iloc[0]

    within = spatial_join_within_buffer(stations, build_route_buffer(track_simp, buffer_meters=params.buffer_m))
    if params.only_24h:
        within = _open_24h(within)

    prices = _numeric(pd.Series(within[fuel])) if fuel in within.columns else pd.Series(dtype="float64")
    has_fuel = prices.notna() & (prices > 0)

    if has_fuel.any():
        top = filter_cheapest_stations(
            within, fuel_column=fuel, top_n=params.top_n, track_utm=track_simp_utm, segment_km=params.segment_km
        )
    else:
        top = within.iloc[0:0].copy()

    if params.include_all_on_route:
        narrow = spatial_join_within_buffer(
            stations, build_route_buffer(track_simp, buffer_meters=ALL_ON_ROUTE_BUFFER_M)
        )
        if params.only_24h:
            narrow = _open_24h(narrow)
        on_route = filter_all_stations_on_route(narrow, fuel_column=fuel, track_utm=track_simp_utm)
        if not on_route.empty:
            parts = [df for df in (top, on_route) if not df.empty]
            merged = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["geometry"])
            top = gpd.GeoDataFrame(merged, crs=on_route.crs)

    top = _with_km(top, track, total_km) if not top.empty else top

    radar = None
    if params.autonomy_km > 0:
        # The radar uses every corridor station that sells this fuel, not only the selected ones.
        survival = gpd.GeoDataFrame(within.loc[has_fuel], crs=within.crs)
        survival = _with_km(survival, track, total_km) if not survival.empty else survival
        radar, _ = calculate_autonomy_radar(track, survival, params.autonomy_km)

    max_price = float(prices[has_fuel].max()) if has_fuel.any() else None
    logger.info("Search: %d selected of %d in corridor (fuel=%s)", len(top), len(within), fuel)
    return SearchResult(
        stations=top,
        corridor_count=len(within),
        max_price_in_corridor=max_price,
        route_km=total_km,
        radar=radar,
    )
