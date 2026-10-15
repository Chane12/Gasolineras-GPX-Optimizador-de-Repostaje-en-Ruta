# api/ — API HTTP `gasolineras_api` (FastAPI)

Expone el motor `gasolineras_core` por HTTP para la web (`web/`, Next.js). Stack y motivos: ADR 0001. Alojamiento: ADR 0002 (contenedor Docker, Cloud Run o Render, arranque en frío).

## Reglas

- **Capa fina**: aquí solo hay HTTP (validación, serialización, caché, límites). La lógica de negocio vive en `core/`; si falta algo, se añade allí con su test, nunca se duplica aquí.
- Dependencias: `web → api → core`. `core` no puede importar nada de `api`.
- **El OpenAPI es el contrato** (la web genera sus tipos a partir de él): cada endpoint con `response_model` Pydantic, con `tags` y nombres de campo estables. Cambiar un campo es un cambio de contrato: dilo en el PR.
- Fábrica `create_app()` en `main.py`; los tests construyen su propia app con `TestClient(create_app())`.
- Servicios externos (MITECO, OSRM, Nominatim): timeout, degradación elegante y uso honesto (User-Agent identificable, caché, rate-limit) — ADR 0005. Un fallo externo devuelve un error HTTP claro (502/503/504), nunca un 500 sin explicar.
- **Precios**: no cachear más de 30 min; si se sirven datos de respaldo, la respuesta debe incluir su antigüedad real.
- **Tests sin red** en `api/tests/`: simula el core o `requests.get` con `monkeypatch`. Los que usen red, con `@pytest.mark.network`.
- Mensajes de error dirigidos al usuario, en español; identificadores y código, en inglés (ADR 0004).
- Logs con `logging.getLogger(__name__)`, nunca `print()`.

## Comandos (desde la raíz)

```bash
uv run uvicorn gasolineras_api.main:app --reload   # http://127.0.0.1:8000/docs
uv run pytest -q api/tests
```
