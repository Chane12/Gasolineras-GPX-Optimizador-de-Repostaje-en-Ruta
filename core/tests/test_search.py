"""Tests for the full search pipeline (no network: synthetic stations along the Ávila–Segovia fixture)."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString

from gasolineras_core.config import CRS_UTM30N, CRS_WGS84, FUEL_TYPES
from gasolineras_core.optimizer.cheapest import filter_cheapest_stations
from gasolineras_core.optimizer.search import (
    SearchParams,
    route_length_km,
    route_positions_km,
    search_stations,
)
from gasolineras_core.spatial.engine import build_route_buffer, build_stations_geodataframe, spatial_join_within_buffer

DIESEL = FUEL_TYPES["diesel"][1]


@pytest.fixture
def stations(fake_stations_df: pd.DataFrame) -> gpd.GeoDataFrame:
    return build_stations_geodataframe(fake_stations_df)


def test_fuel_types_point_to_real_miteco_columns():
    from gasolineras_core.config import PRICE_COLUMNS

    assert {column for _label, column in FUEL_TYPES.values()} <= set(PRICE_COLUMNS)


def test_selects_the_same_stations_as_the_streamlit_pipeline(sample_track, stations):
    """Same steps as legacy/streamlit/app.py: buffer on the simplified track → cheapest top-N."""
    from gasolineras_core.ingestion.gpx_parser import simplify_track

    track_simp = simplify_track(sample_track, tolerance_deg=0.0005)
    within = spatial_join_within_buffer(stations, build_route_buffer(track_simp, buffer_meters=10_000))
    track_utm = gpd.GeoSeries([track_simp], crs=CRS_WGS84).to_crs(CRS_UTM30N).iloc[0]
    expected = filter_cheapest_stations(within, fuel_column=DIESEL, top_n=2, track_utm=track_utm, segment_km=10)

    result = search_stations(stations, sample_track, SearchParams(DIESEL, buffer_m=10_000, top_n=2, segment_km=10))

    assert set(result.stations["Rótulo"]) == set(expected["Rótulo"])
    assert result.corridor_count == len(within)
    assert result.max_price_in_corridor == pytest.approx(float(within[DIESEL].max()))


def test_stations_are_ordered_by_km_within_the_route(sample_track, stations):
    result = search_stations(stations, sample_track, SearchParams(DIESEL, buffer_m=10_000, top_n=5, segment_km=0))

    km = result.stations["km_ruta"].tolist()
    assert km == sorted(km)
    assert all(0 <= k <= result.route_km + 1e-6 for k in km)
    assert (result.stations["precio_seleccionado"] > 0).all()


def test_route_positions_use_the_geodesic_length(sample_track):
    end = gpd.GeoSeries.from_xy([sample_track.coords[-1][0]], [sample_track.coords[-1][1]], crs=CRS_WGS84)
    start = gpd.GeoSeries.from_xy([sample_track.coords[0][0]], [sample_track.coords[0][1]], crs=CRS_WGS84)

    total = route_length_km(sample_track)
    positions = route_positions_km(sample_track, pd.concat([start, end]).to_crs(CRS_UTM30N))

    assert positions[0] == pytest.approx(0.0, abs=1e-6)
    assert positions[1] == pytest.approx(total)


def test_only_24h_filters_by_schedule(sample_track, fake_stations_df):
    fake_stations_df.loc[fake_stations_df["Rótulo"] == "Cepsa N-110", "Horario"] = "L-V: 07:00-22:00"
    gdf = build_stations_geodataframe(fake_stations_df)

    result = search_stations(gdf, sample_track, SearchParams(DIESEL, buffer_m=10_000, top_n=5, only_24h=True))

    assert "Cepsa N-110" not in set(result.stations["Rótulo"])
    assert result.corridor_count == 4


def test_fuel_not_sold_anywhere_returns_no_stations(sample_track, stations):
    result = search_stations(stations, sample_track, SearchParams(FUEL_TYPES["hidrogeno"][1], buffer_m=10_000))

    assert result.stations.empty
    assert result.max_price_in_corridor is None
    assert result.corridor_count > 0


def test_all_on_route_adds_stations_on_the_road_even_if_not_cheapest(sample_track, stations):
    base = search_stations(stations, sample_track, SearchParams(DIESEL, buffer_m=10_000, top_n=1, segment_km=0))
    on_route = search_stations(
        stations,
        sample_track,
        SearchParams(DIESEL, buffer_m=10_000, top_n=1, segment_km=0, include_all_on_route=True),
    )

    assert len(on_route.stations) >= len(base.stations)
    assert on_route.stations["geometry"].is_unique


def test_radar_only_when_autonomy_is_given(sample_track, stations):
    without = search_stations(stations, sample_track, SearchParams(DIESEL, buffer_m=10_000))
    with_radar = search_stations(stations, sample_track, SearchParams(DIESEL, buffer_m=10_000, autonomy_km=20))

    assert without.radar is None
    assert with_radar.radar is not None
    assert with_radar.radar[0]["km_inicio"] == 0.0
    assert with_radar.radar[-1]["km_fin"] == pytest.approx(with_radar.route_km)
    # Segments cover the whole route without gaps
    for prev, nxt in zip(with_radar.radar, with_radar.radar[1:], strict=False):
        assert prev["km_fin"] == pytest.approx(nxt["km_inicio"])


def test_radar_flags_gaps_longer_than_the_autonomy(stations):
    long_empty_track = LineString([(-6.0, 39.0), (-5.0, 39.0)])  # ~86 km with no stations
    result = search_stations(stations, long_empty_track, SearchParams(DIESEL, autonomy_km=50))

    assert result.stations.empty
    assert [s["nivel"] for s in result.radar or []] == ["critico"]
