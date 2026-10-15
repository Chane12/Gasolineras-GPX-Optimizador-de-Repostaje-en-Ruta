# Arquitectura

## Visión general

```text
                ┌─────────────────────────── HOY ───────────────────────────┐
 Navegador ───► │ legacy/streamlit (Streamlit Community Cloud)               │
                │        │ importa                                           │
                │        ▼                                                   │
                │ core/ gasolineras_core ──► MITECO · OSRM · Nominatim       │
                └────────────────────────────────────────────────────────────┘

                ┌──────────────────────── OBJETIVO ─────────────────────────┐
 Navegador ───► │ web/ (Next.js, Vercel)                                      │
                │        │ HTTP/JSON (tipos generados del OpenAPI)           │
                │        ▼                                                   │
                │ api/ (FastAPI, Cloud Run) ── caché MITECO, rate-limit       │
                │        │ importa                                           │
                │        ▼                                                   │
                │ core/ gasolineras_core ──► MITECO · OSRM · Nominatim       │
                └────────────────────────────────────────────────────────────┘
```

Regla de dependencias: `web → api → core`. Nunca al revés, y `core` nunca importa una interfaz (ADR 0003).

## El motor (`core/`)

Pipeline de una búsqueda (detalle de módulos en `core/README.md`):

1. **Precios**: `fetch_gasolineras()` descarga unas 12.000 estaciones del MITECO → `parse_miteco_records()` limpia (coma decimal, precios imposibles, sin coordenadas). Respaldo: `fallback_miteco.parquet` con su antigüedad real; los proxies públicos solo los usa Streamlit (la API no). La conexión directa necesita un cifrado TLS heredado (ADR 0007). La API guarda el catálogo en memoria 30 min para todos los usuarios (`api/.../catalogue.py`).
2. **Ruta**: GPX (`load_gpx_track`) u origen/destino (`get_route_from_text`: Nominatim → OSRM) → `LineString` WGS84 → `validate_gpx_track` (España, ≤ 50.000 puntos) → `simplify_track` (RDP).
3. **Corredor**: `build_route_buffer` (UTM 30N, metros) + `build_stations_geodataframe` (índice R-Tree) → `spatial_join_within_buffer`.
4. **Selección**: `filter_cheapest_stations` (Top-N global + la más barata por tramo de X km) o `filter_all_stations_on_route` (España Vaciada, corredor de 500 m). Añade `precio_seleccionado` y `km_ruta`.
5. **Extras**: desvíos reales OSRM (`enrich_stations_with_osrm`), radar de autonomía (`calculate_autonomy_radar`), exportación (`generate_google_maps_url`, `enrich_gpx_with_stops`).

## La API (`api/`)

Capa HTTP fina sobre el core; contrato en `api/openapi.json`. Flujo típico de la web:

| Paso | Endpoint | Notas |
|---|---|---|
| Ruta | `POST /route/text` · `POST /route/gpx` | Track validado en GeoJSON |
| Combustibles | `GET /fuels` | Identificadores estables + nombre en español |
| Búsqueda | `POST /search` | Gasolineras, km en ruta, ahorro, radar de autonomía y antigüedad de los precios |
| Desvíos | `POST /detours` | OSRM, en una segunda llamada (es lento); parcial si OSRM se satura |
| Exportar | `POST /export/gmaps-url` · `POST /export/gpx` | Enlace de Maps; GPX con paradas |
| Salud | `GET /health` | Estado y antigüedad de los precios; nunca descarga |

Piezas propias: `PriceCatalogue` (precios del MITECO en memoria, 30 min, para todos los usuarios), `ratelimit.py` (cupos por IP) y `logging_config.py`. Imagen: `Dockerfile` en la raíz.

## Sistemas de referencia

- `EPSG:4326` (WGS84, grados): entrada GPX, APIs externas y salida a mapas.
- `EPSG:25830` (ETRS89 / UTM 30N, metros): buffers, distancias y spatial joins. Válido en la península y Baleares; en Canarias distorsiona un 2–3 % (deuda conocida).

## Calidad

| Barrera | Dónde |
|---|---|
| Lint + formato (ruff) | Hook automático al editar + CI |
| Tipos (pyright) | CI |
| Tests sin red (pytest) | CI; snapshot del MITECO en `core/tests/fixtures/` |
| `requirements.txt` legacy al día | CI (`scripts/verify.sh`) |
| Smoke test de la app | `./scripts/verify.sh --smoke` (manual; usa red) |
