# Roadmap

Objetivo: convertir la app Streamlit en una **web profesional** (FastAPI + Next.js) sin perder funcionalidad, con coste de alojamiento 0 € hasta tener un plan de monetización.

**Fase actual: 1 — API** · Última actualización: 2026-10-15

> Cómo usar este archivo: cada sesión empieza leyendo la fase actual y termina marcando lo hecho y anotando la deuda nueva. Las decisiones de arquitectura van en `docs/decisions/`, no aquí.

---

## Fase 0 — Cimientos ✅ (fusionada: PR #34)

Estructura, documentación y barreras de calidad. Sin cambios visibles para el usuario.

- [x] Corrección de bugs de la auditoría inicial (commit `27819a2`)
- [x] Monorepo con workspace uv: `core/` (paquete) + `legacy/streamlit/` — ADR 0003
- [x] `CLAUDE.md` raíz y por carpeta; ADRs 0001–0005
- [x] Tests offline del MITECO con snapshot; 32 tests sin red
- [x] pyright (modo `basic`) en 0 errores
- [x] `scripts/verify.sh` + CI en GitHub Actions
- [x] Hook de formateo automático + skills `/verificar` y `/nueva-funcionalidad`
- [ ] **Acción manual**: cambiar en Streamlit Cloud el archivo principal a `legacy/streamlit/app.py` (justo al fusionar el PR)
- [ ] **Acción manual**: activar en GitHub la protección de `main` (exigir CI en verde antes de fusionar)
- [ ] **Decisión pendiente (propietario)**: licencia. `LICENSE` es CC BY-NC 4.0 (prohíbe el uso comercial por terceros; además CC no está pensada para software), pero `core/pyproject.toml` declaraba EUPL-1.2. Hay que elegir una y alinearlas antes de monetizar o abrir el código a contribuciones.

## Fase 1 — API (FastAPI)

Exponer el motor como API HTTP. Hecho cuando la API reproduce los resultados de la app actual y tiene tests.

- [x] `api/` como miembro del workspace; `api/CLAUDE.md` (esqueleto con `create_app()` y `GET /health` básico)
- [ ] Contrato: esquemas Pydantic de petición/respuesta; OpenAPI publicado
- [ ] `POST /route/text` (origen/destino → track), `POST /route/gpx` (subida)
- [ ] `POST /search` (track + combustible + filtros → estaciones, radar de autonomía)
- [ ] `POST /detours` (desvíos OSRM, con límite de concurrencia)
- [ ] `POST /export/gpx` y `GET /export/gmaps-url`
- [ ] Caché del catálogo MITECO en memoria (TTL 30 min) + `GET /health` con antigüedad de los datos
- [ ] Uso honesto de Nominatim/OSRM: User-Agent identificable, caché de geocodificación, rate-limit propio — ADR 0005
- [ ] Tests de la API (TestClient) sin red
- [ ] Dockerfile de la API

## Fase 2 — Web (Next.js)

Hecho cuando iguala la funcionalidad de la app Streamlit.

- [ ] `web/` con Next.js + TypeScript estricto; `web/CLAUDE.md`
- [ ] Tipos TypeScript generados desde el OpenAPI de la API (nunca escritos a mano)
- [ ] Formulario de ruta (texto / GPX / demo) y parámetros del vehículo
- [ ] Mapa (MapLibre) con ruta, estaciones coloreadas por precio y zonas de riesgo
- [ ] Ranking / tarjetas móviles, plan de viaje, exportación Maps/GPX, radar de autonomía
- [ ] Móvil primero; accesibilidad básica; PWA
- [ ] Tests de componentes y un test end-to-end (Playwright) del flujo demo

## Fase 3 — Lanzamiento

- [ ] Despliegue: web en Vercel, API en Cloud Run (o Render) — ADR 0002
- [ ] Monitorización básica de errores y disponibilidad
- [ ] Periodo en paralelo con Streamlit; después, retirar `legacy/streamlit/`

## Fase 4+ — Crecimiento (sin fecha)

Dominio propio y SEO · cuentas de usuario (rutas y vehículos guardados) · monetización. Se decidirá con un plan de monetización.

---

## Deuda técnica conocida

Anotar aquí todo lo que se detecte y no se arregle en el momento.

| Tema | Detalle | Cuándo |
|---|---|---|
| Nominatim con User-Agent falso | `geocoder.py` se hace pasar por Chrome; viola la política de uso de Nominatim | Fase 1 (ADR 0005) |
| Servidor demo de OSRM | `routing.openstreetmap.de` / `router.project-osrm.org` no son para producción | Fase 1–3 (ADR 0005) |
| Proxies públicos para el MITECO | `corsproxy.io` y otros reciben los datos; dependencia frágil de terceros | Fase 1 |
| UTM 30N en Canarias | Distorsión del 2–3 % en distancias (Canarias está en el huso 28) | Cuando haya usuarios allí |
| `folium_map.py` en `core` | Es presentación, no lógica; desaparece con Streamlit | Fase 3 |
| `print()` como log | Migrar a `logging` al tocar cada módulo | Continuo |
| pyright en modo `basic` | Subir a `standard` (~120 avisos, sobre todo tipos de pandas) | Fase 1 |
| PWA de Streamlit | `.streamlit/static/` no se sirve (falta `enableStaticServing` y la carpeta `static/` junto al script) | No arreglar: la PWA se hace en `web/` |
| `uv.lock` único compartido | Las dependencias de `api/` (y las de desarrollo) pueden mover versiones de la app legacy en producción (p. ej. pydantic 2.14 → `typing-extensions` 4.16; `httpx2` → `idna` 3.20). Revisar el diff de `legacy/streamlit/requirements.txt` en cada PR y pasar `--smoke` | Hasta retirar Streamlit (Fase 3) |
| `km_ruta` con dos métodos | Ranking: longitud UTM del track simplificado; radar: geodésica del original | Unificar en la API |
