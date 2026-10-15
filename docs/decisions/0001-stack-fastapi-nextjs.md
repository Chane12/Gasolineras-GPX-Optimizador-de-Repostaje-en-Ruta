# 0001 — Stack de la web: FastAPI + Next.js

- **Estado**: Aceptada
- **Fecha**: 2026-10-15

## Contexto

La app actual es Streamlit: rápida de construir, pero limitada como web pública (cada interacción re-ejecuta el script, el móvil se resuelve con trucos de CSS y JavaScript, no hay SEO, el estado vive en el servidor por sesión). El objetivo es una web "normal y corriente", profesional, que se pueda hacer crecer (cuentas, SEO, monetización). El motor geoespacial (`core/`, Python + GeoPandas) está probado y no debe reescribirse.

## Decisión

- **Backend**: FastAPI (Python) en `api/`, envolviendo `gasolineras_core` sin duplicar lógica.
- **Frontend**: Next.js (React, TypeScript estricto) en `web/`, con mapa MapLibre GL.
- **Contrato**: el OpenAPI que genera FastAPI es la fuente de verdad; los tipos TypeScript del frontend se **generan** a partir de él.

## Alternativas consideradas

- **Seguir con Streamlit y pulirlo**: techo bajo en UX móvil, rendimiento y SEO.
- **FastAPI + HTML/JS sin framework**: menos piezas, pero el frontend crece mal (plan de viaje, mapa interactivo, estados) y la IA rinde mejor con patrones estándar de React.
- **Reescribir todo en TypeScript (Node)**: el ecosistema geoespacial de Python (GeoPandas, Shapely, pyproj) no tiene equivalente igual de maduro; se perdería el motor probado.
- **Django**: más peso del necesario; la web no necesita su ORM ni sus plantillas.

## Consecuencias

- Dos lenguajes en el repo (Python y TypeScript), cada uno con su `CLAUDE.md`.
- Los tipos generados evitan que frontend y backend se desincronicen, un fallo habitual al programar con IA.
- El backend necesita un servidor con Python (no basta un hosting estático): ver ADR 0002.
- MapLibre sustituye a Folium; `visualization/folium_map.py` se retira con Streamlit.
