# Maquetas de la web

Copia de las maquetas aprobadas el 2026-10-15 (lienzo "A + C · Propuesta", https://claude.ai/artifact/HDYpUVSR51qrvub9kdqP2B). Las reglas que fijan están en [`../diseno.md`](../diseno.md).

Cada archivo es una página HTML con estilos en línea (formato del editor de diseño). Se abren directamente en el navegador para ver medidas, colores y textos exactos; las etiquetas propias del editor (`<x-dc>`, `<helmet>`) el navegador las ignora sin problema. **No son código de producción**: la web se construye en `web/` con los componentes y tokens del sistema de diseño.

| Archivo | Pantalla | Tamaño |
|---|---|---|
| `D-Inicio.dc.html` | Inicio y búsqueda | móvil 390 px |
| `D-Resultados.dc.html` | Resultados: mapa + "Elige tus paradas" + barra "Tu ruta" | móvil 390 × 844 |
| `D-Gasolinera.dc.html` | Ficha de gasolinera | móvil 390 × 844 |
| `D-Plan.dc.html` | Hoja de ruta | móvil 390 × 844 |
| `D-Noche.dc.html` | Resultados en modo noche | móvil 390 × 844 |
| `D-Escritorio.dc.html` | Escritorio | fluido (referencia: 1440 × 900) |

Los datos (precios, km, desvíos) son de ejemplo.
