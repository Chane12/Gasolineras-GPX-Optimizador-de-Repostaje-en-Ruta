"""
src/config.py
=============
Centralized configuration and constants for the Gasolineras en Ruta project.
All modules import shared constants from here — single source of truth.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Project root (resolved dynamically — never hardcoded)
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Coordinate Reference Systems
# ---------------------------------------------------------------------------
CRS_WGS84: str = "EPSG:4326"
CRS_UTM30N: str = "EPSG:25830"

# ---------------------------------------------------------------------------
# MITECO API
# ---------------------------------------------------------------------------
MITECO_API_URL: str = (
    "https://sedeaplicaciones.minetur.gob.es"
    "/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/"
)

PRICE_COLUMNS: list[str] = [
    "Precio Gasoleo A",
    "Precio Gasoleo B",
    "Precio Gasoleo Premium",
    "Precio Gasolina 95 E5",
    "Precio Gasolina 95 E10",
    "Precio Gasolina 95 E5 Premium",
    "Precio Gasolina 98 E5",
    "Precio Gasolina 98 E10",
    "Precio Bioetanol",
    "Precio Biodiesel",
    "Precio Gas Natural Comprimido",
    "Precio Gas Natural Licuado",
    "Precio Gases licuados del petroleo",
    "Precio Hidrogeno",
]

COORD_COLUMNS: list[str] = ["Latitud", "Longitud (WGS84)"]

# ---------------------------------------------------------------------------
# GPX validation
# ---------------------------------------------------------------------------
BBOX_SPAIN: dict[str, float] = {
    "min_lat": 27.6,
    "max_lat": 44.0,
    "min_lon": -18.2,
    "max_lon": 4.3,
}
MAX_TRACK_POINTS: int = 50_000

# ---------------------------------------------------------------------------
# OSRM / Nominatim (routing and geocoding)
# ---------------------------------------------------------------------------
OSRM_BASE_URL: str = "https://routing.openstreetmap.de/routed-car/route/v1/driving"

NOMINATIM_URL: str = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.openstreetmap.org/",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# Google Maps export
# ---------------------------------------------------------------------------
GMAPS_MAX_WAYPOINTS: int = 9
