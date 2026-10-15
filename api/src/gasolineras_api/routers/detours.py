"""Real road detours to stations (OSRM), with bounded concurrency and caching in the core."""

import logging

from fastapi import APIRouter, Depends
from shapely.geometry import LineString

from gasolineras_api.ratelimit import RATE_LIMIT_RESPONSE, rate_limited
from gasolineras_api.schemas import Detour, DetoursRequest, DetoursResponse
from gasolineras_core.optimizer import export

logger = logging.getLogger(__name__)

router = APIRouter(tags=["búsqueda"])


@router.post(
    "/detours",
    response_model=DetoursResponse,
    responses=RATE_LIMIT_RESPONSE,
    dependencies=[Depends(rate_limited("external"))],
)
def detours(body: DetoursRequest) -> DetoursResponse:
    """Calcula el desvío real por carretera (ida y vuelta desde la ruta) hasta cada gasolinera.

    Si el servicio de rutas falla para alguna, su desvío llega a null y ``complete`` es false:
    el resto de resultados siguen siendo válidos.
    """
    track = LineString(body.track.coordinates)
    results = export.compute_detours(track, [(s.lon, s.lat) for s in body.stations])
    items = [
        Detour(
            id=station.id,
            lat=station.lat,
            lon=station.lon,
            detour_km=round(result["distance_km"], 2) if result else None,
            detour_min=round(result["duration_min"], 1) if result else None,
        )
        for station, result in zip(body.stations, results, strict=True)
    ]
    complete = all(r is not None for r in results)
    if not complete:
        logger.warning("Detours incomplete: %d of %d without result", results.count(None), len(results))
    return DetoursResponse(detours=items, complete=complete)
