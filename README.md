# ⛽ Gasolineras GPX — Optimizador de Repostaje en Ruta

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![GeoPandas](https://img.shields.io/badge/GeoPandas-0.14%2B-139C5A?logo=data:image/svg+xml;base64,)](https://geopandas.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **¿Deberías parar a repostar _ahora_ o esperar hasta la próxima ciudad?**  
> Esta herramienta lo calcula por ti: cruza tu ruta GPX con los precios de combustible en tiempo real del MITECO y te muestra las gasolineras más baratas dentro de tu corredor de viaje.

---

## 🗺️ El Problema que Resuelve

Cuando conduces una ruta larga en España, elegir _dónde_ repostar puede suponer diferencias de **10-20 €** en el mismo trayecto. Las comparativas genéricas de precio no tienen en cuenta si esa gasolinera barata está realmente _en tu camino_ o a varios kilómetros de desvío.

**Gasolineras GPX** resuelve esto con precisión geoespacial:

1. Toma tu ruta GPS real (archivo `.gpx`).
2. Construye un corredor de búsqueda configurable alrededor del trayecto (p.ej. 5 km).
3. Cruza ese corredor con el catálogo oficial de precios de la **API MITECO** (datos actualizados cada hora).
4. Te devuelve un mapa interactivo con las **N gasolineras más baratas** que realmente puedes alcanzar sin desviarte.

---

## 🏗️ Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Streamlit)                  │
│  · Carga de archivo GPX        · Filtros de combustible  │
│  · Slider de radio de búsqueda · Mapa Folium embebido    │
└───────────────────────┬─────────────────────────────────┘
                        │
          ┌─────────────▼──────────────┐
          │     Capa de Procesamiento   │
          │  ┌──────────────────────┐  │
          │  │ gpxpy                │  │  ← Lectura de tracks GPX
          │  │ Ramer-Douglas-Peucker│  │  ← Simplificación de geometría
          │  │ Shapely + GeoPandas  │  │  ← Buffer + Spatial Join
          │  │ EPSG:25830 (UTM 30N) │  │  ← Proyección métrica
          │  └──────────────────────┘  │
          └─────────────┬──────────────┘
                        │
          ┌─────────────▼──────────────┐
          │      Fuentes de Datos       │
          │  · API REST MITECO (JSON)   │  ← Precios en tiempo real
          │  · Archivo .gpx (usuario)   │  ← Ruta del viaje
          └────────────────────────────┘
```

### Tecnologías clave

| Componente | Librería | Rol |
|---|---|---|
| UI interactiva | `streamlit` | Frontend web sin JavaScript |
| Análisis geoespacial | `geopandas`, `shapely` | Buffer, spatial join, proyección |
| Simplificación de ruta | Ramer-Douglas-Peucker (vía `gpxpy`) | Reducir vértices de la polilínea GPX |
| Visualización | `folium` | Mapas interactivos HTML |
| Datos de precios | API REST MITECO | Catálogo oficial de gasolineras España |

---

## 🚀 Instalación y Ejecución Local

### Prerrequisitos

- Python **3.11 o superior**
- `git`

### 1. Clonar el repositorio

```bash
git clone https://github.com/TU_USUARIO/gasolineras-gpx.git
cd gasolineras-gpx
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

> ⚠️ **GeoPandas en Windows**: Si la instalación falla por dependencias binarias (`GDAL`, `Fiona`), usa [conda](https://docs.conda.io/) o instala las wheels manualmente desde [Unofficial Windows Binaries](https://www.lfd.uci.edu/~gohlke/pythonlibs/).

### 4. Arrancar la aplicación

```bash
streamlit run app.py
```

La aplicación se abrirá automáticamente en `http://localhost:8501`.

---

## 📁 Estructura del Proyecto

```
gasolineras-gpx/
├── app.py              # Aplicación principal Streamlit
├── requirements.txt    # Dependencias del proyecto
├── README.md
└── .gitignore
```

> Los archivos `.gpx` y cualquier dato espacial intermedio están excluidos del repositorio por `.gitignore`.

---

## 🔗 Fuentes de Datos

- **MITECO — Precios de carburantes**: [geoportalgasolineras.es](https://geoportalgasolineras.es/) / endpoint REST oficial.
- **Sistema de referencia**: ETRS89 / UTM zona 30N — **EPSG:25830** (proyección métrica oficial España peninsular).

---

## 📄 Licencia

Distribuido bajo licencia **MIT**. Consulta el archivo [`LICENSE`](LICENSE) para más detalles.
