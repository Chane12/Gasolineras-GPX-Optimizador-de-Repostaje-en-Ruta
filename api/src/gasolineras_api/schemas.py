"""Request/response models. They are the public contract: the web generates its TypeScript types from them."""

from typing import Literal

from pydantic import BaseModel, Field
from shapely.geometry import LineString

# ~0.1 m precision: plenty for maps and keeps the JSON small.
COORD_DECIMALS = 6


class ErrorResponse(BaseModel):
    """Error explained for the end user, in Spanish."""

    detail: str = Field(examples=["No encontramos la ubicación «Villarriba»."])


class LineStringGeometry(BaseModel):
    """GeoJSON LineString in WGS84. Coordinates are ``[lon, lat]`` (GeoJSON order)."""

    type: Literal["LineString"] = "LineString"
    coordinates: list[tuple[float, float]]

    @classmethod
    def from_shapely(cls, line: LineString) -> "LineStringGeometry":
        return cls(
            coordinates=[(round(x, COORD_DECIMALS), round(y, COORD_DECIMALS)) for x, y, *_ in line.coords],
        )


class Place(BaseModel):
    """A geocoded place."""

    query: str = Field(description="Texto tal como lo escribió el usuario")
    lat: float
    lon: float


class RouteTextRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=200, examples=["Ávila"])
    destination: str = Field(min_length=2, max_length=200, examples=["Segovia"])


class RouteResponse(BaseModel):
    """A validated route in Spain, ready to search for petrol stations along it."""

    track: LineStringGeometry
    point_count: int = Field(description="Número de puntos del track")
    origin: Place | None = Field(default=None, description="Solo en rutas calculadas desde texto")
    destination: Place | None = Field(default=None, description="Solo en rutas calculadas desde texto")
