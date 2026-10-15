"""FastAPI application factory.

Run locally: ``uv run uvicorn gasolineras_api.main:app --reload``
"""

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel

from gasolineras_api.catalogue import PriceCatalogue
from gasolineras_api.logging_config import configure_logging
from gasolineras_api.ratelimit import RateLimiter
from gasolineras_api.routers import detours, export, route, search
from gasolineras_api.routers.search import get_catalogue
from gasolineras_api.schemas import PricesStatus

API_VERSION = version("gasolineras-api")


class HealthResponse(BaseModel):
    """Liveness check plus the age of the price data. Never triggers a download."""

    status: Literal["ok"]
    version: str
    prices: PricesStatus


def _prices_status(catalogue: PriceCatalogue) -> PricesStatus:
    result = catalogue.current
    if result is None:
        return PricesStatus(status="loading" if catalogue.is_refreshing else "unavailable")
    return PricesStatus.from_result(result)


def create_app(
    catalogue: PriceCatalogue | None = None, warm_up: bool = True, rate_limiter: RateLimiter | None = None
) -> FastAPI:
    """Build the app. Tests pass their own ``catalogue`` (no network), ``warm_up=False`` and limits."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging()
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
    app.state.rate_limiter = rate_limiter or RateLimiter()

    @app.get("/health", response_model=HealthResponse, tags=["sistema"])
    def health(request: Request) -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION, prices=_prices_status(get_catalogue(request)))

    app.include_router(route.router)
    app.include_router(search.router)
    app.include_router(detours.router)
    app.include_router(export.router)
    return app


app = create_app()
