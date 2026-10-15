# 0004 — Inglés en el código, español en interfaz y docs

- **Estado**: Aceptada
- **Fecha**: 2026-10-15

## Contexto

El código heredado mezcla español e inglés en nombres de funciones, variables, comentarios y commits (`filter_cheapest_stations` junto a `calcular_desvio`, `gdf_survival` junto a `tramos`). El producto es para un público hispanohablante y el propietario trabaja en español.

## Decisión

- **Inglés**: identificadores (funciones, variables, clases, rutas de la API, campos JSON), mensajes de commit y nombres de ramas.
- **Español**: todo texto que vea el usuario final, la documentación (`README`, `CLAUDE.md`, `docs/`), los ADRs y los comentarios que explican reglas de negocio.
- **Código heredado**: no se traduce en masa. Se renombra solo lo que se toca por otro motivo.

## Alternativas consideradas

- **Todo en español**: los nombres de librerías, frameworks y la mayoría de ejemplos están en inglés; mezclar sería inevitable.
- **Todo en inglés**: la documentación la lee sobre todo el propietario, que trabaja en español.

## Consecuencias

- La API (Fase 1) nace con campos en inglés (`price`, `km_on_route`…) y la web traduce a español en la interfaz.
- Las columnas del MITECO (`"Precio Gasoleo A"`, `"Rótulo"`…) son datos externos: se mantienen tal cual dentro de `core` y se mapean a nombres en inglés en la frontera de la API.
