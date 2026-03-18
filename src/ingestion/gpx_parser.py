"""
src/ingestion/gpx_parser.py
===========================
GPX file loading, validation, and track simplification.
"""

from __future__ import annotations

from pathlib import Path

import gpxpy
from shapely.geometry import LineString

from src.config import BBOX_SPAIN, MAX_TRACK_POINTS


def load_gpx_track(gpx_path: str | Path) -> LineString:
    """
    Lee un archivo GPX y extrae el track principal como un LineString de Shapely.

    Itera sobre todos los tracks y segmentos del archivo GPX, acumulando
    los puntos en orden. Requiere que el GPX tenga al menos un track con
    al menos dos puntos.

    Parameters
    ----------
    gpx_path : str | Path
        Ruta al archivo .gpx.

    Returns
    -------
    LineString
        Geometría de la ruta en coordenadas WGS84 (longitud, latitud).
    """
    gpx_path = Path(gpx_path)
    if not gpx_path.exists():
        raise FileNotFoundError(f"No se encuentra el archivo GPX: {gpx_path}")

    try:
        with open(gpx_path, encoding="utf-8") as f:
            gpx = gpxpy.parse(f)
    except UnicodeDecodeError:
        with open(gpx_path, encoding="latin-1") as f:
            gpx = gpxpy.parse(f)

    coords: list[tuple[float, float]] = []

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                coords.append((point.longitude, point.latitude))

    # Fallback: routes
    if not coords:
        for route in gpx.routes:
            for point in route.points:
                coords.append((point.longitude, point.latitude))

    if len(coords) < 2:
        raise ValueError(f"El GPX '{gpx_path.name}' debe contener al menos 2 puntos de track.")

    print(f"[GPX] Puntos cargados del track: {len(coords)}")
    return LineString(coords)


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
    print(
        f"[Simplify] Vertices: {len(track.coords)} --> {len(simplified.coords)} "
        f"(tolerancia={tolerance_deg} deg)"
    )
    return simplified
