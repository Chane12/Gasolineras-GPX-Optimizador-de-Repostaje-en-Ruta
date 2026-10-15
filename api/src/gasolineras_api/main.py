"""FastAPI application factory.

Run locally: ``uv run uvicorn gasolineras_api.main:app --reload``
"""

from importlib.metadata import version
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

API_VERSION = version("gasolineras-api")


class HealthResponse(BaseModel):
    """Liveness check. Data freshness (MITECO age) will be added with the catalogue cache."""

    status: Literal["ok"]
    version: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="Gasolineras en Ruta API",
        description="Optimizador de repostaje en ruta para España con precios oficiales del MITECO.",
        version=API_VERSION,
    )

    @app.get("/health", response_model=HealthResponse, tags=["sistema"])
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=API_VERSION)

    return app


app = create_app()
