"""Station search along a route, and the list of fuels."""

import logging
import math
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from shapely.geometry import LineString

from gasolineras_api.catalogue import CatalogueUnavailableError, PriceCatalogue
from gasolineras_api.schemas import (
    AutonomySegment,
    ErrorResponse,
    Fuel,
    PricesStatus,
    SearchRequest,
    SearchResponse,
    Station,
)
from gasolineras_core.config import CRS_WGS84, FUEL_TYPES
from gasolineras_core.ingestion.gpx_parser import validate_gpx_track
from gasolineras_core.optimizer.search import SearchParams, search_stations

logger = logging.getLogger(__name__)

router = APIRouter(tags=["búsqueda"])

_RADAR_LEVELS = {"seguro": "safe", "atencion": "warning", "critico": "critical"}


def get_catalogue(request: Request) -> PriceCatalogue:
    return request.app.state.catalogue


@router.get("/fuels", response_model=list[Fuel])
def list_fuels() -> list[Fuel]:
    """Combustibles disponibles, en el orden en que se muestran en la interfaz."""
    return [Fuel(id=fuel_id, label=label) for fuel_id, (label, _column) in FUEL_TYPES.items()]  # type: ignore[arg-type]


def _text(row: Any, column: str) -> str | None:
    value = row.get(column)
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def _station(row: Any, lon: float, lat: float, max_price: float | None) -> Station:
    price = float(row["precio_seleccionado"])
    schedule = _text(row, "Horario")
    return Station(
        id=_text(row, "IDEESS"),
        name=_text(row, "Rótulo") or "Gasolinera",
        address=_text(row, "Dirección"),
        town=_text(row, "Municipio"),
        province=_text(row, "Provincia"),
        postal_code=_text(row, "C.P."),
        schedule=schedule,
        open_24h=bool(schedule and ("24H" in schedule.upper() or "24 H" in schedule.upper())),
        lat=round(lat, 6),
        lon=round(lon, 6),
        price=round(price, 3),
        km_on_route=round(float(row["km_ruta"]), 2),
        savings_vs_max=round(max(0.0, max_price - price), 3) if max_price is not None else None,
    )


@router.post(
    "/search",
    response_model=SearchResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse, "description": "Ruta no válida"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse, "description": "Precios no disponibles"},
    },
)
def search(body: SearchRequest, catalogue: Annotated[PriceCatalogue, Depends(get_catalogue)]) -> SearchResponse:
    """Busca las gasolineras más baratas a lo largo de la ruta y, opcionalmente, el radar de autonomía."""
    track = LineString(body.track.coordinates)
    try:
        validate_gpx_track(track)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    try:
        prices, stations = catalogue.get_stations()
    except CatalogueUnavailableError as exc:
        logger.warning("Search without prices: %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    label, column = FUEL_TYPES[body.fuel]
    result = search_stations(
        stations,
        track,
        SearchParams(
            fuel_column=column,
            buffer_m=body.max_detour_km * 1000.0,
            top_n=body.top_n,
            segment_km=float(body.segment_km),
            only_24h=body.only_24h,
            include_all_on_route=body.all_on_route,
            autonomy_km=float(body.autonomy_km),
        ),
    )

    selected = result.stations
    points = selected.geometry.to_crs(CRS_WGS84) if not selected.empty else selected.geometry
    station_list = [
        _station(row, point.x, point.y, result.max_price_in_corridor)
        for (_, row), point in zip(selected.iterrows(), points, strict=True)
    ]
    autonomy = (
        [
            AutonomySegment(
                start_km=round(seg["km_inicio"], 2),
                end_km=round(seg["km_fin"], 2),
                gap_km=round(seg["gap_km"], 2),
                level=_RADAR_LEVELS[seg["nivel"]],  # type: ignore[arg-type]
                autonomy_ratio=round(seg["pct"], 3),
                from_name=str(seg["origen"]),
                to_name=str(seg["destino"]),
            )
            for seg in result.radar
        ]
        if result.radar is not None
        else None
    )

    return SearchResponse(
        prices=PricesStatus.from_result(prices),
        fuel=Fuel(id=body.fuel, label=label),
        route_km=round(result.route_km, 2),
        corridor_station_count=result.corridor_count,
        max_price_in_corridor=result.max_price_in_corridor,
        stations=station_list,
        autonomy=autonomy,
    )
