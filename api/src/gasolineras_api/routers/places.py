"""Place suggestions while the user types (Photon)."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from gasolineras_api.ratelimit import RATE_LIMIT_RESPONSE, rate_limited
from gasolineras_api.schemas import ErrorResponse, PlaceSuggestion, PlaceSuggestionsResponse
from gasolineras_core.ingestion import geocoder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/places", tags=["lugares"])


@router.get(
    "/suggest",
    response_model=PlaceSuggestionsResponse,
    dependencies=[Depends(rate_limited("suggest"))],
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse, "description": "Photon no responde"},
        **RATE_LIMIT_RESPONSE,
    },
)
def suggest_places(
    q: Annotated[str, Query(max_length=100, description="Lo que el usuario lleva escrito")],
) -> PlaceSuggestionsResponse:
    """Lugares de España que encajan con lo escrito, los más importantes primero (para autocompletar)."""
    try:
        places = geocoder.suggest_places(q)
    except geocoder.RoutingServiceError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return PlaceSuggestionsResponse(
        places=[PlaceSuggestion(name=p.name, context=p.context, lat=p.lat, lon=p.lon, kind=p.kind) for p in places]
    )
