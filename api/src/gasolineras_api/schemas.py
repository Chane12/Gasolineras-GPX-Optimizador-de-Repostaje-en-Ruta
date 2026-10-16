"""Request/response models. They are the public contract: the web generates its TypeScript types from them."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from shapely.geometry import LineString

from gasolineras_core.config import MAX_TRACK_POINTS
from gasolineras_core.ingestion.miteco import MitecoResult, price_freshness

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


class Coordinates(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteTextRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=200, examples=["Ávila"])
    destination: str = Field(min_length=2, max_length=200, examples=["Segovia"])
    origin_point: Coordinates | None = Field(
        default=None, description="Coordenadas del lugar elegido en las sugerencias: evita volver a buscarlo por nombre"
    )
    destination_point: Coordinates | None = Field(default=None, description="Igual que origin_point, para el destino")


class PlaceSuggestion(BaseModel):
    """A place offered while the user types."""

    name: str = Field(examples=["Valencia de Don Juan"])
    context: str = Field(description="Comarca, provincia o comunidad, para distinguir lugares con el mismo nombre")
    lat: float
    lon: float
    kind: str = Field(description="Tipo de lugar en OpenStreetMap: city, town, village…")


class PlaceSuggestionsResponse(BaseModel):
    places: list[PlaceSuggestion] = Field(description="Los más importantes primero; vacía si no hay ninguno")


class RouteResponse(BaseModel):
    """A validated route in Spain, ready to search for petrol stations along it."""

    track: LineStringGeometry
    point_count: int = Field(description="Número de puntos del track")
    origin: Place | None = Field(default=None, description="Solo en rutas calculadas desde texto")
    destination: Place | None = Field(default=None, description="Solo en rutas calculadas desde texto")
    duration_min: float | None = Field(
        default=None, description="Duración por carretera sin paradas (OSRM); solo en rutas calculadas desde texto"
    )


# ---------------------------------------------------------------------------
# Prices and fuels
# ---------------------------------------------------------------------------

FuelId = Literal[
    "gasolina_95",
    "gasolina_95_premium",
    "gasolina_98",
    "diesel",
    "diesel_premium",
    "glp",
    "gnc",
    "gnl",
    "gasoil_b",
    "gasolina_95_e10",
    "gasolina_98_e10",
    "hidrogeno",
]


class Fuel(BaseModel):
    id: FuelId
    label: str = Field(description="Nombre para mostrar, en español")


class PricesStatus(BaseModel):
    """Age of the MITECO prices. The web must show a warning unless ``status`` is ``fresh``."""

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

    @classmethod
    def from_result(cls, result: MitecoResult, now: datetime | None = None) -> "PricesStatus":
        now = now or datetime.now(UTC)
        return cls(
            status=price_freshness(result.fetched_at, now).value,
            fetched_at=result.fetched_at,
            age_minutes=int((now - result.fetched_at).total_seconds() // 60),
            from_fallback=result.from_fallback,
            station_count=len(result.df),
        )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    track: LineStringGeometry = Field(description="Ruta devuelta por /route/text o /route/gpx")
    fuel: FuelId = "gasolina_95"
    max_detour_km: int = Field(default=5, ge=1, le=15, description="Distancia máxima a la ruta (km)")
    top_n: int = Field(default=5, ge=1, le=20, description="Cuántas de las más baratas mostrar")
    segment_km: int = Field(
        default=50,
        description="Añade la más barata de cada tramo de esta longitud (10–300 km); 0 lo desactiva",
    )
    only_24h: bool = Field(default=False, description="Solo gasolineras abiertas 24 h")
    all_on_route: bool = Field(
        default=False,
        description="Modo España Vaciada: añade todas las gasolineras a ≤ 500 m de la ruta, sean o no baratas",
    )
    autonomy_km: int = Field(default=0, ge=0, le=2000, description="Autonomía del vehículo; 0 desactiva el radar")
    include_others: bool = Field(
        default=False,
        description="Devuelve también el resto de gasolineras del corredor con este combustible (other_stations)",
    )

    @field_validator("segment_km")
    @classmethod
    def _segment_range(cls, value: int) -> int:
        if value != 0 and not 10 <= value <= 300:
            raise ValueError("segment_km debe ser 0 o estar entre 10 y 300")
        return value

    @field_validator("track")
    @classmethod
    def _track_size(cls, value: LineStringGeometry) -> LineStringGeometry:
        if not 2 <= len(value.coordinates) <= MAX_TRACK_POINTS:
            raise ValueError(f"El track debe tener entre 2 y {MAX_TRACK_POINTS} puntos")
        return value


class Station(BaseModel):
    id: str | None = Field(default=None, description="Identificador del MITECO (IDEESS)")
    name: str = Field(description="Rótulo")
    address: str | None = None
    town: str | None = None
    province: str | None = None
    postal_code: str | None = None
    schedule: str | None = Field(default=None, description="Horario tal como lo publica el MITECO")
    open_24h: bool
    lat: float
    lon: float
    price: float = Field(description="Precio del combustible elegido (€/L; €/kg en GNC, GNL e hidrógeno)")
    km_on_route: float = Field(description="Kilómetro de la ruta a la altura de la gasolinera")
    savings_vs_max: float | None = Field(
        default=None, description="Ahorro por litro frente a la más cara del corredor (≥ 0)"
    )


class AutonomySegment(BaseModel):
    start_km: float
    end_km: float
    gap_km: float
    level: Literal["safe", "warning", "critical"] = Field(
        description="safe · warning: > 80 % de la autonomía · critical: supera la autonomía"
    )
    autonomy_ratio: float = Field(description="gap_km / autonomía")
    from_name: str
    to_name: str


class SearchResponse(BaseModel):
    prices: PricesStatus
    fuel: Fuel
    route_km: float = Field(description="Longitud de la ruta (km)")
    corridor_station_count: int = Field(description="Gasolineras en el corredor, vendan o no este combustible")
    max_price_in_corridor: float | None = None
    stations: list[Station] = Field(description="Gasolineras sugeridas, ordenadas por km en ruta")
    other_stations: list[Station] | None = Field(
        default=None,
        description="Resto de gasolineras del corredor con este combustible, por km (solo si include_others)",
    )
    autonomy: list[AutonomySegment] | None = Field(
        default=None, description="Radar de autonomía (solo si autonomy_km > 0)"
    )


# ---------------------------------------------------------------------------
# Detours
# ---------------------------------------------------------------------------

MAX_DETOUR_STATIONS = 30


class StationPoint(BaseModel):
    id: str | None = Field(default=None, description="El mismo id que devolvió /search, para casar resultados")
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class DetoursRequest(BaseModel):
    track: LineStringGeometry
    stations: list[StationPoint] = Field(min_length=1, max_length=MAX_DETOUR_STATIONS)

    @field_validator("track")
    @classmethod
    def _track_size(cls, value: LineStringGeometry) -> LineStringGeometry:
        if not 2 <= len(value.coordinates) <= MAX_TRACK_POINTS:
            raise ValueError(f"El track debe tener entre 2 y {MAX_TRACK_POINTS} puntos")
        return value


class Detour(BaseModel):
    id: str | None = None
    lat: float
    lon: float
    detour_km: float | None = Field(description="Ida desde la ruta + vuelta, por carretera; null si OSRM no respondió")
    detour_min: float | None = None


class DetoursResponse(BaseModel):
    detours: list[Detour] = Field(description="En el mismo orden que la petición")
    complete: bool = Field(description="false si alguna gasolinera se quedó sin desvío (servicio de rutas saturado)")


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

MAX_EXPORT_STOPS = 20
LonLat = tuple[float, float]


class GmapsUrlRequest(BaseModel):
    origin: LonLat = Field(description="[lon, lat] del inicio de la ruta")
    destination: LonLat = Field(description="[lon, lat] del final de la ruta")
    stops: list[StationPoint] = Field(default_factory=list, max_length=MAX_EXPORT_STOPS, description="En orden de ruta")


class GmapsUrlResponse(BaseModel):
    url: str
    truncated: int = Field(description="Paradas omitidas: Google Maps admite como máximo 9 intermedias")


class GpxStop(BaseModel):
    name: str = Field(max_length=120)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    price: float | None = Field(default=None, ge=0, description="€/L, para la descripción del waypoint")
    liters: float | None = Field(default=None, ge=0, description="Litros previstos en esta parada")
    cost: float | None = Field(default=None, ge=0, description="Coste previsto de la parada (€)")
    km: float | None = Field(default=None, ge=0, description="Km de la ruta, para la descripción del waypoint")
    schedule: str | None = Field(default=None, max_length=120, description="Horario, para la descripción")


class GpxExportRequest(BaseModel):
    track: LineStringGeometry
    stops: list[GpxStop] = Field(default_factory=list, max_length=10)
    name: str = Field(default="Ruta con gasolineras", max_length=120)
    splice_detours: bool = Field(
        default=True,
        description="Desviar el track por cada gasolinera con OSRM. `false` si el track ya pasa por ellas "
        "(la web calcula los desvíos en el navegador cuando el servidor no llega a OSRM)",
    )

    @field_validator("track")
    @classmethod
    def _track_size(cls, value: LineStringGeometry) -> LineStringGeometry:
        if not 2 <= len(value.coordinates) <= MAX_TRACK_POINTS:
            raise ValueError(f"El track debe tener entre 2 y {MAX_TRACK_POINTS} puntos")
        return value
