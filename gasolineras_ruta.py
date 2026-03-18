"""
gasolineras_ruta.py — COMPATIBILITY SHIM
=========================================
Re-exports all public API from the new src/ modular package.

This file exists so that:
  1. app.py keeps working without import changes (until migrated)
  2. tests/test_regression_monolith.py keeps passing

After all consumers have migrated to ``from src.…``, this file can be deleted.
"""

# fmt: off
# ruff: noqa: F401, E402, I001

# --- Config ---
from src.config import (
    CRS_WGS84,
    CRS_UTM30N,
    PRICE_COLUMNS,
    COORD_COLUMNS,
    BBOX_SPAIN          as _BBOX_SPAIN,
    MAX_TRACK_POINTS    as _MAX_TRACK_POINTS,
    OSRM_BASE_URL       as _OSRM_BASE_URL,
    NOMINATIM_URL       as _NOMINATIM_URL,
    NOMINATIM_HEADERS   as _NOMINATIM_HEADERS,
    GMAPS_MAX_WAYPOINTS as _GMAPS_MAX_WAYPOINTS,
    PROJECT_ROOT,
)

# --- Ingestion ---
from src.ingestion.miteco import fetch_gasolineras
from src.ingestion.gpx_parser import load_gpx_track, validate_gpx_track, simplify_track
from src.ingestion.geocoder import get_route_from_text, RouteTextError

# --- Spatial ---
from src.spatial.engine import (
    build_route_buffer,
    build_stations_geodataframe,
    spatial_join_within_buffer,
)

# --- Optimizer ---
from src.optimizer.cheapest import filter_cheapest_stations, filter_all_stations_on_route
from src.optimizer.autonomy import calculate_autonomy_radar
from src.optimizer.export import (
    prepare_export_gdf,
    generate_google_maps_url,
    get_real_distance_osrm,
    enrich_stations_with_osrm,
    enrich_gpx_with_stops,
)

# --- Visualization ---
from src.visualization.folium_map import generate_map

# --- Pipeline (kept for backward compat with __main__ block) ---

def run_pipeline(
    gpx_path,
    fuel_column="Precio Gasoleo A",
    buffer_meters=5000.0,
    top_n=5,
    simplify_tolerance=0.0005,
    output_html=None,
    segment_km=0.0,
):
    """Legacy pipeline wrapper — delegates to src/ modules."""
    import geopandas as gpd

    print("=" * 60)
    print(" OPTIMIZADOR DE GASOLINERAS EN RUTA -- Espana")
    print("=" * 60)

    df_gasolineras = fetch_gasolineras()
    track_original = load_gpx_track(gpx_path)
    track_simplified = simplify_track(track_original, tolerance_deg=simplify_tolerance)
    gdf_buffer = build_route_buffer(track_simplified, buffer_meters=buffer_meters)
    gdf_stations_utm = build_stations_geodataframe(df_gasolineras)
    gdf_within = spatial_join_within_buffer(gdf_stations_utm, gdf_buffer)

    gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simplified], crs=CRS_WGS84).to_crs(CRS_UTM30N)
    track_utm = gdf_track_utm.geometry.iloc[0]

    gdf_top = filter_cheapest_stations(
        gdf_within,
        fuel_column=fuel_column,
        top_n=top_n,
        track_utm=track_utm,
        segment_km=segment_km,
    )

    ruta_html = None
    mapa_obj = None
    if not gdf_top.empty:
        ruta_html, mapa_obj = generate_map(
            track_original=track_original,
            gdf_top_stations=gdf_top,
            fuel_column=fuel_column,
            output_path=output_html,
            gdf_all_stations=gdf_within,
        )

    return {
        "track_original": track_original,
        "track_simplified": track_simplified,
        "gdf_buffer": gdf_buffer,
        "gdf_stations_utm": gdf_stations_utm,
        "gdf_within_buffer": gdf_within,
        "gdf_top_n": gdf_top,
        "output_html": ruta_html,
        "mapa_obj": mapa_obj,
    }

# fmt: on
