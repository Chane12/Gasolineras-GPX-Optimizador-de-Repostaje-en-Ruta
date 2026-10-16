# Roadmap

Objetivo: convertir la app Streamlit en una **web profesional** (FastAPI + Next.js) sin perder funcionalidad, con coste de alojamiento 0 € hasta tener un plan de monetización.

**Fase actual: 2 — Web** · Última actualización: 2026-10-15

> Cómo usar este archivo: cada sesión empieza leyendo la fase actual y termina marcando lo hecho y anotando la deuda nueva. Las decisiones de arquitectura van en `docs/decisions/`, no aquí.

---

## Fase 0 — Cimientos ✅

Estructura, documentación y barreras de calidad. Sin cambios visibles para el usuario.

- [x] Corrección de bugs de la auditoría inicial (commit `27819a2`)
- [x] Monorepo con workspace uv: `core/` (paquete) + `legacy/streamlit/` — ADR 0003
- [x] `CLAUDE.md` raíz y por carpeta; ADRs 0001–0005
- [x] Tests offline del MITECO con snapshot; 32 tests sin red
- [x] pyright en 0 errores (modo `standard` desde la Fase 1, también sobre los tests)
- [x] `scripts/verify.sh` + CI en GitHub Actions
- [x] Hook de formateo automático + skills `/verificar` y `/nueva-funcionalidad`
- [x] Streamlit Cloud apunta a `legacy/streamlit/app.py`
- [x] Protección de `main` en GitHub: PR obligatorio, CI "Lint, tipos y tests" en verde, rama al día; también para administradores
- [x] Licencia propietaria (todos los derechos reservados), alineada en `LICENSE` y `pyproject.toml` — ADR 0006

## Fase 1 — API (FastAPI) ✅ (2026-10-15; sin desplegar hasta la Fase 3)

Exponer el motor como API HTTP. Hecho cuando la API reproduce los resultados de la app actual y tiene tests.

- [x] `api/` como miembro del workspace; `api/CLAUDE.md` (esqueleto con `create_app()` y `GET /health` básico)
- [x] Contrato: esquemas Pydantic de petición/respuesta (`schemas.py`); OpenAPI en `/openapi.json` y `/docs`, y versionado en `api/openapi.json` (el CI falla si no está al día)
- [x] `POST /route/text` (origen/destino → track), `POST /route/gpx` (subida) — track en GeoJSON; errores 400/413/503
- [x] `POST /search` (track + combustible + filtros → estaciones, radar de autonomía) y `GET /fuels` — lógica en `core/optimizer/search.py`; mismas gasolineras y precios que Streamlit en la demo de Gredos (comprobado con datos reales)
- [x] `POST /detours` (desvíos OSRM, con límite de concurrencia): máx. 3 peticiones simultáneas a OSRM en todo el proceso, caché de 24 h, resultados parciales con `complete: false` si OSRM se satura
- [x] `POST /export/gpx` y `POST /export/gmaps-url` (POST en vez de GET: así las coordenadas no van en la URL de la API) — GPX con waypoints y track desviado por cada parada (OSRM, bajo el límite global)
- [x] Caché del catálogo MITECO en memoria (TTL 30 min, descarga inicial en segundo plano, sin proxies) + `GET /health` con antigüedad de los datos (fresh / stale > 30 min / very_stale > 24 h)
- [x] Uso honesto de Nominatim/OSRM: User-Agent identificable, caché de geocodificación y de rutas, ≤1 pet./s a Nominatim y Photon — ADR 0005 (en el core: también lo usa Streamlit)
- [x] Límite de peticiones por cliente en la API: 10/min en lo que usa OSM (`/route/text`, `/detours`, `/export/gpx`) y 60/min en el resto; 429 con `Retry-After`. IP real tras proxies con `GASOLINERAS_TRUSTED_PROXY_HOPS`
- [x] Tests de la API (TestClient) sin red: 62 tests; el core, 85 (sin red) + 1 con red
- [x] Revisión final de la fase: CORS para la web (`GASOLINERAS_CORS_ORIGINS`), refresco de precios en segundo plano (nadie espera los ~20 s del MITECO), tiempo máximo en desvíos (45 s) y GPX (30 s), errores 500 explicados en español, gzip (track de la demo: 227 → 66 KB), paridad con Streamlit comprobada también con 24 h, España Vaciada, tramos, radar y GLP
- [x] Dockerfile de la API (multi-etapa con uv, usuario sin privilegios, `PORT` configurable); el CI construye la imagen y comprueba `/health` en cada PR

## Fase 2 — Web (Next.js)

Hecho cuando iguala la funcionalidad de la app Streamlit y la hoja de ruta funciona sin conexión. **Plan completo: [`docs/web/plan.md`](web/plan.md) · diseño: [`docs/web/diseno.md`](web/diseno.md) · stack: ADR 0008.**

> **Retomar aquí (2026-10-16)**: estructura y sistema de diseño en código hechos. Siguiente tarea: el punto 4 (cliente de la API). El punto 1 sigue esperando la cuenta de Render del propietario.

- [x] Planificación con el propietario: disposición, alcance, estilo y API en Render (`docs/web/plan.md`)
- [x] Dirección visual aprobada (mezcla de A y C, sin pastel, paradas en el centro y autonomía opcional) y maquetas en `docs/web/maquetas/`
- [ ] **Acción del propietario**: crear la cuenta gratuita de Render y dar acceso (bloquea el punto 1)
- [ ] 1. API publicada en Render (`render.yaml`, CORS, `TRUSTED_PROXY_HOPS=1`)
- [x] 2. `web/` con Next.js 16 + TypeScript 6 estricto + pnpm 12; Node 24 propio en `.tools/` (`scripts/setup-node.sh`, `scripts/pnpm`); `web/CLAUDE.md`; `verify.sh` y CI cubren la web (lint, tipos, formato, tests, build); dependencias con ≥ 7 días de antigüedad y scripts de instalación bloqueados
- [x] 3. Sistema de diseño en código: tokens claro/oscuro en `globals.css` (paleta de Tailwind desactivada; un test impide colores sueltos), fuentes con `next/font`, componentes base (botones, hito, placa de precio, fila de gasolinera, resumen, frescura de precios), formato en español y catálogo en `/diseno`
- [ ] 4. Cliente de la API: tipos generados desde `api/openapi.json` (comprobados en el CI), TanStack Query y aviso de servidor despertando
- [ ] 5. Inicio y formulario (texto / GPX / demo, combustible, "Más opciones") con la búsqueda en la URL
- [ ] 6. Mapa: MapLibre + OpenFreeMap con estilo propio, ruta, placas de precio e hitos
- [ ] 7. Resultados: hoja deslizable, lista y orden, resumen, desvíos en segundo plano y ficha de gasolinera
- [ ] 8. Hoja de ruta: paradas en IndexedDB, barra "Tu ruta", roadbook, exportar a Maps/GPX y autonomía opcional
- [ ] 9. Escritorio y modo noche; revisión visual contra las maquetas
- [ ] 10. PWA y hoja de ruta sin conexión
- [ ] 11. Páginas legales (aviso legal, privacidad, fuentes) y SEO
- [ ] 12. Cierre: e2e Playwright de la demo, axe, presupuesto de rendimiento y lista de paridad completa

## Fase 3 — Lanzamiento

- [ ] Despliegue: web en Vercel, API en Cloud Run (o Render) — ADR 0002. Variables de la API: `GASOLINERAS_CORS_ORIGINS=<dominio de la web>`, `GASOLINERAS_TRUSTED_PROXY_HOPS=1`
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
| PWA de Streamlit | `.streamlit/static/` no se sirve (falta `enableStaticServing` y la carpeta `static/` junto al script) | No arreglar: la PWA se hace en `web/` |
| `uv.lock` único compartido | Las dependencias de `api/` (y las de desarrollo) pueden mover versiones de la app legacy en producción (p. ej. pydantic 2.14 → `typing-extensions` 4.16; `httpx2` → `idna` 3.20). Revisar el diff de `legacy/streamlit/requirements.txt` en cada PR y pasar `--smoke` | Hasta retirar Streamlit (Fase 3) |
| `km_ruta` con dos métodos (solo Streamlit) | La API ya usa un único método (`route_positions_km`: ruta original, longitud geodésica). Streamlit sigue midiendo el ranking sobre el track simplificado (~2,5 % menos) | Se va con Streamlit (Fase 3) |
| Lógica de búsqueda duplicada | `search_stations` (core) replica el pipeline de `legacy/streamlit/app.py`; Streamlit no se migra por estar congelada | Se va con Streamlit (Fase 3) |
| GPX exportado sin altitud ni horas | `/route/gpx` solo devuelve lon/lat, así que el GPX exportado pierde la altitud y los tiempos del original | Si los usuarios lo piden: guardar el GPX original o devolver la altitud |
| TypeScript 7 (nativo) | La web usa TypeScript 6.0: Next.js aún no tiene probado TS 7. Revisar cuando Next lo soporte oficialmente | Fase 2–3 |
| Tamaño máximo del cuerpo JSON | La API no limita el tamaño de las peticiones JSON (el track admite hasta 50.000 puntos). Cloud Run corta en 32 MB; en otro alojamiento habría que limitarlo | Fase 3 |
| Tramos de 0 km en el radar | Gasolineras contiguas generan tramos de 0 km (igual que en Streamlit). La web puede agruparlos al pintarlos | Fase 2 |
