# 0005 — Uso responsable de MITECO, OSRM y Nominatim

- **Estado**: Aceptada. Implementada en la Fase 1 (2026-10-15): puntos 1–4 y 6 en el core y la API. El punto 5 (salida de OSRM) queda para cuando haya tráfico (Fase 3+).
- **Fecha**: 2026-10-15

## Contexto

La app depende de tres servicios públicos gratuitos:

| Servicio | Para qué | Problema actual |
|---|---|---|
| API REST del MITECO | Precios y estaciones (fuente oficial) | Falla a veces; se usan proxies públicos de terceros como respaldo |
| Nominatim / Photon (OSM) | Texto → coordenadas | Se envía un User-Agent falso de Chrome; la [política de Nominatim](https://operations.osmfoundation.org/policies/nominatim/) exige identificarse, máximo 1 petición por segundo y cachear resultados |
| OSRM público (`routing.openstreetmap.de`, `router.project-osrm.org`) | Ruta por carretera, desvíos, GPX con paradas | Son servidores de demostración, no para uso en producción; se hacen muchas peticiones por búsqueda (2 por estación para los desvíos) |

Como app de uso personal pasaba desapercibida; como web pública, puede provocar bloqueos y es incorrecto con quien mantiene esos servicios.

## Decisión

1. **Identificarse siempre**: User-Agent propio (`GasolinerasEnRuta/<versión> (+URL o email de contacto)`). Nunca suplantar navegadores.
2. **Cachear**: catálogo del MITECO (TTL 30 min, compartido por todos los usuarios en la API); geocodificación (por texto normalizado, larga duración); rutas OSRM (por coordenadas redondeadas).
3. **Limitar**: rate-limit propio hacia Nominatim (≤ 1 petición/s) y concurrencia acotada hacia OSRM; límite por cliente en la API.
4. **Degradar con elegancia**: si un servicio falla, la búsqueda sigue con lo disponible (sin desvíos, con datos de respaldo indicando su antigüedad).
5. **Plan de salida para OSRM**: cuando haya tráfico o monetización, OSRM propio con el extracto de España de OSM o un proveedor con plan comercial.
6. **Proxies públicos del MITECO**: retirarlos en la API (con el catálogo cacheado en el servidor ya no hacen falta) o sustituirlos por un respaldo propio.

## Alternativas consideradas

- **Proveedores comerciales desde el principio** (Google Maps, Mapbox, OpenRouteService): planes gratuitos limitados y condiciones restrictivas; prematuro con coste 0 €.
- **Seguir como hasta ahora**: riesgo de bloqueo justo cuando la web empiece a tener usuarios.

## Consecuencias

- La API necesita una capa de caché (en memoria para empezar; Redis gratuito si hace falta).
- La geocodificación en vivo mientras se escribe (autocompletado) queda **fuera** con Nominatim: su política lo prohíbe. Si se quiere, Photon o un proveedor dedicado.
- Hay que tener una URL o un email de contacto público para el User-Agent.
