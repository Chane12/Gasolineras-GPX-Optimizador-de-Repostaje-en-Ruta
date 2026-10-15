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

1. **Precios**: `fetch_gasolineras()` descarga unas 12.000 estaciones del MITECO → `parse_miteco_records()` limpia (coma decimal, precios imposibles, sin coordenadas). Respaldo: proxies públicos → `fallback_miteco.parquet`.
2. **Ruta**: GPX (`load_gpx_track`) u origen/destino (`get_route_from_text`: Nominatim → OSRM) → `LineString` WGS84 → `validate_gpx_track` (España, ≤ 50.000 puntos) → `simplify_track` (RDP).
3. **Corredor**: `build_route_buffer` (UTM 30N, metros) + `build_stations_geodataframe` (índice R-Tree) → `spatial_join_within_buffer`.
4. **Selección**: `filter_cheapest_stations` (Top-N global + la más barata por tramo de X km) o `filter_all_stations_on_route` (España Vaciada, corredor de 500 m). Añade `precio_seleccionado` y `km_ruta`.
5. **Extras**: desvíos reales OSRM (`enrich_stations_with_osrm`), radar de autonomía (`calculate_autonomy_radar`), exportación (`generate_google_maps_url`, `enrich_gpx_with_stops`).

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
