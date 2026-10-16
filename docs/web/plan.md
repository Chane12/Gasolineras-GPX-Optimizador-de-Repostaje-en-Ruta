# Plan de la web (Fase 2)

Planificado con el propietario el 2026-10-15. El diseño está en [`diseno.md`](diseno.md), el stack técnico en el [ADR 0008](../decisions/0008-web-stack.md) y el avance en [`ROADMAP.md`](../ROADMAP.md).

## Objetivo

Sustituir la app Streamlit por una web profesional, con identidad propia, en la que un motorista **organiza su ruta y elige dónde repostar**. Se considera hecha cuando iguala la funcionalidad de Streamlit, **con el mismo nivel de acabado en el ordenador y en el móvil**. Después se retira Streamlit (Fase 3).

## Decisiones del propietario (2026-10-15)

| Tema | Decisión |
|---|---|
| Disposición en el móvil | **Mapa a pantalla completa + hoja deslizable** (como Google Maps). En escritorio: panel a la izquierda y mapa a la derecha |
| Estilo visual | Mezcla de las direcciones A (señalización vial, hito kilométrico) y C (atlas y roadbook, su tipografía), **sin colores pastel**. Ver `diseno.md` |
| Idea central | **Organizar la ruta con las paradas**. La autonomía es **opcional** y está desactivada por defecto |
| Alcance de la primera versión | **Paridad con Streamlit + hoja de ruta** (exportable e imprimible). Lo demás, después. *Revisado el 2026-10-16: la hoja de ruta sin conexión (PWA) pasa a después del lanzamiento* |
| API para probar en el móvil | Se publica **ya, al principio de la Fase 2, en Render** (plan gratuito, sin tarjeta). El propietario crea la cuenta y da acceso; el despliegue lo hace el agente |
| Exigencia | "Una web cojonuda, profesional": alto nivel de acabado, nada que parezca una plantilla |
| Ordenador y móvil (2026-10-16) | **Los dos son necesarios e igual de importantes**, y los dos muy pulidos. Se prepara la ruta sobre todo en el ordenador y se consulta en ruta con el móvil. Sin prisa: las cosas bien hechas desde el principio |

## Para quién y cuándo

- **Antes del viaje**, en casa, sobre todo en el **ordenador** (también en el móvil): planificar con calma y elegir las paradas.
- **En ruta**, en el **móvil**, con guantes: consultar la hoja de ruta y abrir la navegación. Sin cobertura, de momento, sirven el GPX exportado y la hoja impresa; el modo sin conexión llega después del lanzamiento.

## Pantallas y flujo

```text
Inicio ──buscar──► Resultados (mapa + "Elige tus paradas") ──► Ficha de gasolinera
                         │  barra "Tu ruta" (paradas elegidas)
                         ▼
                   Hoja de ruta ──► Google Maps · GPX
```

| Pantalla | Contenido | Endpoints |
|---|---|---|
| Inicio | Titular, formulario (origen/destino o GPX, combustible, "Más opciones": distancia máxima, solo 24 h, España Vaciada, tramo de seguridad y autonomía opcional), ruta de ejemplo de Gredos, cómo funciona | `GET /fuels`, `POST /route/text`, `POST /route/gpx` |
| Resultados | Mapa con la ruta y las placas de precio. Hoja con el resumen, las pestañas Por km / Por precio / Por desvío y la lista con "+" para añadir parada. Barra "Tu ruta" | `POST /search`, `POST /detours` (en segundo plano) |
| Ficha | Mapa con el desvío, precio, ahorro, desvío, horario, posición en la ruta. Botones "Cómo llegar" y "Añadir parada" | — (datos de `/search` y `/detours`) |
| Hoja de ruta | Trayecto con hitos, roadbook, ahorro estimado, autonomía opcional, exportación | `POST /export/gmaps-url`, `POST /export/gpx` |
| Legales | Aviso legal, privacidad, fuentes de datos (MITECO, OpenStreetMap) | — |

Comportamientos clave:
- **La búsqueda vive en la URL** (origen, destino, combustible y opciones): compartir el enlace es compartir la búsqueda. Un GPX subido no cabe en la URL, así que se guarda en el dispositivo.
- **La hoja de ruta se guarda en el dispositivo** (IndexedDB): paradas, track y precios en el momento de elegirlos, con su fecha. Se puede imprimir o guardar en PDF. (Abrirla sin conexión, con la PWA, llega después del lanzamiento.)
- **Arranque en frío de la API** (Render se duerme tras unos 15 min sin uso y tarda unos 50 s en despertar): la web llama a `/health` en cuanto se abre el inicio. Si tarda, muestra "Despertando el servidor…" en vez de un error.
- **Antigüedad de los precios**: siempre visible (píldora de frescura). Si la API dice `stale` o `very_stale`, el aviso aumenta, según la decisión de producto de la Fase 1.
- **Desvíos**: se piden después de la búsqueda, porque es lento, y se rellenan en la lista según llegan. Si OSRM falla, la lista funciona igual (`complete: false`).

## Paridad con Streamlit (lista de control)

- [ ] Ruta desde texto, desde GPX y con la demo de Gredos
- [ ] Combustible (12 tipos de `/fuels`), distancia máxima, número de resultados, más barata por tramo, solo 24 h, España Vaciada
- [ ] Mapa con la ruta y las gasolineras por precio; centrar el mapa al elegir una de la lista
- [ ] Ranking con precio, km, desvío real, horario y ahorro frente a la más cara
- [ ] Resumen: mejor precio, ahorro y número de gasolineras en la zona
- [ ] Plan de viaje: añadir y quitar paradas, km entre paradas, ahorro estimado
- [ ] Exportar a Google Maps (máximo 9 paradas, con aviso) y GPX con paradas
- [ ] Radar de autonomía (aquí, opcional) con perfiles moto 250 / coche 600 / gran autonomía 900 / manual
- [ ] Compartir la búsqueda por enlace
- [ ] Antigüedad de los precios y aviso si son de respaldo

## Calidad

- **Accesibilidad**:
  - Contraste AA, objetivos de 44 px, foco visible, navegación con teclado.
  - La lista es la vista accesible principal; el mapa la complementa y no es imprescindible.
  - La hoja deslizable también se maneja con teclado.
- **Rendimiento** (móvil en 4G):
  - LCP < 2,5 s.
  - El mapa se carga de forma diferida.
  - Las fuentes se sirven con `next/font` (alojadas en la propia web, sin llamadas a Google en tiempo de ejecución).
- **Privacidad**: sin cookies de seguimiento, así que no hace falta banner de cookies. La analítica, si se quiere, se decidirá después (ver preguntas abiertas).
- **SEO**: el inicio se renderiza en el servidor, con título, descripción y Open Graph propios.
- **Tests**:
  - Componentes con Vitest + Testing Library.
  - Flujo de la demo de punta a punta con Playwright y la API simulada.
  - Comprobación de accesibilidad automática (axe) en el e2e.

> **Revisión de experiencia y flujo (2026-10-16)**: [`revision-ux.md`](revision-ux.md). Guía los puntos 7–9.

## Listón de calidad (ordenador y móvil)

Decisión del propietario (2026-10-16): los dos tamaños valen lo mismo. En la práctica:

- **Cada pantalla se construye a la vez para los dos tamaños**, en el mismo PR. Nada de "ya haremos el escritorio después".
- **Cada PR visual se revisa con capturas** a 390 × 844 (móvil) y 1440 × 900 (ordenador), en claro y en oscuro, contra la maqueta. Las capturas se hacen con `scripts/screenshots.py` (ver `web/CLAUDE.md`).
- **Cosas propias del ordenador**: ratón (al pasar por una fila se resalta su placa en el mapa, y al revés), teclado (moverse por la lista, atajos sencillos) y aprovechar el ancho (más datos por fila, mapa grande).
- **Cosas propias del móvil**: gestos, objetivos de 44 px, la hoja deslizable y uso con una mano.
- **Pantallas sin maqueta de escritorio** (ficha y hoja de ruta): antes de programarlas se diseña su versión de ordenador y el propietario la aprueba.

## Orden de trabajo (un PR por punto)

Hechos: 1–6 (ver `ROADMAP.md`). Desde el punto 7, el orden se revisó el 2026-10-16 para tratar igual ordenador y móvil:

1. **API en Render**: `render.yaml`, variables (`GASOLINERAS_CORS_ORIGINS`, `GASOLINERAS_TRUSTED_PROXY_HOPS=3`) y comprobación de `/health`.
2. **Estructura de `web/`**: Next.js + TypeScript estricto, lint y formato, `web/CLAUDE.md`, job de CI para la web y `verify.sh` ampliado.
3. **Sistema de diseño en código**: tokens de `diseno.md` en Tailwind (claro y oscuro), fuentes y componentes base.
4. **Cliente de la API**: tipos generados desde `api/openapi.json` (comprobados en el CI), `openapi-fetch` + TanStack Query, aviso de servidor despertando y errores en español.
5. **Inicio y formulario**: texto, GPX y demo, combustible, "Más opciones" y estado en la URL.
6. **Mapa**: MapLibre + OpenFreeMap con estilo propio, ruta, placas de precio, hitos de las paradas, centrar y encuadrar.
7. **Resultados en los dos tamaños**:
   - Ordenador: cabecera con buscador, panel a la izquierda y mapa a la derecha (`D-Escritorio`).
   - Móvil: hoja deslizable (`D-Resultados`).
   - Lista con pestañas de orden y resumen de cifras; relación lista ↔ mapa con ratón, teclado y toque.
   - Script de capturas para revisar cada PR en los dos tamaños.
8. **Desvíos y ficha de gasolinera**: desvíos en segundo plano (reintentando solo los que falten) y ficha (`D-Gasolinera`). En el ordenador, la ficha se diseña antes para el panel.
9. **Hoja de ruta**:
   - Paradas guardadas en el dispositivo (IndexedDB) y barra o panel "Tu ruta".
   - Roadbook (`D-Plan`) y versión para imprimir o PDF.
   - Exportar a Google Maps y GPX, y autonomía opcional.
   - En el ordenador, se diseña antes.
10. **Inicio en el ordenador y revisión visual completa**:
    - Inicio a dos columnas, y "Editar" vuelve con el formulario relleno.
    - Repaso de todas las pantallas en los dos tamaños, en claro y en oscuro, contra las maquetas.
11. **Legales y SEO**: aviso legal, privacidad, fuentes y metadatos.
12. **Cierre**: e2e de la demo en los dos tamaños, accesibilidad (axe), presupuesto de rendimiento y la lista de paridad completa.

**Después del lanzamiento**: PWA y hoja de ruta sin conexión (manifest, iconos con el hito y service worker con Serwist, ADR 0008).

## Preguntas abiertas para el propietario

- **Web publicada para pruebas (Vercel)**: hace falta para probar en un móvil real antes de la Fase 3. El propietario crearía una cuenta gratuita en vercel.com y el agente haría el resto. Recomendado antes del punto 7 o durante él.
- **Nombre y dominio**: ¿se mantiene "Gasolineras en Ruta"? El dominio propio llega en la Fase 4, pero el nombre aparece ya en el logo y los metadatos.
- **Analítica**: ¿ninguna, o una sin cookies (por ejemplo Vercel Web Analytics, gratuita)?
- **Aviso legal**: titular y contacto que deben aparecer (obligatorio en España por la LSSI si hay actividad económica).

## Cómo retomar el trabajo

1. Leer [`ROADMAP.md`](../ROADMAP.md): la fase actual es la 2 y la primera tarea sin marcar es la siguiente.
2. Leer este plan, [`diseno.md`](diseno.md) y el [ADR 0008](../decisions/0008-web-stack.md).
3. Respetar el "Listón de calidad": cada pantalla, en los dos tamaños y revisada con capturas.
