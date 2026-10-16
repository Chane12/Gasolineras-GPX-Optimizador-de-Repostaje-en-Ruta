# 0002 — Alojamiento a 0 € hasta monetizar

- **Estado**: Aceptada
- **Fecha**: 2026-10-15

## Contexto

El proyecto no genera ingresos todavía. El propietario quiere coste 0 € hasta tener un plan de monetización. El backend necesita Python con GeoPandas (~300–400 MB de RAM con el catálogo de unas 12.000 estaciones cargado) y el frontend es Next.js.

## Decisión

- **Web (Next.js)**: Vercel, plan gratuito.
- **API (FastAPI)**: Google Cloud Run, plan gratuito (escala a cero; arranque en frío de unos segundos). Requiere registrar una tarjeta, aunque no cobra dentro del límite gratuito.
- **Alternativa sin tarjeta**: Render, plan gratuito (arranque en frío de unos 50 s tras inactividad).
- **Mientras dure la transición**: la app Streamlit sigue en Streamlit Community Cloud.
- La API debe empaquetarse como **contenedor Docker estándar** para poder cambiar de proveedor sin tocar código.

## Alternativas consideradas

- **VPS de 5–15 €/mes**: sin arranques en frío y con control total; se descarta por ahora solo por coste. Es el primer paso cuando haya ingresos.
- **Fly.io / Railway**: ya no tienen un plan gratuito útil.
- **Todo en Vercel (funciones serverless en Python)**: límites de tamaño y de tiempo incompatibles con GeoPandas.

## Consecuencias

- La primera petición tras un rato sin uso será lenta (arranque en frío): el frontend debe mostrar un estado de carga claro y la API debe arrancar rápido (cargar el MITECO de forma diferida o en segundo plano).
- Sin disco persistente garantizado: el fallback del MITECO va a `GASOLINERAS_DATA_DIR` (p. ej. `/tmp`) y puede perderse en cada arranque.
- **El plan gratuito de Vercel (Hobby) es solo para uso no comercial** (añadido el 2026-10-16, al publicar la web de pruebas). Si se monetiza (Fase 4), habrá que pasar a Vercel Pro (~20 $/mes) o mover la web a otro alojamiento gratuito que admita uso comercial (p. ej. Cloudflare Pages). La web es un Next.js estándar, sin funciones propias de Vercel, para que mudarla sea sencillo.
- Revisar esta decisión cuando haya tráfico real o monetización.
