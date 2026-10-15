# Roadmap

Objetivo: convertir la app Streamlit en una **web profesional** (FastAPI + Next.js) sin perder funcionalidad, con coste de alojamiento 0 € hasta tener un plan de monetización.

**Fase actual: 1 — API** · Última actualización: 2026-10-15

> Cómo usar este archivo: cada sesión empieza leyendo la fase actual y termina marcando lo hecho y anotando la deuda nueva. Las decisiones de arquitectura van en `docs/decisions/`, no aquí.

---

## Fase 0 — Cimientos ✅

Estructura, documentación y barreras de calidad. Sin cambios visibles para el usuario.

- [x] Corrección de bugs de la auditoría inicial (commit `27819a2`)
- [x] Monorepo con workspace uv: `core/` (paquete) + `legacy/streamlit/` — ADR 0003
- [x] `CLAUDE.md` raíz y por carpeta; ADRs 0001–0005
- [x] Tests offline del MITECO con snapshot; 32 tests sin red
- [x] pyright (modo `basic`) en 0 errores
- [x] `scripts/verify.sh` + CI en GitHub Actions
- [x] Hook de formateo automático + skills `/verificar` y `/nueva-funcionalidad`
- [x] Streamlit Cloud apunta a `legacy/streamlit/app.py`
- [x] Protección de `main` en GitHub: PR obligatorio, CI "Lint, tipos y tests" en verde, rama al día; también para administradores
- [x] Licencia propietaria (todos los derechos reservados), alineada en `LICENSE` y `pyproject.toml` — ADR 0006

## Fase 1 — API (FastAPI)

Exponer el motor como API HTTP. Hecho cuando la API reproduce los resultados de la app actual y tiene tests.

- [x] `api/` como miembro del workspace; `api/CLAUDE.md` (esqueleto con `create_app()` y `GET /health` básico)
- [ ] Contrato: esquemas Pydantic de petición/respuesta; OpenAPI publicado (en curso: `schemas.py` crece con cada endpoint)
- [x] `POST /route/text` (origen/destino → track), `POST /route/gpx` (subida) — track en GeoJSON; errores 400/413/503
- [x] `POST /search` (track + combustible + filtros → estaciones, radar de autonomía) y `GET /fuels` — lógica en `core/optimizer/search.py`; mismas gasolineras y precios que Streamlit en la demo de Gredos (comprobado con datos reales)
- [x] `POST /detours` (desvíos OSRM, con límite de concurrencia): máx. 3 peticiones simultáneas a OSRM en todo el proceso, caché de 24 h, resultados parciales con `complete: false` si OSRM se satura
- [x] `POST /export/gpx` y `POST /export/gmaps-url` (POST en vez de GET: así las coordenadas no van en la URL de la API) — GPX con waypoints y track desviado por cada parada (OSRM, bajo el límite global)
- [x] Caché del catálogo MITECO en memoria (TTL 30 min, descarga inicial en segundo plano, sin proxies) + `GET /health` con antigüedad de los datos (fresh / stale > 30 min / very_stale > 24 h)
- [x] Uso honesto de Nominatim/OSRM: User-Agent identificable, caché de geocodificación y de rutas, ≤1 pet./s a Nominatim y Photon — ADR 0005 (en el core: también lo usa Streamlit)
- [x] Límite de peticiones por cliente en la API: 10/min en lo que usa OSM (`/route/text`, `/detours`, `/export/gpx`) y 60/min en el resto; 429 con `Retry-After`. IP real tras proxies con `GASOLINERAS_TRUSTED_PROXY_HOPS`
- [ ] Tests de la API (TestClient) sin red
- [x] Dockerfile de la API (multi-etapa con uv, usuario sin privilegios, `PORT` configurable); el CI construye la imagen y comprueba `/health` en cada PR

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
| Track completo de ida y vuelta | `/route/*` devuelve el track entero (hasta 50.000 puntos, ~1 MB) y `/search` lo recibirá de vuelta. Valorar devolver uno simplificado o un id de ruta en el servidor | Al diseñar `/search` |
| Photon lento | Como respaldo de Nominatim llega a tardar ~14 s; tiene el doble de timeout (10 s) | Vigilar |
| Servidor demo de OSRM | `routing.openstreetmap.de` / `router.project-osrm.org` no son para producción | Fase 1–3 (ADR 0005) |
| Proxies públicos para el MITECO | Dejaron de funcionar el 2026-10-15 (`corsproxy.io` exige clave; los otros dan 522). Solo quedan en Streamlit, que ya descarga directo (ADR 0007); si el MITECO falla, se pierden ~15 s probándolos. Quitarlos si siguen muertos | Próximo arreglo en Streamlit o Fase 3 |
| Fecha oficial del MITECO | La respuesta trae `Fecha` (hora de publicación); usamos la hora de descarga. Valorar mostrar la oficial | Al diseñar `/search` |
| UTM 30N en Canarias | Distorsión del 2–3 % en distancias (Canarias está en el huso 28) | Cuando haya usuarios allí |
| `folium_map.py` en `core` | Es presentación, no lógica; desaparece con Streamlit | Fase 3 |
| `print()` como log | Ya no queda en el camino de búsqueda de la API; sí en `cli.py` y `folium_map.py` (se van con Streamlit) | Continuo |
| pyright en modo `basic` | Subir a `standard` (~120 avisos, sobre todo tipos de pandas) | Fase 1 |
| PWA de Streamlit | `.streamlit/static/` no se sirve (falta `enableStaticServing` y la carpeta `static/` junto al script) | No arreglar: la PWA se hace en `web/` |
| `uv.lock` único compartido | Las dependencias de `api/` (y las de desarrollo) pueden mover versiones de la app legacy en producción (p. ej. pydantic 2.14 → `typing-extensions` 4.16; `httpx2` → `idna` 3.20). Revisar el diff de `legacy/streamlit/requirements.txt` en cada PR y pasar `--smoke` | Hasta retirar Streamlit (Fase 3) |
| `km_ruta` con dos métodos (solo Streamlit) | La API ya usa un único método (`route_positions_km`: ruta original, longitud geodésica). Streamlit sigue midiendo el ranking sobre el track simplificado (~2,5 % menos) | Se va con Streamlit (Fase 3) |
| Lógica de búsqueda duplicada | `search_stations` (core) replica el pipeline de `legacy/streamlit/app.py`; Streamlit no se migra por estar congelada | Se va con Streamlit (Fase 3) |
| GPX exportado sin altitud ni horas | `/route/gpx` solo devuelve lon/lat, así que el GPX exportado pierde la altitud y los tiempos del original | Si los usuarios lo piden: guardar el GPX original o devolver la altitud |
| Tramos de 0 km en el radar | Gasolineras contiguas generan tramos de 0 km (igual que en Streamlit). La web puede agruparlos al pintarlos | Fase 2 |
