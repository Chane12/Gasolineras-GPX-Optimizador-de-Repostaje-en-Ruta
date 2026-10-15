"""
gasolineras_core.config
=======================
Centralized configuration and constants for the Gasolineras en Ruta project.
All modules import shared constants from here — single source of truth.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Datos empaquetados con el motor (viajan con el paquete, sea cual sea el cwd).
PACKAGE_DATA_DIR: Path = Path(__file__).resolve().parent / "data"
DEMO_GPX_PATH: Path = PACKAGE_DATA_DIR / "sierra_gredos.gpx"

# Datos de ejecución (caché/fallback del MITECO). Configurable para despliegues
# (p. ej. un volumen o /tmp en contenedores); por defecto, el directorio de trabajo.
DATA_DIR: Path = Path(os.environ.get("GASOLINERAS_DATA_DIR", Path.cwd()))

# ---------------------------------------------------------------------------
# Coordinate Reference Systems
# ---------------------------------------------------------------------------
CRS_WGS84: str = "EPSG:4326"
CRS_UTM30N: str = "EPSG:25830"

# ---------------------------------------------------------------------------
# MITECO API
# ---------------------------------------------------------------------------
MITECO_API_URL: str = (
    "https://sedeaplicaciones.minetur.gob.es/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/"
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
    "Precio Gases licuados del petróleo",  # con tilde, como lo publica el MITECO
    "Precio Hidrogeno",
]

COORD_COLUMNS: list[str] = ["Latitud", "Longitud (WGS84)"]

# Nombres de columna antiguos o mal escritos → nombre real del MITECO (se renombran al limpiar los datos).
MITECO_COLUMN_ALIASES: dict[str, str] = {
    "Precio Gases licuados del petroleo": "Precio Gases licuados del petróleo",
}

# El servidor del MITECO solo negocia TLS 1.2 con AES256-GCM-SHA384 (intercambio de claves RSA, sin
# secreto hacia adelante). Python >= 3.10 excluye esos cifrados por defecto y la conexión directa fallaba
# siempre. Se añade solo ese cifrado y solo para este host; el certificado se sigue verificando. ADR 0007.
MITECO_HOST_PREFIX: str = "https://sedeaplicaciones.minetur.gob.es/"
MITECO_EXTRA_TLS_CIPHERS: str = "AES256-GCM-SHA384"

# Antigüedad de los precios (decisión de producto, 2026-10-15):
# - hasta 30 min: actuales (también es el TTL de la caché del catálogo);
# - hasta 24 h: se muestran con un aviso visible de su antigüedad;
# - más de 24 h: se muestran con un aviso fuerte de que pueden no ser fiables. Nunca se deja sin resultados.
PRICES_FRESH_MAX_AGE_S: float = 30 * 60
PRICES_STRONG_WARNING_AGE_S: float = 24 * 3600

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
# OSRM / Nominatim / Photon (routing and geocoding) — uso responsable, ADR 0005
# ---------------------------------------------------------------------------
# Identificación honesta ante los servicios de OSM (nunca suplantar un navegador).
PROJECT_URL: str = "https://github.com/Chane12/Gasolineras-GPX-Optimizador-de-Repostaje-en-Ruta"
USER_AGENT: str = f"GasolinerasEnRuta/1.0 (+{PROJECT_URL})"

OSRM_BASE_URL: str = "https://routing.openstreetmap.de/routed-car/route/v1/driving"
OSRM_FALLBACK_URL: str = "https://router.project-osrm.org/route/v1/driving"

NOMINATIM_URL: str = "https://nominatim.openstreetmap.org/search"
PHOTON_URL: str = "https://photon.komoot.io/api"
GEOCODER_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "application/json",
}

# Política de Nominatim: como máximo 1 petición/s por aplicación. Si la cola de espera
# supera GEOCODER_MAX_WAIT_S, se responde "servicio ocupado" en vez de bloquear.
GEOCODER_MIN_INTERVAL_S: float = 1.0
GEOCODER_MAX_WAIT_S: float = 10.0
GEOCODE_CACHE_TTL_S: float = 7 * 24 * 3600  # los lugares no se mueven
GEOCODE_CACHE_MAX_ITEMS: int = 2048
ROUTE_CACHE_TTL_S: float = 24 * 3600
ROUTE_CACHE_MAX_ITEMS: int = 512

# ---------------------------------------------------------------------------
# Google Maps export
# ---------------------------------------------------------------------------
GMAPS_MAX_WAYPOINTS: int = 9
