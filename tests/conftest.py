"""
conftest.py — Shared fixtures for all tests.

Provides reusable test data that mirrors the production pipeline inputs
without hitting the network (except tests marked @pytest.mark.network).
"""

from pathlib import Path

import pandas as pd
import pytest
from shapely.geometry import LineString

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_GPX = FIXTURES_DIR / "sample_track.gpx"


@pytest.fixture
def sample_gpx_path() -> Path:
    """Path to the minimal 20-point GPX fixture (Ávila–Segovia)."""
    assert SAMPLE_GPX.exists(), f"Missing fixture: {SAMPLE_GPX}"
    return SAMPLE_GPX


@pytest.fixture
def sample_track() -> LineString:
    """LineString parsed from the sample GPX via the monolith."""
    from gasolineras_ruta import load_gpx_track

    return load_gpx_track(SAMPLE_GPX)


@pytest.fixture
def fake_stations_df() -> pd.DataFrame:
    """
    Synthetic MITECO-like DataFrame with 5 gas stations near the Ávila–Segovia
    corridor.  No network required.

    Columns match the real MITECO schema so that build_stations_geodataframe()
    and filter_cheapest_stations() work unmodified.
    """
    return pd.DataFrame(
        {
            "Latitud":             [40.665, 40.700, 40.740, 40.790, 40.820],
            "Longitud (WGS84)":    [-4.660, -4.580, -4.500, -4.400, -4.340],
            "Rótulo":              ["Repsol Ávila", "Cepsa N-110", "BP Villacastín",
                                    "Shell Segovia", "Galp Segovia"],
            "Municipio":           ["Ávila", "Mediana", "Villacastín", "Segovia", "Segovia"],
            "Provincia":           ["Ávila"] * 2 + ["Segovia"] * 3,
            "Dirección":           ["N-110 km 5", "N-110 km 15", "N-110 km 25",
                                    "N-110 km 35", "N-110 km 42"],
            "Horario":             ["L-D: 24H"] * 5,
            "Precio Gasoleo A":    [1.459, 1.389, 1.519, 1.399, 1.479],
            "Precio Gasolina 95 E5": [1.559, 1.499, 1.619, 1.509, 1.579],
            "C.P.":                ["05001", "05100", "40100", "40001", "40002"],
        }
    )
