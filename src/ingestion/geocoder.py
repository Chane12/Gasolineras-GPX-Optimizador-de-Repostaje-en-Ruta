"""
src/ingestion/geocoder.py
=========================
Geocoding (Nominatim/Photon) and OSRM routing for text-based route input.
"""

from __future__ import annotations

import random
import time

import requests
from shapely.geometry import LineString

from src.config import NOMINATIM_HEADERS, NOMINATIM_URL, OSRM_BASE_URL


class RouteTextError(ValueError):
    """Se lanza cuando no es posible trazar la ruta entre los puntos de texto dados."""


def _geocode(lugar: str, timeout: float = 5.0) -> tuple[float, float]:
    """
    Geocodifica un nombre de lugar usando Nominatim (OSM) y Photon (Komoot).

    Parameters
    ----------
    lugar : str
        Nombre del lugar a geocodificar.
    timeout : float
        Tiempo máximo de espera en segundos.

    Returns
    -------
    tuple[float, float]
        (latitud, longitud) en WGS84.

    Raises
    ------
    RouteTextError
        Si no se devuelven resultados o la llamada falla.
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
        "GasolinerasRutaApp/1.0",
    ]

    headers = NOMINATIM_HEADERS.copy()

    endpoints = [
        {"url": NOMINATIM_URL, "type": "nominatim"},
        {"url": "https://photon.komoot.io/api", "type": "photon"},
    ]

    last_err = None

    for attempt, ep in enumerate(endpoints):
        headers["User-Agent"] = random.choice(user_agents)
        try:
            if attempt > 0:
                time.sleep(2)  # Cooldown básico solo entre alternancia de endpoints principales

            query_lugar = lugar
            if "españa" not in lugar.lower() and "spain" not in lugar.lower():
                query_lugar = f"{lugar}, España"

            if ep["type"] == "nominatim":
                params = {"q": query_lugar, "format": "json", "limit": 1, "countrycodes": "es"}
            else:
                params = {"q": query_lugar, "limit": 1}

            resp = requests.get(
                ep["url"],
                params=params,
                headers=headers,
                timeout=timeout,
            )
            resp.raise_for_status()
            results = resp.json()

            lat, lon = None, None
            if ep["type"] == "nominatim":
                if not results:
                    raise RouteTextError(f"No encontramos la ubicación «{lugar}».")
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
            elif ep["type"] == "photon":
                if not results.get("features"):
                    raise RouteTextError(f"No encontramos la ubicación «{lugar}».")
                coords = results["features"][0]["geometry"]["coordinates"]
                lon, lat = float(coords[0]), float(coords[1])

            print(f"[Geocode] «{lugar}» -> ({lat:.5f}, {lon:.5f}) via {ep['url']}")
            return lat, lon

        except RouteTextError:
            raise
        except requests.exceptions.HTTPError:
            last_err = resp.status_code
            if resp.status_code in (429, 403):
                print(f"[Geocode] Rate limit/Forbidden en {ep['url']}, intentando alternativa...")
                continue
            raise RouteTextError(f"Error HTTP al geocodificar «{lugar}»: {resp.status_code}") from None
        except Exception as exc:
            last_err = exc
            print(f"[Geocode] Error en {ep['url']}: {exc}")
            continue

    raise RouteTextError(
        f"Error al geocodificar «{lugar}» tras intentar varios servidores. Último error: {last_err}"
    )


def get_route_from_text(origen: str, destino: str) -> LineString:
    """
    Obtiene la ruta por carretera entre dos puntos descritos en texto plano
    y la devuelve como un LineString de Shapely en EPSG:4326.

    Parameters
    ----------
    origen : str
        Nombre del punto de partida.
    destino : str
        Nombre del destino.

    Returns
    -------
    LineString
        Ruta en EPSG:4326.

    Raises
    ------
    RouteTextError
        Ante cualquier fallo de geocodificación o de la API OSRM.
    """
    lat_o, lon_o = _geocode(origen)
    lat_d, lon_d = _geocode(destino)

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0",
    ]
    headers = {"User-Agent": random.choice(user_agents)}

    endpoints = [
        f"{OSRM_BASE_URL}/{lon_o},{lat_o};{lon_d},{lat_d}?overview=full&geometries=geojson&alternatives=false&steps=false",
        f"{OSRM_BASE_URL}/{lon_o},{lat_o};{lon_d},{lat_d}?overview=simplified&geometries=geojson&alternatives=false&steps=false",
        f"http://router.project-osrm.org/route/v1/driving/{lon_o},{lat_o};{lon_d},{lat_d}?overview=simplified&geometries=geojson&alternatives=false&steps=false",
    ]

    data = None
    last_err = None

    for url in endpoints:
        try:
            print("[Ruta] Intentando OSRM endpoint...")
            resp = requests.get(url, headers=headers, timeout=12.0)
            if resp.status_code == 429:
                last_err = "El servicio de enrutamiento está saturado (rate-limit)."
                continue
            resp.raise_for_status()
            data = resp.json()
            break
        except Exception as exc:
            last_err = str(exc)
            data = None

    if data is None:
        raise RouteTextError(
            f"No se pudo contactar con ningún servicio de OSRM. Último error: {last_err}"
        )

    try:
        routes = data.get("routes", [])
        if not routes:
            raise RouteTextError(
                f"OSRM no encontró ruta entre «{origen}» y «{destino}». "
                "Comprueba que ambos puntos sean accesibles por carretera."
            )
        coords = routes[0]["geometry"]["coordinates"]
        if len(coords) < 2:
            raise RouteTextError("La ruta devuelta por OSRM es demasiado corta.")
        track = LineString(coords)
        dist_km = routes[0]["legs"][0]["distance"] / 1000.0
        print(f"[OSRM] Ruta «{origen}» -> «{destino}»: {dist_km:.1f} km, {len(coords)} puntos.")
        return track
    except RouteTextError:
        raise
    except Exception as exc:
        raise RouteTextError(f"Error al procesar la geometría de la ruta: {exc}") from exc
