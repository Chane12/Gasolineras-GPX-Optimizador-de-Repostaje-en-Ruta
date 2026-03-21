# Gasolineras GPX: Optimizador de Repostaje en Ruta

Optimizador espacial avanzado diseñado para cruzar trazas GPS (GPX) con el catálogo del Ministerio para la Transición Ecológica (MITECO). Calcula las estaciones de servicio óptimas y más baratas en el corredor de tu ruta, evaluando geometría espacial, cálculos de autonomía y costes de desvío real (OSRM).

## Arquitectura

El core de procesamiento está refactorizado en una arquitectura modular, predecible y altamente tipada dentro del directorio `src/`:

```text
src/
├── config.py             # Única fuente de verdad para CRS (WGS84/UTM30N) y constantes
├── ingestion/            # Módulos de adquisición de datos
│   ├── miteco.py         # Descarga y parseo del catálogo MITECO
│   ├── gpx_parser.py     # Carga, validación y simplificación del track GPS
│   └── geocoder.py       # Geocodificación (Nominatim) y enrutamiento baseline (OSRM)
├── spatial/              # Motor GIS (GeoPandas + Shapely)
│   ├── engine.py         # Generación de buffers proyectados y Spatial Joins (R-Tree)
│   └── nearest.py        # Consultas de vecino más cercano optimizadas (cKDTree)
├── optimizer/            # Lógica de negocio y filtrado
│   ├── cheapest.py       # Identificación Top-N, interpolación segmentada
│   ├── autonomy.py       # Análisis de intervalos de riesgo según autonomía
│   └── export.py         # Splicing de tracks GPX, URLs de G.Maps y desvíos OSRM reales
└── visualization/        # Componentes de renderizado
    └── folium_map.py     # Mapas interactivos con capas analíticas
```

## Requisitos del Sistema

*   **Python:** 3.11+
*   **Gestor de Dependencias:** El proyecto utiliza **exclusivamente `uv`** (extremadamente rápido, escrito en Rust) para el control determinista de entornos y aislamiento de paquetes. 

Para instalar `uv` en Linux/macOS:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

*(Nota: Evite usar gestores heredados, el proyecto no utiliza instaladores convencionales ni archivos temporales de requisitos).*

## Quick Start (Instalación)

Con `uv` instalado, clonar y provisionar el entorno es un proceso de 1 segundo:

```bash
# 1. Clonar el repositorio
git clone <URL_DEL_REPOSITORIO>
cd Gasolineras-GPX-Optimizador-de-Repostaje-en-Ruta

# 2. Sincronizar dependencias (Crea un entorno aislado y bloqueado por uv.lock)
uv sync
```

## Uso (Ejecución)

### Interfaz Web (Streamlit)
La UI original interactiva sigue siendo la interfaz principal de exploración:

```bash
uv run streamlit run app.py
```

### CLI (Línea de Comandos)
Para automatización o procesamiento por lotes interactuando directamente con el core de negocio:

```bash
# Ver opciones de ayuda del orquestador:
uv run python main.py --help

# Ejecución por defecto (usa el demo local):
uv run python main.py --gpx sierra_gredos.gpx --fuel "Precio Gasolina 95 E5" --top 10
```

## Desarrollo y Testing

Garantizar la estabilidad frente a refactorizaciones requiere verificación algorítmica y control de calidad estricto sobre el código base.

**Linting y Formateo:**
Para ejecutar el linter (Ruff) sobre la lógica central y las comprobaciones de test:
```bash
uv run ruff check src/ tests/ main.py
```

**Suite de Tests de Regresión (Golden Output):**
Tests intensivos determinan que la estructura modular entrega resultados algorítmicamente idénticos a las pruebas del motor monolítico heredado.
```bash
uv run pytest
```