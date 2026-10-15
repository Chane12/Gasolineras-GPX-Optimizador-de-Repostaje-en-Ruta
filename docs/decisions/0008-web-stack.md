# 0008 — Stack técnico de la web

- **Estado**: Aceptada
- **Fecha**: 2026-10-15

## Contexto

El ADR 0001 fija Next.js + TypeScript para la web, con tipos generados desde el OpenAPI. Falta concretar las piezas, ahora que hay un diseño aprobado y unos requisitos claros: mapa protagonista con hoja deslizable, hoja de ruta sin conexión, búsqueda compartible por enlace, alojamiento a 0 € (ADR 0002) y una API que puede tardar unos 50 s en despertar.

## Decisión

| Pieza | Elección | Motivo |
|---|---|---|
| Framework | **Next.js (App Router)** + TypeScript `strict` | ADR 0001. El inicio se renderiza en el servidor (SEO) y el resto es interactivo en el cliente |
| Gestor de paquetes | **pnpm** | Rápido, con lockfile estricto y bien soportado en Vercel |
| Estilos | **Tailwind CSS** con los tokens de `docs/web/diseno.md` como tema (claro y oscuro) | Los tokens viven en un solo sitio; no usamos una paleta genérica |
| Componentes accesibles | **Radix UI** (primitivas sin estilo) | Accesibilidad resuelta (diálogos, pestañas, menús) sin imponer un aspecto: la web no debe parecer una plantilla |
| Hoja deslizable | **Vaul** (sobre Radix Dialog) | Gestos táctiles, puntos de anclaje y accesible con teclado |
| Mapa | **MapLibre GL JS** + teselas vectoriales de **OpenFreeMap** con **estilo propio** | Gratis, sin clave ni límites, datos de OpenStreetMap. El estilo propio es parte de la identidad (ADR 0001 ya descartaba Folium) |
| Datos de la API | **openapi-typescript** (tipos desde `api/openapi.json`) + **openapi-fetch** + **TanStack Query** | Tipos que no se escriben a mano, con caché, reintentos y estados de carga |
| Estado en la URL | **nuqs** | La búsqueda queda en la URL, así que compartirla es copiar el enlace |
| Hoja de ruta local | **IndexedDB** (a través de `idb-keyval`) | Persiste sin conexión y aguanta tracks grandes, que en `localStorage` no caben |
| PWA | **Serwist** (service worker) | Mantenido y pensado para Next.js |
| Fuentes | `next/font` con Familjen Grotesk e IBM Plex Mono | Alojadas en la propia web: sin llamadas a Google en tiempo de ejecución, más rápido y mejor para la privacidad |
| Tests | **Vitest** + Testing Library; **Playwright** + **axe** para el e2e, con la API simulada | Rápidos y sin red, igual que en Python |
| Calidad | ESLint + Prettier + `tsc --noEmit` en `verify.sh` y en el CI | El mismo listón que en el backend |

## Alternativas consideradas

- **shadcn/ui completo**: acelera, pero su aspecto por defecto es justo el "estilo web de IA" que el propietario quiere evitar. Usamos las mismas primitivas (Radix) con nuestro propio diseño.
- **Leaflet**: más simple, pero con teselas raster y sin estilo vectorial propio; peor rendimiento y menos control visual.
- **Mapbox GL / Google Maps**: de pago o con condiciones restrictivas a partir de cierto uso. Va contra el ADR 0002.
- **Estado global (Redux/Zustand) para la búsqueda**: la URL y TanStack Query cubren casi todo. Si hace falta algo local más complejo (la hoja de ruta), se hace con un hook sobre IndexedDB.
- **Remix / Astro**: válidos, pero el ADR 0001 ya eligió Next.js y no hay motivo nuevo para cambiar.

## Consecuencias

- `web/` tendrá su propio `CLAUDE.md`, su lockfile de pnpm y un job de CI. `scripts/verify.sh` comprobará también la web.
- Los tipos de la API se regeneran desde `api/openapi.json`, y el CI falla si no coinciden: un cambio de contrato rompe el build de la web en el mismo PR.
- El estilo del mapa (JSON de MapLibre) vive en el repo y forma parte del sistema de diseño.
- OpenFreeMap es un servicio gratuito de terceros. Si cayera o cambiara sus condiciones, el plan B es Protomaps (teselas propias en un archivo estático); el estilo propio se puede portar.
