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

Hecho cuando iguala la funcionalidad de la app Streamlit **con el mismo acabado en el ordenador y en el móvil** (decisión del 2026-10-16: los dos igual de importantes; el modo sin conexión pasa a después del lanzamiento). **Plan completo: [`docs/web/plan.md`](web/plan.md) · diseño: [`docs/web/diseno.md`](web/diseno.md) · stack: ADR 0008.**

> **Retomar aquí (2026-10-16)**: hechos los puntos 1–8. API en Render (https://gasolineras-api-kwnx.onrender.com) y web de pruebas en Vercel (https://gasolineras-web.vercel.app; cada PR, con vista previa). Ordenador y móvil valen lo mismo: cada pantalla se hace para los dos tamaños a la vez ("Listón de calidad" en `docs/web/plan.md`). Flujo aprobado: maquetas en `docs/web/maquetas/flujo/` y reglas en `docs/web/diseno.md` → "Flujo aprobado". **Siguiente tarea: el punto 9 (hoja de ruta: paradas guardadas en el dispositivo, botón "Hoja de ruta" en "Tu ruta", roadbook, imprimir o PDF, Google Maps y GPX), según `Escritorio-HojaDeRuta` y `Movil-HojaDeRuta`.** Notas:
> - La pantalla de la ruta está en `web/src/app/ruta/route-results.tsx` (una sola estructura: panel + mapa en el ordenador, hoja deslizable en el móvil). Las paradas viven en memoria hasta el punto 9. Capturas para revisar: `uvx --from playwright python scripts/screenshots.py`.
> - El OSRM público a veces limita las peticiones desde Render: `/detours` devuelve `complete: false`. La web debe volver a pedir solo los desvíos que falten, tras una pausa.
> - Para probar la web contra la API publicada: `NEXT_PUBLIC_API_URL=https://gasolineras-api-kwnx.onrender.com ./scripts/pnpm -C web dev`.

- [x] Planificación con el propietario: disposición, alcance, estilo y API en Render (`docs/web/plan.md`)
- [x] Dirección visual aprobada (mezcla de A y C, sin pastel, paradas en el centro y autonomía opcional) y maquetas en `docs/web/maquetas/`
- [x] **Acción del propietario**: crear la cuenta gratuita de Render (2026-10-16)
- [x] 1. API publicada en Render: https://gasolineras-api-kwnx.onrender.com (`render.yaml`, Fráncfort, se redespliega sola). Comprobado: precios directos del MITECO, ruta/búsqueda/desvíos, CORS y límite por IP (`TRUSTED_PROXY_HOPS=3`, verificado con cabeceras falseadas)
- [x] 2. `web/` con Next.js 16 + TypeScript 6 estricto + pnpm 12; Node 24 propio en `.tools/` (`scripts/setup-node.sh`, `scripts/pnpm`); `web/CLAUDE.md`; `verify.sh` y CI cubren la web (lint, tipos, formato, tests, build); dependencias con ≥ 7 días de antigüedad y scripts de instalación bloqueados
- [x] 3. Sistema de diseño en código: tokens claro/oscuro en `globals.css` (paleta de Tailwind desactivada; un test impide colores sueltos), fuentes con `next/font`, componentes base (botones, hito, placa de precio, fila de gasolinera, resumen, frescura de precios), formato en español y catálogo en `/diseno`
- [x] 4. Cliente de la API: tipos generados desde `api/openapi.json` (comprobados en `verify.sh`), `openapi-fetch` + TanStack Query (reintenta solo fallos transitorios), errores en español y aviso de servidor despertando / no disponible con "Reintentar"
- [x] 5. Inicio y formulario según la maqueta: origen/destino (intercambiar) o GPX (guardado en IndexedDB), combustibles desde `/fuels`, "Más opciones" plegado con la autonomía opcional; la búsqueda pasa a la URL de `/ruta` (nuqs, nombres en español). `/ruta` es provisional hasta los puntos 6–7
- [x] 6. Mapa: MapLibre + OpenFreeMap con estilo propio a partir de los tokens (claro/oscuro), ruta con halo, origen/destino, placas de precio en tres tonos, hitos de las paradas, centrar desde la lista y "Ver toda la ruta"; carga diferida. `/ruta` ya pide la ruta (texto, GPX o demo con el nuevo `GET /route/demo`) y la búsqueda
- [x] 7a. Sugerencias de lugares: `GET /places/suggest` (Photon, España, ciudades primero) y `/route/text` con el punto elegido; inicio a dos columnas con solo origen, destino y combustible; un lugar que no aparece se avisa en su campo con alternativas. Las demás opciones (distancia, 24 h, autonomía…) se quitaron del inicio y vuelven como filtros en el 7b
- [x] 7b. Ruta como sitio de trabajo (`Escritorio-Ruta`, `Movil-Resultados`): búsqueda editable (cabecera en el ordenador, diálogo "Cambiar" en el móvil), filtros al momento en la URL (desvío, 24 h, "Ver también las de paso", autonomía con avisos), resumen, orden por km o precio, unas 8 recomendadas (4 más baratas + la más barata de cada sexto de ruta) y el resto bajo "Ver las N", nombres y horarios legibles, "Tu ruta" siempre a la vista (paradas en memoria hasta el 9) y resaltado lista → mapa. API: `include_others` / `other_stations`
- [x] 7c. Mapa: placas solo en las recomendadas (y paradas o la elegida), las demás como puntos que se pueden tocar, placas que se tapan pasan a punto (queda la más barata), zoom y leyenda en el ordenador. Script de capturas `scripts/screenshots.py` (móvil y ordenador, claro y oscuro)
- [x] 7. (resumen) Resultados en los dos tamaños: panel + mapa en el ordenador (`D-Escritorio`), hoja deslizable en el móvil (`D-Resultados`), pestañas de orden, resumen, lista ↔ mapa con ratón, teclado y toque; script de capturas (390 × 844 y 1440 × 900, claro y oscuro)
- [x] 8. Desvíos reales en segundo plano (recomendadas, paradas y ficha abierta; reintenta solo los que faltan con pausas de 4 y 12 s, máximo 3 intentos) con la pestaña "Por desvío"; ficha de gasolinera (`Escritorio-Ficha`, `Movil-Ficha`) en el panel o la hoja, en la URL (`gasolinera=`), con anterior/siguiente por km, desvío en km y minutos, horario, ahorro, siguiente recomendada, "Añadir parada" y "Cómo llegar" (Google Maps)
- [ ] 9. Hoja de ruta: paradas en IndexedDB, "Tu ruta", roadbook, imprimir o PDF, exportar a Maps/GPX y autonomía opcional (diseñar antes la versión de ordenador)
- [ ] 10. **Opciones avanzadas** (aprobadas por el propietario el 2026-10-16): sección plegada "Opciones avanzadas" junto a los filtros, recordada en el dispositivo y con una etiqueta discreta si hay algo activo. Una idea por PR:
  - [ ] 10a. Planificar mis repostajes: con la autonomía (o depósito y consumo), con cuánto se sale y la reserva mínima, propone las paradas más baratas sin bajar nunca de la reserva y las pone en "Tu ruta" (editables)
  - [ ] 10b. "Abierta cuando pases": con la hora de salida y los tiempos de OSRM, marca las que estarán cerradas al pasar (mejor que "Solo 24 h")
  - [ ] 10c. Mis descuentos: el usuario escribe sus descuentos por marca (cént/L o %); se ordena y recomienda por el precio que pagará. Sin inventar descuentos oficiales
  - [ ] 10d. "Solo las de mi lado": lado de la carretera según el sentido de la marcha, calculado con la geometría de la ruta (el campo `Margen` del MITECO va según el kilometraje de la carretera). Validar con casos reales antes de mostrarlo
  - [ ] 10e. Pequeñas: excluir marcas, número de recomendadas y GPX con waypoints detallados (precio y horario)
- [ ] 11. Inicio: "Editar" con el formulario relleno, y revisión visual completa (los dos tamaños, claro y oscuro)
- [ ] 12. Páginas legales (aviso legal, privacidad, fuentes) y SEO
- [ ] 13. Cierre: e2e Playwright de la demo en los dos tamaños, axe, presupuesto de rendimiento y lista de paridad completa
- [x] **Acción del propietario**: cuenta de Vercel y app de Vercel en GitHub (2026-10-16). Web de pruebas en https://gasolineras-web.vercel.app (sin indexar): `main` se publica solo y cada PR tiene vista previa (`web/vercel.json`, `web/CLAUDE.md`)

## Fase 3 — Lanzamiento

- [ ] Lanzamiento: la web ya está en Vercel y la API en Render (ADR 0002); falta abrirla a buscadores (`SITE_INDEXABLE=true`) y, si hay dominio propio, añadirlo a `GASOLINERAS_CORS_ORIGINS`
- [ ] Monitorización básica de errores y disponibilidad
- [ ] Periodo en paralelo con Streamlit; después, retirar `legacy/streamlit/`
- [ ] Después del lanzamiento: PWA y hoja de ruta sin conexión (Serwist, ADR 0008)

## Fase 4+ — Crecimiento (sin fecha)

Ahorro en euros según los litros que repostas (decisión C de `docs/web/revision-ux.md`: posible, no de momento) · Dominio propio y SEO · cuentas de usuario (rutas y vehículos guardados) · monetización. Se decidirá con un plan de monetización.

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
| Botón "Hoja de ruta" | "Tu ruta" aún no abre la hoja de ruta | Punto 9 |
| Camino del desvío en el mapa | La maqueta `Escritorio-Ficha` dibuja el desvío; `/detours` solo devuelve km y minutos. Haría falta devolver la geometría (OSRM ya la calcula) | Cuando se pula la ficha |
| Desvíos de "Ver todas" | Solo se piden para las recomendadas, las paradas y la ficha abierta (el OSRM público no aguanta cientos); en "Ver todas", las demás salen sin desvío | Si molesta: pedirlos al hacer scroll |
| Parámetros `top` y `tramo` de la URL | Ya no se usan (las recomendadas se calculan solas); se aceptan para no romper enlaces antiguos. Quitarlos del parser cuando no haya enlaces viejos | Fase 3 |
| "Editar" no rellena el formulario | Desde `/ruta`, "Editar" vuelve al inicio con el formulario vacío; debería traer la búsqueda de la URL | Punto 10 (o el 7, con el buscador de la cabecera del ordenador) |
| Python de Streamlit Cloud | Streamlit Cloud ejecuta la app con **Python 3.11**; `verify.sh --smoke` usa el Python del proyecto. Tras un cambio del core, la app se reinicia y alguna vez Streamlit Cloud falla al hacerlo ("Oh no. Error running app", sin error de Python en el registro): se arregla con "Reboot app" en su panel (pasó el 2026-10-16). Si se repite, valorar fijar 3.11 en la prueba de humo | Hasta retirar Streamlit (Fase 3) |
| Tamaño máximo del cuerpo JSON | La API no limita el tamaño de las peticiones JSON (el track admite hasta 50.000 puntos). Cloud Run corta en 32 MB; en otro alojamiento habría que limitarlo | Fase 3 |
| Tramos de 0 km en el radar | Gasolineras contiguas generan tramos de 0 km (igual que en Streamlit). La web puede agruparlos al pintarlos | Fase 2 |
