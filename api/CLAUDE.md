# api/ — API HTTP `gasolineras_api` (FastAPI)

Expone el motor `gasolineras_core` por HTTP para la web (`web/`, Next.js). Stack y motivos: ADR 0001. Alojamiento: ADR 0002 (contenedor Docker, Cloud Run o Render, arranque en frío).

## Reglas

- **Capa fina**: aquí solo hay HTTP (validación, serialización, caché, límites). La lógica de negocio vive en `core/`; si falta algo, se añade allí con su test, nunca se duplica aquí.
- Dependencias: `web → api → core`. `core` no puede importar nada de `api`.
- **El OpenAPI es el contrato** (la web genera sus tipos a partir de él): cada endpoint con `response_model` Pydantic, con `tags` y nombres de campo estables. Está versionado en `api/openapi.json` (`./scripts/export-openapi.sh`; `verify.sh` falla si no está al día). Cambiar un campo es un cambio de contrato: dilo en el PR.
- Fábrica `create_app()` en `main.py`; los tests construyen su propia app con `TestClient(create_app())` y simulan las funciones del core con `monkeypatch` (ver `tests/test_route.py`).
- Servicios externos (MITECO, OSRM, Nominatim): timeout, degradación elegante y uso honesto (User-Agent identificable, caché, rate-limit) — ADR 0005. El limitador y las cachés viven en el core (`gasolineras_core.http_utils`) para que también los use la app Streamlit.
- **Códigos de error** (siempre `{"detail": "mensaje en español para el usuario"}`, declarados en `responses=` con `ErrorResponse`):
  - `400`: la entrada es válida, pero no se puede atender (lugar no encontrado, sin ruta por carretera, GPX inválido, fuera de España).
  - `413`: archivo demasiado grande.
  - `422`: el cuerpo no cumple el esquema (lo genera FastAPI; `detail` es una lista).
  - `503`: un servicio externo está caído o saturado.
  - Nunca un `500` sin explicar.
- **Todo endpoint nuevo declara su cupo** (`ratelimit.py`): `dependencies=[Depends(rate_limited("external"))]` si llama a Nominatim u OSRM, `"default"` si no, y `responses=RATE_LIMIT_RESPONSE`. Solo `/health` va sin límite. Detrás de un proxy (Cloud Run) hay que definir `GASOLINERAS_TRUSTED_PROXY_HOPS=1`; si no, todos los usuarios compartirían la IP del proxy.
- Los routers van en `routers/` (uno por recurso); los modelos públicos, en `schemas.py`. Las geometrías se devuelven en GeoJSON (`[lon, lat]`, WGS84).
- **Precios**: siempre a través de `PriceCatalogue` (`catalogue.py`, en `app.state.catalogue`): una descarga cada 30 min para todos, sin proxies, y si el MITECO cae se conservan los últimos datos. Toda respuesta con precios debe incluir su antigüedad (`price_freshness`: fresh ≤ 30 min, stale ≤ 24 h con aviso, very_stale > 24 h con aviso fuerte). Nunca se deja al usuario sin resultados por antigüedad.
- **Tests sin red** en `api/tests/`: simula el core o `requests.get` con `monkeypatch`. Los que usen red, con `@pytest.mark.network`.
- Mensajes de error dirigidos al usuario, en español; identificadores y código, en inglés (ADR 0004).
- Logs con `logging.getLogger(__name__)`, nunca `print()`.

## Comandos (desde la raíz)

```bash
uv run uvicorn gasolineras_api.main:app --reload   # http://127.0.0.1:8000/docs
uv run pytest -q api/tests
docker build -t gasolineras-api . && docker run -p 8080:8080 gasolineras-api   # imagen de producción (Dockerfile en la raíz)
```

Variables de entorno: `PORT` (8080 en Docker), `GASOLINERAS_TRUSTED_PROXY_HOPS` (1 detrás de Cloud Run), `GASOLINERAS_LOG_LEVEL` (INFO), `GASOLINERAS_DATA_DIR` (`/tmp` en Docker: copia de respaldo del MITECO).
