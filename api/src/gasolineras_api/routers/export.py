"""Export the trip: Google Maps link and GPX with fuel stops."""

import geopandas as gpd
from fastapi import APIRouter, Depends, Response
from shapely.geometry import LineString

from gasolineras_api.ratelimit import RATE_LIMIT_RESPONSE, rate_limited
from gasolineras_api.schemas import GmapsUrlRequest, GmapsUrlResponse, GpxExportRequest
from gasolineras_core.config import CRS_WGS84
from gasolineras_core.optimizer import export

router = APIRouter(prefix="/export", tags=["exportación"])

_PRICE_COLUMN = "precio_parada"


@router.post(
    "/gmaps-url",
    response_model=GmapsUrlResponse,
    responses=RATE_LIMIT_RESPONSE,
    dependencies=[Depends(rate_limited("default"))],
)
def gmaps_url(body: GmapsUrlRequest) -> GmapsUrlResponse:
    """Enlace de Google Maps con la ruta y las paradas de repostaje (máximo 9 intermedias)."""
    stops = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy([s.lon for s in body.stops], [s.lat for s in body.stops]), crs=CRS_WGS84
    )
    url, truncated = export.generate_google_maps_url(LineString([body.origin, body.destination]), stops)
    return GmapsUrlResponse(url=url, truncated=truncated)


@router.post(
    "/gpx",
    response_class=Response,
    responses={200: {"content": {"application/gpx+xml": {}}, "description": "Archivo GPX"}, **RATE_LIMIT_RESPONSE},
    dependencies=[Depends(rate_limited("external"))],
)
def gpx(body: GpxExportRequest) -> Response:
    """GPX con la ruta y las paradas como waypoints; el track se desvía por cada gasolinera (OSRM).

    Si el servicio de rutas no responde para una parada, el track solo pasa por la gasolinera.
    """
    track = LineString(body.track.coordinates)
    stops = gpd.GeoDataFrame(
        {
            "Rótulo": [s.name for s in body.stops],
            _PRICE_COLUMN: [s.price or 0.0 for s in body.stops],
            "litros_a_repostar": [s.liters or 0.0 for s in body.stops],
            "coste_parada_eur": [s.cost or 0.0 for s in body.stops],
        },
        geometry=gpd.points_from_xy([s.lon for s in body.stops], [s.lat for s in body.stops]),
        crs=CRS_WGS84,
    )
    xml = export.enrich_gpx_with_stops(export.build_gpx_from_track(track, body.name), stops, fuel_column=_PRICE_COLUMN)
    return Response(
        content=xml,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": 'attachment; filename="ruta-gasolineras.gpx"'},
    )
