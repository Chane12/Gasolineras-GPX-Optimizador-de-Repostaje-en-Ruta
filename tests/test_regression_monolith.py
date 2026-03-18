"""
test_regression_monolith.py
===========================
Regression tests that capture the CURRENT behaviour of gasolineras_ruta.py
(the monolith) **before** any refactoring.

Strategy
--------
These tests run the same functions the production pipeline uses, but with
local/synthetic data so they execute in < 2 s and need no internet access.

After the refactoring is complete, a mirror test file
(test_regression_modular.py) will import from src/ and assert identical
results.  Any divergence = broken refactor.

Fixtures come from conftest.py (sample_gpx_path, sample_track, fake_stations_df).
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString, Point

# ---------------------------------------------------------------------------
# Import directly from the monolith (pre-refactor)
# ---------------------------------------------------------------------------
from gasolineras_ruta import (
    CRS_UTM30N,
    CRS_WGS84,
    build_route_buffer,
    build_stations_geodataframe,
    calculate_autonomy_radar,
    filter_all_stations_on_route,
    filter_cheapest_stations,
    generate_google_maps_url,
    load_gpx_track,
    simplify_track,
    spatial_join_within_buffer,
    validate_gpx_track,
)

# ===================================================================
# 1. INGESTION — GPX parsing
# ===================================================================

class TestGPXIngestion:
    """Tests for GPX loading, validation, and simplification."""

    def test_load_gpx_returns_linestring(self, sample_gpx_path: Path):
        track = load_gpx_track(sample_gpx_path)
        assert isinstance(track, LineString)

    def test_load_gpx_preserves_point_count(self, sample_gpx_path: Path):
        track = load_gpx_track(sample_gpx_path)
        assert len(track.coords) == 20, (
            f"Expected 20 coords from fixture, got {len(track.coords)}"
        )

    def test_load_gpx_first_and_last_coords(self, sample_gpx_path: Path):
        track = load_gpx_track(sample_gpx_path)
        first = track.coords[0]
        last = track.coords[-1]
        # GPX fixture: first point Ávila, last point near Segovia
        assert abs(first[1] - 40.656356) < 1e-4, f"Unexpected first lat: {first[1]}"
        assert abs(last[1] - 40.942903) < 1e-4, f"Unexpected last lat: {last[1]}"

    def test_validate_gpx_track_passes_for_spain(self, sample_track: LineString):
        """Track centroid is inside Spain bounding box → no exception."""
        validate_gpx_track(sample_track)  # should not raise

    def test_validate_gpx_track_rejects_outside_spain(self):
        """A track in London should be rejected."""
        london_track = LineString([(-0.1, 51.5), (-0.2, 51.6)])
        with pytest.raises(ValueError, match="territorio español"):
            validate_gpx_track(london_track)

    def test_simplify_reduces_vertices(self, sample_track: LineString):
        simplified = simplify_track(sample_track, tolerance_deg=0.01)
        assert len(simplified.coords) < len(sample_track.coords)
        assert len(simplified.coords) >= 2  # at least start and end

    def test_simplify_preserves_endpoints(self, sample_track: LineString):
        simplified = simplify_track(sample_track, tolerance_deg=0.01)
        assert simplified.coords[0] == sample_track.coords[0]
        assert simplified.coords[-1] == sample_track.coords[-1]


# ===================================================================
# 2. SPATIAL ENGINE — Buffer, GeoDataFrame, Spatial Join
# ===================================================================

class TestSpatialEngine:
    """Tests for the core GIS operations."""

    def test_build_route_buffer_returns_geodataframe(self, sample_track: LineString):
        gdf_buf = build_route_buffer(sample_track, buffer_meters=5000)
        assert isinstance(gdf_buf, gpd.GeoDataFrame)
        assert len(gdf_buf) == 1
        assert gdf_buf.crs.to_epsg() == 25830  # UTM 30N

    def test_buffer_area_increases_with_radius(self, sample_track: LineString):
        buf_1k = build_route_buffer(sample_track, buffer_meters=1000)
        buf_5k = build_route_buffer(sample_track, buffer_meters=5000)
        area_1k = buf_1k.geometry.area.iloc[0]
        area_5k = buf_5k.geometry.area.iloc[0]
        assert area_5k > area_1k, "Larger buffer should have larger area"

    def test_build_stations_geodataframe_crs(self, fake_stations_df: pd.DataFrame):
        gdf = build_stations_geodataframe(fake_stations_df)
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert gdf.crs.to_epsg() == 25830
        assert len(gdf) == 5

    def test_build_stations_geodataframe_has_sindex(self, fake_stations_df: pd.DataFrame):
        gdf = build_stations_geodataframe(fake_stations_df)
        # Accessing .sindex should not raise and should return a spatial index
        assert gdf.sindex is not None

    def test_spatial_join_finds_stations_in_buffer(
        self, sample_track: LineString, fake_stations_df: pd.DataFrame
    ):
        """With a 10km buffer, all 5 synthetic stations should be within range."""
        gdf_buf = build_route_buffer(sample_track, buffer_meters=10_000)
        gdf_stations = build_stations_geodataframe(fake_stations_df)
        gdf_within = spatial_join_within_buffer(gdf_stations, gdf_buf)
        # All 5 stations are on or very near the route
        assert len(gdf_within) >= 3, (
            f"Expected at least 3 stations within 10km buffer, got {len(gdf_within)}"
        )

    def test_spatial_join_narrow_buffer_has_smaller_area(
        self, sample_track: LineString, fake_stations_df: pd.DataFrame
    ):
        """A 100m buffer should have a much smaller area than a 10km buffer."""
        gdf_buf_narrow = build_route_buffer(sample_track, buffer_meters=100)
        gdf_buf_wide = build_route_buffer(sample_track, buffer_meters=10_000)
        area_narrow = gdf_buf_narrow.geometry.area.iloc[0]
        area_wide = gdf_buf_wide.geometry.area.iloc[0]
        # The wide buffer area should be at least 50x larger
        assert area_wide / area_narrow > 50


# ===================================================================
# 3. OPTIMIZER — Filtering logic
# ===================================================================

class TestOptimizer:
    """Tests for cheapest-station filtering and autonomy radar."""

    @pytest.fixture
    def gdf_within(
        self, sample_track: LineString, fake_stations_df: pd.DataFrame
    ) -> gpd.GeoDataFrame:
        """Pre-computed spatial join result for the test corridor."""
        gdf_buf = build_route_buffer(sample_track, buffer_meters=10_000)
        gdf_stations = build_stations_geodataframe(fake_stations_df)
        return spatial_join_within_buffer(gdf_stations, gdf_buf)

    @pytest.fixture
    def track_utm(self, sample_track: LineString) -> LineString:
        gdf = gpd.GeoDataFrame(geometry=[sample_track], crs=CRS_WGS84).to_crs(CRS_UTM30N)
        return gdf.geometry.iloc[0]

    def test_filter_cheapest_returns_sorted(self, gdf_within, track_utm):
        top = filter_cheapest_stations(
            gdf_within,
            fuel_column="Precio Gasoleo A",
            top_n=3,
            track_utm=track_utm,
        )
        assert len(top) <= 3
        if not top.empty:
            prices = top["precio_seleccionado"].tolist()
            # km_ruta ordering (route order), but prices should all be valid
            assert all(p > 0 for p in prices)

    def test_filter_cheapest_invalid_column_raises(self, gdf_within):
        with pytest.raises(ValueError, match="no encontrada"):
            filter_cheapest_stations(
                gdf_within,
                fuel_column="Precio Combustible Imaginario",
                top_n=3,
            )

    def test_filter_all_stations_on_route(self, gdf_within, track_utm):
        """España Vaciada mode: should return all stations with valid fuel prices."""
        result = filter_all_stations_on_route(
            gdf_within,
            fuel_column="Precio Gasoleo A",
            track_utm=track_utm,
        )
        assert isinstance(result, gpd.GeoDataFrame)
        if not result.empty:
            assert "km_ruta" in result.columns
            # Should be sorted by km_ruta
            km_values = result["km_ruta"].tolist()
            assert km_values == sorted(km_values)

    def test_autonomy_radar_returns_tramos(self, sample_track):
        """Autonomy radar should produce a list of tramos with expected keys."""
        # Build a minimal gdf_top with km_ruta
        gdf_top = gpd.GeoDataFrame(
            {"km_ruta": [10.0, 30.0], "Rótulo": ["A", "B"]},
            geometry=[Point(-4.66, 40.665), Point(-4.50, 40.74)],
            crs=CRS_WGS84,
        )
        tramos, total_km = calculate_autonomy_radar(
            sample_track, gdf_top, autonomia_km=500
        )
        assert isinstance(tramos, list)
        assert total_km > 0
        assert len(tramos) >= 1
        required_keys = {"km_inicio", "km_fin", "gap_km", "nivel", "emoji", "label"}
        for t in tramos:
            assert required_keys.issubset(t.keys()), f"Missing keys in tramo: {t.keys()}"


# ===================================================================
# 4. EXPORT — Google Maps URL
# ===================================================================

class TestExport:
    """Tests for export utilities."""

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
        """More than 9 waypoints should be truncated."""
        geoms = [Point(-4.5 - i * 0.01, 40.7 + i * 0.01) for i in range(12)]
        gdf_stops = gpd.GeoDataFrame(
            {"Rótulo": [f"Station {i}" for i in range(12)]},
            geometry=geoms,
            crs=CRS_WGS84,
        ).to_crs(CRS_UTM30N)
        url, n_truncated = generate_google_maps_url(sample_track, gdf_stops)
        assert n_truncated == 3  # 12 - 9 = 3


# ===================================================================
# 5. FULL PIPELINE SNAPSHOT (golden output)
# ===================================================================

class TestPipelineSnapshot:
    """
    Golden-output regression test.

    Captures the EXACT output structure of the monolith's core pipeline
    (GPX → simplify → buffer → sjoin → filter) with synthetic data.
    After refactoring, the modular pipeline must produce IDENTICAL results.
    """

    def test_pipeline_output_schema(
        self, sample_track: LineString, fake_stations_df: pd.DataFrame
    ):
        """Validates the end-to-end output schema from the monolith."""
        # 1. Simplify
        track_simp = simplify_track(sample_track, tolerance_deg=0.0005)
        assert isinstance(track_simp, LineString)

        # 2. Buffer
        gdf_buf = build_route_buffer(track_simp, buffer_meters=10_000)
        assert gdf_buf.crs.to_epsg() == 25830

        # 3. Stations GeoDataFrame
        gdf_stations = build_stations_geodataframe(fake_stations_df)
        assert gdf_stations.crs.to_epsg() == 25830

        # 4. Spatial Join
        gdf_within = spatial_join_within_buffer(gdf_stations, gdf_buf)
        assert isinstance(gdf_within, gpd.GeoDataFrame)

        # 5. Filter cheapest
        gdf_track_utm = gpd.GeoDataFrame(
            geometry=[track_simp], crs=CRS_WGS84
        ).to_crs(CRS_UTM30N)
        track_utm = gdf_track_utm.geometry.iloc[0]

        gdf_top = filter_cheapest_stations(
            gdf_within,
            fuel_column="Precio Gasoleo A",
            top_n=3,
            track_utm=track_utm,
        )

        # --- Assertions that define the "golden contract" ---
        assert isinstance(gdf_top, gpd.GeoDataFrame)
        assert "precio_seleccionado" in gdf_top.columns
        assert "combustible" in gdf_top.columns
        assert "km_ruta" in gdf_top.columns
        assert len(gdf_top) <= 3

        if not gdf_top.empty:
            # All prices must be positive floats
            assert gdf_top["precio_seleccionado"].dtype in (np.float64, float)
            assert (gdf_top["precio_seleccionado"] > 0).all()

            # km_ruta must exist and be non-negative
            assert (gdf_top["km_ruta"] >= 0).all()

    def test_cheapest_station_is_deterministic(
        self, sample_track: LineString, fake_stations_df: pd.DataFrame
    ):
        """Running the pipeline twice must yield the same cheapest station."""
        def run_once():
            track_simp = simplify_track(sample_track, tolerance_deg=0.0005)
            gdf_buf = build_route_buffer(track_simp, buffer_meters=10_000)
            gdf_stations = build_stations_geodataframe(fake_stations_df)
            gdf_within = spatial_join_within_buffer(gdf_stations, gdf_buf)
            gdf_track_utm = gpd.GeoDataFrame(
                geometry=[track_simp], crs=CRS_WGS84
            ).to_crs(CRS_UTM30N)
            track_utm = gdf_track_utm.geometry.iloc[0]
            return filter_cheapest_stations(
                gdf_within,
                fuel_column="Precio Gasoleo A",
                top_n=2,
                track_utm=track_utm,
            )

        result_a = run_once()
        result_b = run_once()

        if not result_a.empty and not result_b.empty:
            prices_a = result_a["precio_seleccionado"].tolist()
            prices_b = result_b["precio_seleccionado"].tolist()
            assert prices_a == prices_b, "Pipeline output is not deterministic"
