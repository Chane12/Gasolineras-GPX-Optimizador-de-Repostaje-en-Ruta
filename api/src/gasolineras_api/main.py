"""FastAPI application factory.

Run locally: ``uv run uvicorn gasolineras_api.main:app --reload``
"""

import logging
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from gasolineras_api.catalogue import PriceCatalogue
from gasolineras_api.logging_config import configure_logging
from gasolineras_api.ratelimit import RateLimiter
from gasolineras_api.routers import detours, export, places, route, search
from gasolineras_api.routers.search import get_catalogue
from gasolineras_api.schemas import PricesStatus

API_VERSION = version("gasolineras-api")
CORS_ORIGINS_ENV = "GASOLINERAS_CORS_ORIGINS"
DEFAULT_CORS_ORIGINS = ["http://localhost:3000"]  # Next.js en local
CORS_ORIGIN_REGEX_ENV = "GASOLINERAS_CORS_ORIGIN_REGEX"

logger = logging.getLogger(__name__)


def cors_origins_from_env() -> list[str]:
    """Origins allowed to call the API from a browser (the web). Comma-separated in GASOLINERAS_CORS_ORIGINS."""
    raw = os.environ.get(CORS_ORIGINS_ENV, "")
    origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return origins or DEFAULT_CORS_ORIGINS


def cors_origin_regex_from_env() -> str | None:
    """Pattern for origins that cannot be listed one by one (Vercel preview URLs). The whole origin must match."""
    return os.environ.get(CORS_ORIGIN_REGEX_ENV, "").strip() or None


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
    catalogue: PriceCatalogue | None = None,
    warm_up: bool = True,
    rate_limiter: RateLimiter | None = None,
    cors_origins: list[str] | None = None,
    cors_origin_regex: str | None = None,
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

    # Order matters: the last middleware added is the outermost. CORS must wrap everything.
    app.add_middleware(GZipMiddleware, minimum_size=1024)  # tracks of thousands of points
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else cors_origins_from_env(),
        allow_origin_regex=cors_origin_regex if cors_origin_regex is not None else cors_origin_regex_from_env(),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Retry-After", "Content-Disposition"],
        max_age=600,
    )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Never an unexplained 500: log the details, give the user a clear message.
        logger.exception("Unexpected error in %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Ha ocurrido un error inesperado. Inténtalo de nuevo y, si se repite, avísanos."},
        )

    @app.get("/health", response_model=HealthResponse, tags=["sistema"])
    def health(request: Request) -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION, prices=_prices_status(get_catalogue(request)))

    app.include_router(route.router)
    app.include_router(places.router)
    app.include_router(search.router)
    app.include_router(detours.router)
    app.include_router(export.router)
    return app


app = create_app()
