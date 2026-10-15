"""
gasolineras_core.ingestion.geocoder
===================================
Geocoding (Nominatim, with Photon as fallback) and OSRM routing for text-based route input.

Polite use of OSM services (ADR 0005): identifiable User-Agent, at most one request per second
to each geocoder (process-wide) and caching of places and routes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests
from shapely.geometry import LineString

from gasolineras_core.config import (
    BBOX_SPAIN,
    GEOCODE_CACHE_MAX_ITEMS,
    GEOCODE_CACHE_TTL_S,
    GEOCODER_HEADERS,
    GEOCODER_MAX_WAIT_S,
    GEOCODER_MIN_INTERVAL_S,
    NOMINATIM_URL,
    OSRM_BASE_URL,
    OSRM_FALLBACK_URL,
    PHOTON_URL,
    ROUTE_CACHE_MAX_ITEMS,
    ROUTE_CACHE_TTL_S,
    USER_AGENT,
)
from gasolineras_core.http_utils import RateLimitBusyError, RateLimiter, TTLCache

logger = logging.getLogger(__name__)

LatLon = tuple[float, float]


class RouteTextError(ValueError):
    """Se lanza cuando no es posible trazar la ruta entre los puntos de texto dados."""


class PlaceNotFoundError(RouteTextError):
    """El geocodificador respondió, pero no conoce el lugar indicado."""


class NoRouteError(RouteTextError):
    """OSRM respondió, pero no hay ruta por carretera entre los puntos."""


class RoutingServiceError(RouteTextError):
    """Los servicios externos (geocodificación u OSRM) no están disponibles o están saturados."""


@dataclass(frozen=True)
class GeocodedPlace:
    query: str
    lat: float
    lon: float
    source: str  # "nominatim" | "photon"


_nominatim_limiter = RateLimiter(GEOCODER_MIN_INTERVAL_S, GEOCODER_MAX_WAIT_S)
_photon_limiter = RateLimiter(GEOCODER_MIN_INTERVAL_S, GEOCODER_MAX_WAIT_S)
_geocode_cache: TTLCache[GeocodedPlace] = TTLCache(GEOCODE_CACHE_MAX_ITEMS, GEOCODE_CACHE_TTL_S)
_route_cache: TTLCache[LineString] = TTLCache(ROUTE_CACHE_MAX_ITEMS, ROUTE_CACHE_TTL_S)

_SERVICE_UNAVAILABLE_MSG = (
    "El servicio de búsqueda de lugares no está disponible ahora mismo. Inténtalo de nuevo en unos minutos."
)
_ROUTING_UNAVAILABLE_MSG = (
    "El servicio de rutas por carretera no está disponible ahora mismo. Inténtalo de nuevo en unos minutos."
)


def clear_caches() -> None:
    """Vacía las cachés de lugares y rutas (útil en tests)."""
    _geocode_cache.clear()
    _route_cache.clear()


def normalize_place(place: str) -> str:
    """Clave de caché: sin espacios sobrantes y sin distinguir mayúsculas."""
    return " ".join(place.split()).casefold()


def _with_country(place: str) -> str:
    lowered = place.lower()
    if "españa" in lowered or "spain" in lowered:
        return place
    return f"{place}, España"


def _parse_nominatim(results: Any) -> LatLon | None:
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def _parse_photon(results: Any) -> LatLon | None:
    features = results.get("features") if isinstance(results, dict) else None
    if not features:
        return None
    lon, lat = features[0]["geometry"]["coordinates"][:2]
    return float(lat), float(lon)


def geocode_place(place: str, timeout: float = 5.0) -> GeocodedPlace:
    """
    Convierte un nombre de lugar de España en coordenadas WGS84.

    Usa Nominatim y, si está caído o saturado, Photon. Los resultados se cachean.

    Raises
    ------
    PlaceNotFoundError
        Si el lugar está vacío o el geocodificador no lo encuentra.
    RoutingServiceError
        Si ningún geocodificador está disponible.
    """
    key = normalize_place(place)
    if not key:
        raise PlaceNotFoundError("Indica un lugar de origen y otro de destino.")
    cached = _geocode_cache.get(key)
    if cached is not None:
        return cached

    query = _with_country(" ".join(place.split()))
    bb = BBOX_SPAIN
    endpoints = [
        (
            "nominatim",
            NOMINATIM_URL,
            {"q": query, "format": "json", "limit": 1, "countrycodes": "es"},
            _nominatim_limiter,
            timeout,
            _parse_nominatim,
        ),
        (
            "photon",
            PHOTON_URL,
            {"q": query, "limit": 1, "bbox": f"{bb['min_lon']},{bb['min_lat']},{bb['max_lon']},{bb['max_lat']}"},
            _photon_limiter,
            timeout * 2,  # Photon is slower; it is only the fallback
            _parse_photon,
        ),
    ]

    for source, url, params, limiter, ep_timeout, parse in endpoints:
        try:
            limiter.wait()
            resp = requests.get(url, params=params, headers=GEOCODER_HEADERS, timeout=ep_timeout)
            resp.raise_for_status()
            latlon = parse(resp.json())
        except (RateLimitBusyError, requests.RequestException, ValueError, KeyError, IndexError) as exc:
            logger.warning("Geocoder %s failed for %r: %s", source, place, exc)
            continue

        if latlon is None:
            raise PlaceNotFoundError(f"No encontramos la ubicación «{place.strip()}».")
        result = GeocodedPlace(query=place.strip(), lat=latlon[0], lon=latlon[1], source=source)
        _geocode_cache.set(key, result)
        logger.info("Geocoded %r -> (%.5f, %.5f) via %s", place, result.lat, result.lon, source)
        return result

    raise RoutingServiceError(_SERVICE_UNAVAILABLE_MSG)


def fetch_road_route(origin: LatLon, destination: LatLon, timeout: float = 12.0) -> LineString:
    """
    Pide a OSRM la ruta por carretera entre dos puntos (lat, lon) y la devuelve en EPSG:4326.

    Raises
    ------
    NoRouteError
        Si no existe ruta por carretera entre los puntos.
    RoutingServiceError
        Si ningún servidor OSRM está disponible.
    """
    key = (round(origin[0], 5), round(origin[1], 5), round(destination[0], 5), round(destination[1], 5))
    cached = _route_cache.get(key)
    if cached is not None:
        return cached

    coords_path = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    common = "geometries=geojson&alternatives=false&steps=false"
    urls = [
        f"{OSRM_BASE_URL}/{coords_path}?overview=full&{common}",
        f"{OSRM_BASE_URL}/{coords_path}?overview=simplified&{common}",
        f"{OSRM_FALLBACK_URL}/{coords_path}?overview=simplified&{common}",
    ]
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    data: dict[str, Any] | None = None
    for url in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 400:
                # OSRM answers 400 {"code": "NoRoute"/"NoSegment"} when the points are not connected by road.
                code = resp.json().get("code")
                if code in ("NoRoute", "NoSegment"):
                    raise NoRouteError(
                        "No hay ruta por carretera entre esos dos puntos. Comprueba que ambos sean accesibles en coche."
                    )
            resp.raise_for_status()
            data = resp.json()
            break
        except NoRouteError:
            raise
        except (requests.RequestException, ValueError) as exc:
            logger.warning("OSRM request failed (%s): %s", url.split("/route/")[0], exc)

    if data is None:
        raise RoutingServiceError(_ROUTING_UNAVAILABLE_MSG)

    routes = data.get("routes") or []
    if not routes:
        raise NoRouteError("No hay ruta por carretera entre esos dos puntos.")
    try:
        coords = routes[0]["geometry"]["coordinates"]
    except (KeyError, TypeError) as exc:
        raise RoutingServiceError(_ROUTING_UNAVAILABLE_MSG) from exc
    if len(coords) < 2:
        raise NoRouteError("La ruta devuelta es demasiado corta: el origen y el destino están casi en el mismo punto.")

    track = LineString(coords)
    _route_cache.set(key, track)
    logger.info("OSRM route: %d points", len(coords))
    return track


def get_route_from_text(origen: str, destino: str) -> LineString:
    """
    Obtiene la ruta por carretera entre dos puntos descritos en texto plano
    y la devuelve como un LineString de Shapely en EPSG:4326.

    Raises
    ------
    RouteTextError
        Ante cualquier fallo (sus subclases distinguen la causa).
    """
    o = geocode_place(origen)
    d = geocode_place(destino)
    try:
        return fetch_road_route((o.lat, o.lon), (d.lat, d.lon))
    except NoRouteError:
        raise NoRouteError(
            f"No hay ruta por carretera entre «{o.query}» y «{d.query}». Comprueba que ambos sean accesibles en coche."
        ) from None
