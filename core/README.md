# gasolineras-core

Motor geoespacial de Gasolineras en Ruta. Contiene toda la lógica de negocio y **no depende de ninguna interfaz web**: lo usan la app Streamlit (`legacy/streamlit/`), la CLI y, desde la Fase 1, la API (`api/`).

## Módulos

```text
src/gasolineras_core/
├── config.py           # Única fuente de verdad: CRS, URLs, User-Agent, columnas, límites, rutas de datos
├── http_utils.py       # RateLimiter y TTLCache compartidos por el proceso (uso responsable de servicios, ADR 0005)
├── cli.py              # CLI `gasolineras` (orquestador, sin lógica propia)
├── data/               # Datos empaquetados (GPX de demo Sierra de Gredos)
├── ingestion/
│   ├── miteco.py       # Descarga del MITECO (TLS ADR 0007, proxies opcionales, fallback parquet), limpieza y antigüedad
│   ├── gpx_parser.py   # GPX (archivo o bytes) → track, validación (España, nº de puntos) y simplificación RDP
│   └── geocoder.py     # geocode_place (Nominatim → Photon, ≤1 pet./s, caché) y fetch_road_route (OSRM, caché)
├── spatial/
│   ├── engine.py       # Buffer del corredor en UTM, GeoDataFrame de estaciones, spatial join (R-Tree)
│   └── nearest.py      # Vecino más cercano (KDTree)
├── optimizer/
│   ├── cheapest.py     # Top-N más baratas, más barata por tramo, modo España Vaciada
│   ├── autonomy.py     # Radar de autonomía: tramos entre gasolineras vs. autonomía del vehículo
│   └── export.py       # URL de Google Maps, GPX con paradas (track splicing OSRM), desvíos OSRM
└── visualization/
    └── folium_map.py   # Mapa Folium (lo usan Streamlit y la CLI; la web nueva no)
```

## Flujo del pipeline

1. `fetch_gasolineras(use_proxies=...)` → `MitecoResult(df, fetched_at, from_fallback)`; `price_freshness()` → fresh / stale / very_stale
2. `load_gpx_track()` / `parse_gpx_track()` / `get_route_from_text()` → `LineString` WGS84 → `validate_gpx_track()` → `simplify_track()`
3. `build_route_buffer()` + `build_stations_geodataframe()` → `spatial_join_within_buffer()` (todo en EPSG:25830)
4. `filter_cheapest_stations()` / `filter_all_stations_on_route()` → añade `precio_seleccionado`, `combustible`, `km_ruta`
5. Opcional: `enrich_stations_with_osrm()`, `calculate_autonomy_radar()`, `generate_google_maps_url()`, `enrich_gpx_with_stops()`

## Uso

```bash
uv run gasolineras --help
uv run gasolineras --fuel "Precio Gasolina 95 E5" --top 10 --segment-km 50
```

## Configuración por entorno

| Variable | Por defecto | Uso |
|---|---|---|
| `GASOLINERAS_DATA_DIR` | directorio de trabajo | Dónde se guarda/lee `fallback_miteco.parquet` |
