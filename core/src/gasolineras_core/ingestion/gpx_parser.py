"""
gasolineras_core.ingestion.gpx_parser
=====================================
GPX file loading, validation, and track simplification.
"""

from __future__ import annotations

import logging
from pathlib import Path

import gpxpy
from shapely.geometry import LineString

from gasolineras_core.config import BBOX_SPAIN, MAX_TRACK_POINTS

logger = logging.getLogger(__name__)


def parse_gpx_track(data: bytes | str, name: str = "GPX") -> LineString:
    """
    Extrae el track principal de un GPX en memoria como un LineString de Shapely (WGS84, lon/lat).

    Acumula en orden los puntos de todos los tracks y segmentos; si no hay tracks, usa las rutas.

    Raises
    ------
    ValueError
        Si no es un GPX válido o tiene menos de 2 puntos.
    """
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
    else:
        text = data

    try:
        gpx = gpxpy.parse(text)
    except Exception as exc:  # gpxpy raises several exception types for malformed XML/GPX
        raise ValueError(f"El archivo «{name}» no es un GPX válido.") from exc

    coords: list[tuple[float, float]] = [
        (point.longitude, point.latitude)
        for track in gpx.tracks
        for segment in track.segments
        for point in segment.points
    ]
    if not coords:
        coords = [(point.longitude, point.latitude) for route in gpx.routes for point in route.points]

    if len(coords) < 2:
        raise ValueError(f"El GPX «{name}» debe contener al menos 2 puntos de track.")

    logger.info("GPX %s: %d track points", name, len(coords))
    return LineString(coords)


def load_gpx_track(gpx_path: str | Path) -> LineString:
    """
    Lee un archivo GPX y extrae el track principal como un LineString de Shapely (ver ``parse_gpx_track``).
    """
    gpx_path = Path(gpx_path)
    if not gpx_path.exists():
        raise FileNotFoundError(f"No se encuentra el archivo GPX: {gpx_path}")
    return parse_gpx_track(gpx_path.read_bytes(), name=gpx_path.name)


def validate_gpx_track(track: LineString) -> None:
    """
    Valida que el track GPX sea seguro de procesar.

    Comprueba:
    1. Que no exceda el máximo de puntos permitido (protección OOM).
    2. Que el centroide de la ruta esté dentro del territorio español.

    Parameters
    ----------
    track : LineString
        LineString en WGS84 con las coordenadas de la ruta.

    Raises
    ------
    ValueError
        Si el track tiene demasiados puntos o no está en España.
    """
    n_pts = len(track.coords)
    if n_pts > MAX_TRACK_POINTS:
        raise ValueError(
            f"La ruta tiene demasiados puntos ({n_pts:,}). "
            f"Máximo permitido: {MAX_TRACK_POINTS:,}. "
            "Simplifica el GPX antes de subirlo."
        )

    lons = [c[0] for c in track.coords]
    lats = [c[1] for c in track.coords]
    c_lon = sum(lons) / len(lons)
    c_lat = sum(lats) / len(lats)

    bb = BBOX_SPAIN
    if not (bb["min_lat"] < c_lat < bb["max_lat"] and bb["min_lon"] < c_lon < bb["max_lon"]):
        raise ValueError(
            f"La ruta no parece estar en territorio español "
            f"(centroide: lat={c_lat:.3f}, lon={c_lon:.3f}). "
            "Esta herramienta solo cubre España peninsular, Baleares y Canarias."
        )

    print(f"[Validación] Track OK: {n_pts:,} puntos, centroide ({c_lat:.3f}, {c_lon:.3f}).")


def simplify_track(track: LineString, tolerance_deg: float = 0.0005) -> LineString:
    """
    Simplifica un LineString usando el algoritmo de Ramer-Douglas-Peucker.

    Parameters
    ----------
    track : LineString
        Geometría original de la ruta en EPSG:4326 (grados decimales).
    tolerance_deg : float
        Tolerancia de simplificación en grados. ~0.0005° ≈ 50 metros.

    Returns
    -------
    LineString
        LineString simplificado.
    """
    simplified = track.simplify(tolerance_deg, preserve_topology=True)
    if not isinstance(simplified, LineString):
        raise ValueError(f"La simplificación del track produjo una geometría inesperada: {simplified.geom_type}")
    print(f"[Simplify] Vertices: {len(track.coords)} --> {len(simplified.coords)} (tolerancia={tolerance_deg} deg)")
    return simplified
