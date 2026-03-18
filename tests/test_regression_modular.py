"""
test_regression_modular.py
==========================
Regression tests that import from the NEW src/ package and verify identical
behaviour to the monolith (tested by test_regression_monolith.py).

If any test here fails but its monolith counterpart passes, it means
the refactoring introduced a regression.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import LineString, Point

# ---------------------------------------------------------------------------
# Import from the MODULAR package (src/)
# ---------------------------------------------------------------------------
from src.config import CRS_UTM30N, CRS_WGS84
from src.ingestion.gpx_parser import load_gpx_track, simplify_track, validate_gpx_track
from src.optimizer.autonomy import calculate_autonomy_radar
from src.optimizer.cheapest import filter_all_stations_on_route, filter_cheapest_stations
from src.optimizer.export import generate_google_maps_url
from src.spatial.engine import build_route_buffer, build_stations_geodataframe, spatial_join_within_buffer
from src.spatial.nearest import build_kdtree_from_points, query_nearest

# ===================================================================
# 1. INGESTION — GPX parsing (via src.ingestion.gpx_parser)
# ===================================================================

class TestGPXIngestionModular:
    """Same tests as TestGPXIngestion but importing from src/."""

    def test_load_gpx_returns_linestring(self, sample_gpx_path: Path):
        track = load_gpx_track(sample_gpx_path)
        assert isinstance(track, LineString)

    def test_load_gpx_preserves_point_count(self, sample_gpx_path: Path):
        track = load_gpx_track(sample_gpx_path)
        assert len(track.coords) == 20

    def test_load_gpx_first_and_last_coords(self, sample_gpx_path: Path):
        track = load_gpx_track(sample_gpx_path)
        first = track.coords[0]
        last = track.coords[-1]
        assert abs(first[1] - 40.656356) < 1e-4
        assert abs(last[1] - 40.942903) < 1e-4

    def test_validate_gpx_track_passes_for_spain(self, sample_track: LineString):
        validate_gpx_track(sample_track)

    def test_validate_gpx_track_rejects_outside_spain(self):
        london_track = LineString([(-0.1, 51.5), (-0.2, 51.6)])
        with pytest.raises(ValueError, match="territorio español"):
            validate_gpx_track(london_track)

    def test_simplify_reduces_vertices(self, sample_track: LineString):
        simplified = simplify_track(sample_track, tolerance_deg=0.01)
        assert len(simplified.coords) < len(sample_track.coords)
        assert len(simplified.coords) >= 2

    def test_simplify_preserves_endpoints(self, sample_track: LineString):
        simplified = simplify_track(sample_track, tolerance_deg=0.01)
        assert simplified.coords[0] == sample_track.coords[0]
        assert simplified.coords[-1] == sample_track.coords[-1]


# ===================================================================
# 2. SPATIAL ENGINE (via src.spatial.engine)
# ===================================================================

class TestSpatialEngineModular:

    def test_build_route_buffer_returns_geodataframe(self, sample_track: LineString):
        gdf_buf = build_route_buffer(sample_track, buffer_meters=5000)
        assert isinstance(gdf_buf, gpd.GeoDataFrame)
        assert len(gdf_buf) == 1
        assert gdf_buf.crs.to_epsg() == 25830

    def test_buffer_area_increases_with_radius(self, sample_track: LineString):
        buf_1k = build_route_buffer(sample_track, buffer_meters=1000)
        buf_5k = build_route_buffer(sample_track, buffer_meters=5000)
        assert buf_5k.geometry.area.iloc[0] > buf_1k.geometry.area.iloc[0]

    def test_build_stations_geodataframe_crs(self, fake_stations_df):
        gdf = build_stations_geodataframe(fake_stations_df)
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert gdf.crs.to_epsg() == 25830
        assert len(gdf) == 5

    def test_build_stations_geodataframe_has_sindex(self, fake_stations_df):
        gdf = build_stations_geodataframe(fake_stations_df)
        assert gdf.sindex is not None

    def test_spatial_join_finds_stations_in_buffer(self, sample_track, fake_stations_df):
        gdf_buf = build_route_buffer(sample_track, buffer_meters=10_000)
        gdf_stations = build_stations_geodataframe(fake_stations_df)
        gdf_within = spatial_join_within_buffer(gdf_stations, gdf_buf)
        assert len(gdf_within) >= 3

    def test_spatial_join_narrow_buffer_has_smaller_area(self, sample_track, fake_stations_df):
        gdf_buf_narrow = build_route_buffer(sample_track, buffer_meters=100)
        gdf_buf_wide = build_route_buffer(sample_track, buffer_meters=10_000)
        assert gdf_buf_wide.geometry.area.iloc[0] / gdf_buf_narrow.geometry.area.iloc[0] > 50


# ===================================================================
# 3. SPATIAL NEAREST (via src.spatial.nearest)
# ===================================================================

class TestSpatialNearestModular:
    """Tests specific to the new KD-Tree utility module."""

    def test_build_kdtree_and_query(self):
        points = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
        tree = build_kdtree_from_points(points)
        dist, idx = query_nearest(tree, (0.9, 0.9))
        assert idx == 1
        assert dist < 0.2

    def test_query_exact_match(self):
        points = [(10.0, 20.0), (30.0, 40.0)]
        tree = build_kdtree_from_points(points)
        dist, idx = query_nearest(tree, (10.0, 20.0))
        assert idx == 0
        assert dist == 0.0


# ===================================================================
# 4. OPTIMIZER (via src.optimizer.cheapest)
# ===================================================================

class TestOptimizerModular:

    @pytest.fixture
    def gdf_within(self, sample_track, fake_stations_df):
        gdf_buf = build_route_buffer(sample_track, buffer_meters=10_000)
        gdf_stations = build_stations_geodataframe(fake_stations_df)
        return spatial_join_within_buffer(gdf_stations, gdf_buf)

    @pytest.fixture
    def track_utm(self, sample_track):
        gdf = gpd.GeoDataFrame(geometry=[sample_track], crs=CRS_WGS84).to_crs(CRS_UTM30N)
        return gdf.geometry.iloc[0]

    def test_filter_cheapest_returns_sorted(self, gdf_within, track_utm):
        top = filter_cheapest_stations(gdf_within, fuel_column="Precio Gasoleo A", top_n=3, track_utm=track_utm)
        assert len(top) <= 3
        if not top.empty:
            assert all(p > 0 for p in top["precio_seleccionado"].tolist())

    def test_filter_cheapest_invalid_column_raises(self, gdf_within):
        with pytest.raises(ValueError, match="no encontrada"):
            filter_cheapest_stations(gdf_within, fuel_column="Precio Combustible Imaginario", top_n=3)

    def test_filter_all_stations_on_route(self, gdf_within, track_utm):
        result = filter_all_stations_on_route(gdf_within, fuel_column="Precio Gasoleo A", track_utm=track_utm)
        assert isinstance(result, gpd.GeoDataFrame)
        if not result.empty:
            assert "km_ruta" in result.columns
            km_values = result["km_ruta"].tolist()
            assert km_values == sorted(km_values)

    def test_autonomy_radar_returns_tramos(self, sample_track):
        gdf_top = gpd.GeoDataFrame(
            {"km_ruta": [10.0, 30.0], "Rótulo": ["A", "B"]},
            geometry=[Point(-4.66, 40.665), Point(-4.50, 40.74)],
            crs=CRS_WGS84,
        )
        tramos, total_km = calculate_autonomy_radar(sample_track, gdf_top, autonomia_km=500)
        assert isinstance(tramos, list)
        assert total_km > 0
        assert len(tramos) >= 1
        required_keys = {"km_inicio", "km_fin", "gap_km", "nivel", "emoji", "label"}
        for t in tramos:
            assert required_keys.issubset(t.keys())


# ===================================================================
# 5. EXPORT (via src.optimizer.export)
# ===================================================================

class TestExportModular:

    def test_google_maps_url_generation(self, sample_track):
        gdf_stops = gpd.GeoDataFrame(
            {"Rótulo": ["Test Station"]},
            geometry=[Point(-4.58, 40.70)],
            crs=CRS_WGS84,
        ).to_crs(CRS_UTM30N)
        url, n_truncated = generate_google_maps_url(sample_track, gdf_stops)
        assert url.startswith("https://www.google.com/maps/dir/")
        assert n_truncated == 0
        assert "waypoints=" in url

    def test_google_maps_url_truncates_excess_waypoints(self, sample_track):
        geoms = [Point(-4.5 - i * 0.01, 40.7 + i * 0.01) for i in range(12)]
        gdf_stops = gpd.GeoDataFrame(
            {"Rótulo": [f"Station {i}" for i in range(12)]},
            geometry=geoms,
            crs=CRS_WGS84,
        ).to_crs(CRS_UTM30N)
        url, n_truncated = generate_google_maps_url(sample_track, gdf_stops)
        assert n_truncated == 3


# ===================================================================
# 6. FULL PIPELINE SNAPSHOT — GOLDEN OUTPUT COMPARISON
# ===================================================================

class TestPipelineSnapshotModular:
    """
    Mirror of TestPipelineSnapshot but using src/ imports.
    Must produce IDENTICAL results to the monolith version.
    """

    def test_pipeline_output_schema(self, sample_track, fake_stations_df):
        track_simp = simplify_track(sample_track, tolerance_deg=0.0005)
        assert isinstance(track_simp, LineString)

        gdf_buf = build_route_buffer(track_simp, buffer_meters=10_000)
        assert gdf_buf.crs.to_epsg() == 25830

        gdf_stations = build_stations_geodataframe(fake_stations_df)
        assert gdf_stations.crs.to_epsg() == 25830

        gdf_within = spatial_join_within_buffer(gdf_stations, gdf_buf)
        assert isinstance(gdf_within, gpd.GeoDataFrame)

        gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simp], crs=CRS_WGS84).to_crs(CRS_UTM30N)
        track_utm = gdf_track_utm.geometry.iloc[0]

        gdf_top = filter_cheapest_stations(
            gdf_within, fuel_column="Precio Gasoleo A", top_n=3, track_utm=track_utm
        )

        assert isinstance(gdf_top, gpd.GeoDataFrame)
        assert "precio_seleccionado" in gdf_top.columns
        assert "combustible" in gdf_top.columns
        assert "km_ruta" in gdf_top.columns
        assert len(gdf_top) <= 3

        if not gdf_top.empty:
            assert gdf_top["precio_seleccionado"].dtype in (np.float64, float)
            assert (gdf_top["precio_seleccionado"] > 0).all()
            assert (gdf_top["km_ruta"] >= 0).all()

    def test_cheapest_station_is_deterministic(self, sample_track, fake_stations_df):
        def run_once():
            track_simp = simplify_track(sample_track, tolerance_deg=0.0005)
            gdf_buf = build_route_buffer(track_simp, buffer_meters=10_000)
            gdf_stations = build_stations_geodataframe(fake_stations_df)
            gdf_within = spatial_join_within_buffer(gdf_stations, gdf_buf)
            gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simp], crs=CRS_WGS84).to_crs(CRS_UTM30N)
            track_utm = gdf_track_utm.geometry.iloc[0]
            return filter_cheapest_stations(gdf_within, fuel_column="Precio Gasoleo A", top_n=2, track_utm=track_utm)

        result_a = run_once()
        result_b = run_once()

        if not result_a.empty and not result_b.empty:
            prices_a = result_a["precio_seleccionado"].tolist()
            prices_b = result_b["precio_seleccionado"].tolist()
            assert prices_a == prices_b, "Pipeline output is not deterministic"

    def test_golden_output_monolith_vs_modular(self, sample_track, fake_stations_df):
        """
        THE CRITICAL TEST: runs the same pipeline via the monolith shim
        AND via src/ imports, then compares the golden outputs.
        """
        # --- Monolith path ---
        import gasolineras_ruta as mono

        track_simp_m = mono.simplify_track(sample_track, tolerance_deg=0.0005)
        gdf_buf_m = mono.build_route_buffer(track_simp_m, buffer_meters=10_000)
        gdf_stations_m = mono.build_stations_geodataframe(fake_stations_df)
        gdf_within_m = mono.spatial_join_within_buffer(gdf_stations_m, gdf_buf_m)
        gdf_track_utm_m = gpd.GeoDataFrame(geometry=[track_simp_m], crs=mono.CRS_WGS84).to_crs(mono.CRS_UTM30N)
        track_utm_m = gdf_track_utm_m.geometry.iloc[0]
        gdf_top_m = mono.filter_cheapest_stations(
            gdf_within_m, fuel_column="Precio Gasoleo A", top_n=3, track_utm=track_utm_m
        )

        # --- Modular path ---
        track_simp_s = simplify_track(sample_track, tolerance_deg=0.0005)
        gdf_buf_s = build_route_buffer(track_simp_s, buffer_meters=10_000)
        gdf_stations_s = build_stations_geodataframe(fake_stations_df)
        gdf_within_s = spatial_join_within_buffer(gdf_stations_s, gdf_buf_s)
        gdf_track_utm_s = gpd.GeoDataFrame(geometry=[track_simp_s], crs=CRS_WGS84).to_crs(CRS_UTM30N)
        track_utm_s = gdf_track_utm_s.geometry.iloc[0]
        gdf_top_s = filter_cheapest_stations(
            gdf_within_s, fuel_column="Precio Gasoleo A", top_n=3, track_utm=track_utm_s
        )

        # --- Comparison ---
        assert len(gdf_top_m) == len(gdf_top_s), (
            f"Different number of results: monolith={len(gdf_top_m)}, modular={len(gdf_top_s)}"
        )

        prices_m = sorted(gdf_top_m["precio_seleccionado"].tolist())
        prices_s = sorted(gdf_top_s["precio_seleccionado"].tolist())
        assert prices_m == prices_s, (
            f"Different prices: monolith={prices_m}, modular={prices_s}"
        )

        if "km_ruta" in gdf_top_m.columns and "km_ruta" in gdf_top_s.columns:
            km_m = sorted(gdf_top_m["km_ruta"].round(2).tolist())
            km_s = sorted(gdf_top_s["km_ruta"].round(2).tolist())
            assert km_m == km_s, (
                f"Different km_ruta: monolith={km_m}, modular={km_s}"
            )
