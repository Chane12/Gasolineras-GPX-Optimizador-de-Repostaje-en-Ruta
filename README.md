# ⛽ Gasolineras en Ruta — Dashboard de Repostaje Inteligente

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![GeoPandas](https://img.shields.io/badge/GeoPandas-0.14%2B-139C5A)](https://geopandas.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Demo en Streamlit Cloud](https://img.shields.io/badge/Demo-Streamlit%20Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://gasolineras-gpx.streamlit.app/)

> **¿Dónde debería parar a repostar en mi próxima ruta?**  
> Esta herramienta cruza tu trayecto real con los precios de combustible en tiempo real del MITECO y te muestra, sobre un mapa interactivo, las gasolineras más baratas de tu corredor de viaje — para que tú mismo diseñes tu plan de repostaje.

---

## 🗺️ El Problema que Resuelve

Cuando conduces una ruta larga en España, elegir _dónde_ repostar puede suponer diferencias de **10–20 €** en el mismo trayecto. Las comparativas genéricas no tienen en cuenta si esa gasolinera barata está realmente en tu camino o a varios kilómetros de desvío.

**Gasolineras en Ruta** resuelve esto con precisión geoespacial:

1. Toma tu ruta GPS real (archivo `.gpx`) o define origen y destino por nombre de ciudad.
2. Construye un corredor de búsqueda configurable alrededor del trayecto (1–15 km).
3. Cruza ese corredor con el catálogo oficial de precios de la **API MITECO** (actualizado cada hora).
4. Te devuelve un **dashboard interactivo** con las N gasolineras más baratas que realmente puedes alcanzar sin desviarte.
5. Tú eliges cuáles añadir a tu **Plan de Viaje** y exportas la ruta a Google Maps o GPX.

---

## ✨ Funcionalidades Principales

### 🔍 Búsqueda de Ruta
- **Modo Texto**: Introduce origen y destino por nombre de ciudad/municipio. Calcula la ruta real con OSRM.
- **Modo GPX**: Sube tu propio track `.gpx` (moto, coche, bicicleta…).
- **Modo Demo**: Ruta de ejemplo Madrid → Valencia (~356 km) para explorar sin subir archivos.

### ⛽ Análisis de Combustible
- Selección de tipo de combustible (Gasolina 95, Diésel, GLP, GNC, GNL, etc.)
- Radio de búsqueda configurable (1–15 km alrededor del trayecto)
- Filtro de Top N gasolineras más baratas
- **Análisis de depósito**: Calcula si llegas al destino con el combustible actual, cuánto necesitas reponer y el ahorro potencial vs. la gasolinera más cara de la zona

### 🛒 Plan de Viaje Manual
- Selecciona gasolineras directamente desde la tabla de ranking
- Añade o elimina paradas de tu Plan de Viaje con un clic
- La tabla del plan calcula automáticamente el **tramo en km** entre cada parada para controlar tu autonomía

### 🗺️ Mapa Interactivo
- Mapa Folium embebido con todos los marcadores de gasolineras
- Haz clic en una fila de la tabla → el mapa se centra automáticamente en esa gasolinera
- **Radar de Autonomía Crítica**: detecta y muestra en rojo los tramos donde podrías quedarte sin combustible según tu autonomía configurada

### 📤 Exportación
- **Google Maps** (modo Texto): genera un enlace directo con todas las paradas de tu Plan de Viaje como waypoints.
- **GPX enriquecido** (modo GPX): descarga tu track original con las gasolineras seleccionadas inyectadas como Waypoints, listo para importar en cualquier GPS/app de navegación.

### 🔗 Compartir por URL
- Los parámetros de búsqueda (combustible, radio, top N, autonomía) se reflejan en la URL para que puedas compartir tu configuración.

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Streamlit)                      │
│  · Texto / GPX / Demo     · Tabla de ranking interactiva    │
│  · Mapa Folium embebido   · Carrito "Mi Plan de Viaje"      │
│  · Radar de Autonomía     · Exportación Google Maps / GPX   │
└───────────────────────┬─────────────────────────────────────┘
                        │
          ┌─────────────▼──────────────┐
          │     Capa de Procesamiento   │
          │  ┌──────────────────────┐  │
          │  │ gpxpy / OSRM API     │  │  ← Lectura de tracks / routing
          │  │ Ramer-Douglas-Peucker│  │  ← Simplificación de geometría
          │  │ Shapely + GeoPandas  │  │  ← Buffer + Spatial Join
          │  │ EPSG:25830 (UTM 30N) │  │  ← Proyección métrica
          │  └──────────────────────┘  │
          └─────────────┬──────────────┘
                        │
          ┌─────────────▼──────────────┐
          │      Fuentes de Datos       │
          │  · API REST MITECO (JSON)   │  ← Precios en tiempo real
          │  · OSRM (routing público)   │  ← Cálculo de rutas por nombre
          │  · Archivo .gpx (usuario)   │  ← Track GPS del viaje
          └────────────────────────────┘
```

### Tecnologías clave

| Componente | Librería | Rol |
|---|---|---|
| UI interactiva | `streamlit` | Frontend web sin JavaScript |
| Análisis geoespacial | `geopandas`, `shapely` | Buffer, spatial join, proyección UTM |
| Simplificación de ruta | Ramer-Douglas-Peucker (`gpxpy`) | Reducir vértices de la polilínea GPX |
| Visualización | `folium` | Mapas interactivos HTML |
| Proyección / distancias | `pyproj` | Cálculos geodésicos precisos |
| Datos de precios | API REST MITECO | Catálogo oficial de gasolineras España |
| Routing por texto | OSRM demo server | Obtener trayecto real origen–destino |

---

## 🚀 Instalación y Ejecución Local

### Prerrequisitos

- Python **3.11 o superior**
- `git`

### 1. Clonar el repositorio

```bash
git clone https://github.com/Chane12/Gasolineras-GPX-Optimizador-de-Repostaje-en-Ruta.git
cd Gasolineras-GPX-Optimizador-de-Repostaje-en-Ruta
```

### 2. Crear y activar un entorno virtual

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

> ⚠️ **GeoPandas en Windows**: Si la instalación falla por dependencias binarias (`GDAL`, `Fiona`), usa [conda](https://docs.conda.io/) o instala las wheels desde [Unofficial Windows Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/).

### 4. Arrancar la aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá en `http://localhost:8501`.

---

## 📁 Estructura del Proyecto

```
Gasolineras-GPX-Optimizador-de-Repostaje-en-Ruta/
├── app.py                  # Aplicación principal Streamlit (UI + pipeline)
├── gasolineras_ruta.py     # Módulo de análisis geoespacial y exportación
├── demo_route.gpx          # Ruta demo Madrid → Valencia
├── requirements.txt        # Dependencias del proyecto
├── INSTRUCCIONES.txt       # Guía de uso rápido
├── README.md
└── .gitignore
```

---

## 🔗 Fuentes de Datos

- **MITECO — Precios de carburantes**: [geoportalgasolineras.es](https://geoportalgasolineras.es/) / endpoint REST oficial. Actualización horaria.
- **OSRM** — [router.project-osrm.org](http://router.project-osrm.org) — Motor de routing de código abierto para calcular rutas por nombre de ciudad.
- **Sistema de referencia**: ETRS89 / UTM zona 30N — **EPSG:25830** (proyección métrica oficial para España peninsular).

---

## 📄 Licencia

Distribuido bajo licencia **MIT**. Consulta el archivo [`LICENSE`](LICENSE) para más detalles.
