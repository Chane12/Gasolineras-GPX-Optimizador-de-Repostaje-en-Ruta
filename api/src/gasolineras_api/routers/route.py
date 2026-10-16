"""Route input: origin/destination text or GPX upload → validated track."""

import logging
from functools import cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from shapely.geometry import LineString

from gasolineras_api.ratelimit import RATE_LIMIT_RESPONSE, rate_limited
from gasolineras_api.schemas import ErrorResponse, LineStringGeometry, Place, RouteResponse, RouteTextRequest
from gasolineras_core.config import DEMO_GPX_PATH
from gasolineras_core.ingestion import geocoder
from gasolineras_core.ingestion.gpx_parser import parse_gpx_track, validate_gpx_track

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/route", tags=["ruta"])

MAX_GPX_BYTES = 15 * 1024 * 1024  # a GPX near the 50,000-point limit is ~5-10 MB

ROUTE_ERRORS: dict[int | str, dict] = {
    status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Lugar, ruta o GPX no válidos"},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse, "description": "Servicio externo no disponible"},
    **RATE_LIMIT_RESPONSE,
}


def _validated(track: LineString) -> LineString:
    try:
        validate_gpx_track(track)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return track


@router.post(
    "/text",
    response_model=RouteResponse,
    responses=ROUTE_ERRORS,
    dependencies=[Depends(rate_limited("external"))],
)
def route_from_text(body: RouteTextRequest) -> RouteResponse:
    """Calcula la ruta por carretera entre un origen y un destino escritos en texto."""
    try:
        origin = geocoder.geocode_place(body.origin)
        destination = geocoder.geocode_place(body.destination)
        track = geocoder.fetch_road_route((origin.lat, origin.lon), (destination.lat, destination.lon))
    except geocoder.RoutingServiceError as exc:
        logger.warning("External routing service unavailable: %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except geocoder.RouteTextError as exc:  # place not found / no road route
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    track = _validated(track)
    return RouteResponse(
        track=LineStringGeometry.from_shapely(track),
        point_count=len(track.coords),
        origin=Place(query=origin.query, lat=origin.lat, lon=origin.lon),
        destination=Place(query=destination.query, lat=destination.lat, lon=destination.lon),
    )


@router.post(
    "/gpx",
    response_model=RouteResponse,
    dependencies=[Depends(rate_limited("default"))],
    responses={
        **ROUTE_ERRORS,
        status.HTTP_413_CONTENT_TOO_LARGE: {"model": ErrorResponse, "description": "Archivo demasiado grande"},
    },
)
def route_from_gpx(file: Annotated[UploadFile, File(description="Archivo .gpx con el track")]) -> RouteResponse:
    """Lee la ruta de un archivo GPX subido por el usuario."""
    data = file.file.read(MAX_GPX_BYTES + 1)
    if len(data) > MAX_GPX_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"El archivo supera el máximo de {MAX_GPX_BYTES // (1024 * 1024)} MB.",
        )
    try:
        track = parse_gpx_track(data, name=file.filename or "GPX")
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    track = _validated(track)
    return RouteResponse(track=LineStringGeometry.from_shapely(track), point_count=len(track.coords))


@cache
def _demo_route() -> RouteResponse:
    track = parse_gpx_track(DEMO_GPX_PATH.read_bytes(), name=DEMO_GPX_PATH.name)
    return RouteResponse(track=LineStringGeometry.from_shapely(track), point_count=len(track.coords))


@router.get("/demo", response_model=RouteResponse, dependencies=[Depends(rate_limited("default"))])
def route_demo() -> RouteResponse:
    """Ruta de ejemplo: los puertos de la Sierra de Gredos (la misma demo que la app Streamlit)."""
    return _demo_route()
