"""FastAPI application factory.

Run locally: ``uv run uvicorn gasolineras_api.main:app --reload``
"""

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from gasolineras_api.catalogue import PriceCatalogue
from gasolineras_api.routers import route
from gasolineras_core.ingestion.miteco import price_freshness

API_VERSION = version("gasolineras-api")


class PricesStatus(BaseModel):
    """State of the MITECO price catalogue held in memory."""

    status: Literal["fresh", "stale", "very_stale", "loading", "unavailable"] = Field(
        description=(
            "fresh: ≤ 30 min · stale: ≤ 24 h (mostrar aviso) · very_stale: > 24 h (aviso fuerte) · "
            "loading: primera descarga en curso · unavailable: sin datos"
        )
    )
    fetched_at: datetime | None = Field(default=None, description="Momento de la descarga de los precios (UTC)")
    age_minutes: int | None = None
    from_fallback: bool = Field(default=False, description="Copia local porque el MITECO no respondía")
    station_count: int = 0


class HealthResponse(BaseModel):
    """Liveness check plus the age of the price data. Never triggers a download."""

    status: Literal["ok"]
    version: str
    prices: PricesStatus


def get_catalogue(request: Request) -> PriceCatalogue:
    return request.app.state.catalogue


def _prices_status(catalogue: PriceCatalogue) -> PricesStatus:
    result = catalogue.current
    if result is None:
        return PricesStatus(status="loading" if catalogue.is_refreshing else "unavailable")
    now = datetime.now(UTC)
    return PricesStatus(
        status=price_freshness(result.fetched_at, now).value,
        fetched_at=result.fetched_at,
        age_minutes=int((now - result.fetched_at).total_seconds() // 60),
        from_fallback=result.from_fallback,
        station_count=len(result.df),
    )


def create_app(catalogue: PriceCatalogue | None = None, warm_up: bool = True) -> FastAPI:
    """Build the app. Tests pass their own ``catalogue`` (no network) and ``warm_up=False``."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if warm_up:
            # Cold starts (ADR 0002): answer requests at once; prices load in the background.
            threading.Thread(target=app.state.catalogue.warm_up, name="miteco-warm-up", daemon=True).start()
        yield

    app = FastAPI(
        title="Gasolineras en Ruta API",
        description="Optimizador de repostaje en ruta para España con precios oficiales del MITECO.",
        version=API_VERSION,
        lifespan=lifespan,
    )
    app.state.catalogue = catalogue or PriceCatalogue()

    @app.get("/health", response_model=HealthResponse, tags=["sistema"])
    def health(request: Request) -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION, prices=_prices_status(get_catalogue(request)))

    app.include_router(route.router)
    return app


app = create_app()
