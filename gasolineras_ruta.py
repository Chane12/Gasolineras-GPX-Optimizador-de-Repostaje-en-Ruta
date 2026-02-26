"""
gasolineras_ruta.py
===================
Optimizador de rutas y precios de combustible en España.

Autor: Lead Data Engineer / Arquitecto GIS
Descripción:
    - Descarga las gasolineras en tiempo real del MITECO (Ministerio para
      la Transición Ecológica y el Reto Demográfico).
    - Lee un track GPX, lo simplifica con Ramer-Douglas-Peucker y le aplica
      un buffer espacial en proyección métrica (EPSG:25830, UTM 30N).
    - Realiza un Spatial Join para quedarse solo con las gasolineras dentro
      del buffer.
    - Filtra por tipo de combustible y devuelve el Top-N de las más baratas.
    - Genera un mapa interactivo en HTML con folium.

Dependencias:
    pip install geopandas shapely folium requests gpxpy pyproj fiona
"""

from __future__ import annotations

import heapq
import json
import math
import time
import warnings
from pathlib import Path
from typing import Optional

import folium
import gpxpy
import gpxpy.gpx
import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point
from shapely.ops import transform
from pyproj import Geod
import math as _math
import pyproj

# Silencia advertencias de GeoPandas sobre índices espaciales (dependiendo de versión)
warnings.filterwarnings("ignore", category=UserWarning, module="geopandas")

# ---------------------------------------------------------------------------
# Constantes globales
# ---------------------------------------------------------------------------

# Endpoint oficial del MITECO (Geoportal SEGESP)
MITECO_API_URL: str = (
    "https://sedeaplicaciones.minetur.gob.es"
    "/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/"
)

# CRS de origen (GPS / WGS84) y CRS de trabajo (UTM zona 30N, metro como unidad)
CRS_WGS84: str = "EPSG:4326"
CRS_UTM30N: str = "EPSG:25830"

# Columns del JSON del MITECO que contienen precios (pueden llegar con comas decimales)
PRICE_COLUMNS: list[str] = [
    "Precio Gasoleo A",
    "Precio Gasoleo B",
    "Precio Gasoleo Premium",
    "Precio Gasolina 95 E5",
    "Precio Gasolina 95 E10",
    "Precio Gasolina 95 E5 Premium",
    "Precio Gasolina 98 E5",
    "Precio Gasolina 98 E10",
    "Precio Bioetanol",
    "Precio Biodiesel",
    "Precio Gas Natural Comprimido",
    "Precio Gas Natural Licuado",
    "Precio Gases licuados del petróleo",
    "Precio Hidrogeno",
]

# Columnas de coordenadas del MITECO (también llegan con coma decimal)
COORD_COLUMNS: list[str] = ["Latitud", "Longitud (WGS84)"]


# ===========================================================================
# 1. INGESTA - API del MITECO
# ===========================================================================

def fetch_gasolineras(timeout: int = 30) -> pd.DataFrame:
    """
    Descarga el catálogo completo de gasolineras desde la API REST del MITECO.
    """
    import urllib.parse

    print("[MITECO] Descargando datos via requests...")

    # Cabeceras de navegador para evitar filtros básicos de User-Agent
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-ES,es;q=0.9",
    }

    # ----------------------------------------------------------------
    # Intento 1 — conexión directa al MITECO
    # ----------------------------------------------------------------
    data = None
    _err_direct: Exception | None = None
    try:
        response = requests.get(MITECO_API_URL, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        print("[MITECO] Conexión directa exitosa.")
    except requests.exceptions.RequestException as exc:
        _err_direct = exc  # guardar: Python 3 borra 'as e' al salir del except
        print(f"[MITECO] Conexión directa falló ({type(_err_direct).__name__}). "
              "Probando proxies públicos...")

    # ----------------------------------------------------------------
    # Intentos 2-4 — proxies de paso en cascada
    # El MITECO bloquea IPs de centros de datos (AWS/GCP) a nivel TCP.
    # Probamos varios proxies públicos en orden hasta que uno funcione.
    # ----------------------------------------------------------------
    if data is None:
        encoded_url = urllib.parse.quote(MITECO_API_URL, safe="")
        proxy_candidates = [
            # Proxy 1: corsproxy.io — muy fiable, ampliamente usado
            f"https://corsproxy.io/?{encoded_url}",
            # Proxy 2: allorigins (formato get con vía raw)
            f"https://api.allorigins.win/get?url={encoded_url}",
            # Proxy 3: codetabs
            f"https://api.codetabs.com/v1/proxy?quest={encoded_url}",
        ]

        last_proxy_err: Exception | None = None
        for proxy_url in proxy_candidates:
            proxy_name = proxy_url.split("//")[1].split("/")[0]
            try:
                print(f"[MITECO] Intentando proxy: {proxy_name}...")
                resp = requests.get(proxy_url, headers=headers, timeout=15)
                resp.raise_for_status()

                # allorigins /get devuelve {"contents": "...", "status": {...}}
                if "allorigins.win/get" in proxy_url:
                    wrapper = resp.json()
                    data = json.loads(wrapper["contents"])
                else:
                    data = resp.json()

                print(f"[MITECO] Datos obtenidos via {proxy_name}.")
                break
            except Exception as exc:
                last_proxy_err = exc
                print(f"[MITECO] Proxy {proxy_name} falló: {exc}")

        if data is None:
            raise ConnectionError(
                "No se pudo conectar con la API del MITECO ni directamente "
                "ni mediante ningún proxy. Comprueba tu conexión a Internet.\n"
                f"Error directo: {_err_direct}\n"
                f"Último error de proxy: {last_proxy_err}"
            )

    records = data.get("ListaEESSPrecio", [])
    if not records:
        raise ValueError("La API del MITECO no devolvió registros. Comprueba el endpoint.")

    df = pd.DataFrame(records)
    print(f"[MITECO] Registros descargados: {len(df)}")

    # --- Limpieza de campos numéricos (coma → punto) ---
    # El MITECO devuelve strings como "1,549" → debemos convertir a 1.549
    for col in PRICE_COLUMNS:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .str.strip()
            )
            # Cadenas vacías o no numéricas → NaN
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in COORD_COLUMNS:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .str.strip()
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- Eliminar filas sin coordenadas ---
    lat_col = "Latitud"
    lon_col = "Longitud (WGS84)"
    filas_antes = len(df)
    df = df.dropna(subset=[lat_col, lon_col])
    # También eliminar coordenadas (0, 0) que son claramente erróneas
    df = df[(df[lat_col] != 0.0) & (df[lon_col] != 0.0)]
    print(
        f"[MITECO] Filas eliminadas por falta de coordenadas: "
        f"{filas_antes - len(df)} -- Válidas: {len(df)}"
    )

    df = df.reset_index(drop=True)
    return df


# ===========================================================================
# 1b. ENRUTAMIENTO POR TEXTO — Geocodificación + OSRM
# ===========================================================================

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim rechaza User-Agents genéricos y bloques de IPs de centros de datos.
# Usamos un UA de navegador real + Referer para evitar el 403.
_NOMINATIM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.openstreetmap.org/",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept": "application/json",
}

_OSRM_ROUTE_URL = "https://routing.openstreetmap.de/routed-car/route/v1/driving"


class RouteTextError(ValueError):
    """Se lanza cuando no es posible trazar la ruta entre los puntos de texto dados."""


def _geocode(lugar: str, timeout: float = 5.0) -> tuple[float, float]:
    """
    Geocodifica un nombre de lugar usando la API pública de Nominatim (OSM).

    Usa ``requests`` directamente para evitar añadir la dependencia de
    ``geopy`` al proyecto. El User-Agent personalizado es obligatorio
    según los Términos de Uso de Nominatim.

    Parameters
    ----------
    lugar : str
        Nombre del lugar a geocodificar (ciudad, dirección, poi...).
    timeout : float
        Tiempo máximo de espera en segundos.

    Returns
    -------
    tuple[float, float]
        (latitud, longitud) en WGS84.

    Raises
    ------
    RouteTextError
        Si Nominatim no devuelve resultados o la llamada falla.
    """
    try:
        time.sleep(1)  # Nominatim exige ≤1 req/s; también reduce riesgo de rate-limit
        resp = requests.get(
            _NOMINATIM_URL,
            params={"q": lugar, "format": "json", "limit": 1},
            headers=_NOMINATIM_HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            raise RouteTextError(
                f"No encontramos la ubicación «{lugar}». "
                "Prueba a escribir el nombre completo de la ciudad o provincia."
            )
        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
        print(f"[Geocode] «{lugar}» -> ({lat:.5f}, {lon:.5f})")
        return lat, lon
    except RouteTextError:
        raise
    except Exception as exc:
        raise RouteTextError(
            f"Error al geocodificar «{lugar}»: {exc}"
        ) from exc


def get_route_from_text(origen: str, destino: str) -> LineString:
    """
    Obtiene la ruta por carretera entre dos puntos descritos en texto plano
    y la devuelve como un ``LineString`` de Shapely en EPSG:4326.

    Flujo
    -----
    1. Geocodificar origen  → (lat_o, lon_o)  via Nominatim
    2. Geocodificar destino → (lat_d, lon_d)  via Nominatim
    3. Petición OSRM con ``overview=full&geometries=geojson`` para obtener
       la geometría completa de la ruta (todos los waypoints intermedios).
    4. Extraer el array de coordenadas ``[lon, lat]`` del GeoJSON y
       construir el ``LineString``.

    Parameters
    ----------
    origen : str
        Nombre del punto de partida (p. ej. "Madrid", "A Coruña").
    destino : str
        Nombre del destino (p. ej. "Barcelona", "Sevilla").

    Returns
    -------
    LineString
        Ruta en EPSG:4326 compatible con el resto del pipeline.

    Raises
    ------
    RouteTextError
        Ante cualquier fallo de geocodificación o de la API OSRM.
    """
    # Paso 1 & 2 — Geocodificación
    lat_o, lon_o = _geocode(origen)
    lat_d, lon_d = _geocode(destino)

    import random
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) Gecko/20100101 Firefox/123.0"
    ]
    headers = {"User-Agent": random.choice(user_agents)}

    # Plan de contingencia OSRM: 
    # 1. Intentar full geometry en router principal (FOSSGIS).
    # 2. Intentar simplified geometry en router principal (FOSSGIS) para evitar timeouts en >500km.
    # 3. Fallback final simplificado al router oficial de OSRM demo.
    endpoints = [
        f"{_OSRM_ROUTE_URL}/{lon_o},{lat_o};{lon_d},{lat_d}?overview=full&geometries=geojson&alternatives=false&steps=false",
        f"{_OSRM_ROUTE_URL}/{lon_o},{lat_o};{lon_d},{lat_d}?overview=simplified&geometries=geojson&alternatives=false&steps=false",
        f"http://router.project-osrm.org/route/v1/driving/{lon_o},{lat_o};{lon_d},{lat_d}?overview=simplified&geometries=geojson&alternatives=false&steps=false"
    ]

    data = None
    last_err = None
    
    for url in endpoints:
        try:
            print(f"[Ruta] Intentando OSRM endpoint...")
            resp = requests.get(url, headers=headers, timeout=12.0)
            if resp.status_code == 429:
                last_err = "El servicio de enrutamiento está saturado (rate-limit)."
                continue
            resp.raise_for_status()
            data = resp.json()  # Aquí se generaba el JSONDecodeError si nos daban HTML de error (5XX capturados engañosamente)
            break
        except Exception as exc:
            last_err = str(exc)
            data = None
            
    if data is None:
        raise RouteTextError(f"No se pudo contactar con ningún servicio de OSRM (timeouts o respuestas corruptas). Último error: {last_err}")

    # Paso 4 — Extraer geometría
    try:
        routes = data.get("routes", [])
        if not routes:
            raise RouteTextError(
                f"OSRM no encontró ruta entre «{origen}» y «{destino}». "
                "Comprueba que ambos puntos sean accesibles por carretera."
            )
        coords = routes[0]["geometry"]["coordinates"]  # lista de [lon, lat]
        if len(coords) < 2:
            raise RouteTextError("La ruta devuelta por OSRM es demasiado corta.")
        track = LineString(coords)  # Shapely acepta [lon, lat] → EPSG:4326
        dist_km = routes[0]["legs"][0]["distance"] / 1000.0
        print(f"[OSRM] Ruta «{origen}» -> «{destino}»: {dist_km:.1f} km, "
              f"{len(coords)} puntos.")
        return track
    except RouteTextError:
        raise
    except Exception as exc:
        raise RouteTextError(
            f"Error al procesar la geometría de la ruta: {exc}"
        ) from exc


# ===========================================================================
# 2. PROCESAMIENTO GPX
# ===========================================================================

def load_gpx_track(gpx_path: str | Path) -> LineString:
    """
    Lee un archivo GPX y extrae el track principal como un LineString de Shapely.

    Itera sobre todos los tracks y segmentos del archivo GPX, acumulando
    los puntos en orden. Requiere que el GPX tenga al menos un track con
    al menos dos puntos.

    Parameters
    ----------
    gpx_path : str | Path
        Ruta al archivo .gpx.

    Returns
    -------
    LineString
        Geometría de la ruta en coordenadas WGS84 (longitud, latitud).
        Nota: Shapely usa el orden (x=lon, y=lat).
    """
    gpx_path = Path(gpx_path)
    if not gpx_path.exists():
        raise FileNotFoundError(f"No se encuentra el archivo GPX: {gpx_path}")

    # Intentar UTF-8 primero (estándar); fallback a latin-1 para archivos
    # exportados desde Garmin/Windows con caracteres especiales (tildes, etc.)
    try:
        with open(gpx_path, "r", encoding="utf-8") as f:
            gpx = gpxpy.parse(f)
    except UnicodeDecodeError:
        with open(gpx_path, "r", encoding="latin-1") as f:
            gpx = gpxpy.parse(f)

    coords: list[tuple[float, float]] = []

    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                # Shapely: (x=longitud, y=latitud)
                coords.append((point.longitude, point.latitude))

    # Si no hay tracks, intentar rutas (routes) como fallback
    if not coords:
        for route in gpx.routes:
            for point in route.points:
                coords.append((point.longitude, point.latitude))

    if len(coords) < 2:
        raise ValueError(
            f"El GPX '{gpx_path.name}' debe contener al menos 2 puntos de track."
        )

    print(f"[GPX] Puntos cargados del track: {len(coords)}")
    return LineString(coords)


# ===========================================================================
# VALIDACIÓN DEL GPX
# Límites de seguridad antes de lanzar el pipeline completo.
# ===========================================================================

# Bounding box de España peninsular + Baleares + Canarias + Ceuta/Melilla
_BBOX_SPAIN = {"min_lat": 27.6, "max_lat": 44.0, "min_lon": -18.2, "max_lon": 4.3}
_MAX_TRACK_POINTS = 50_000


def validate_gpx_track(track: LineString) -> None:
    """
    Valida que el track GPX sea seguro de procesar.

    Comprueba:
    1. Que no exceda el máximo de puntos permitido (protección OOM).
    2. Que el centroide de la ruta esté dentro del territorio español.

    Parameters
    ----------
    track : LineString
        LineString en WGS84 con las coordenadas de la ruta.

    Raises
    ------
    ValueError
        Si el track tiene demasiados puntos o no está en España.
    """
    n_pts = len(track.coords)
    if n_pts > _MAX_TRACK_POINTS:
        raise ValueError(
            f"La ruta tiene demasiados puntos ({n_pts:,}). "
            f"Máximo permitido: {_MAX_TRACK_POINTS:,}. "
            "Simplifica el GPX antes de subirlo."
        )

    # Centroide aproximado: media de coordenadas del track
    lons = [c[0] for c in track.coords]
    lats = [c[1] for c in track.coords]
    c_lon = sum(lons) / len(lons)
    c_lat = sum(lats) / len(lats)

    bb = _BBOX_SPAIN
    if not (bb["min_lat"] < c_lat < bb["max_lat"] and bb["min_lon"] < c_lon < bb["max_lon"]):
        raise ValueError(
            f"La ruta no parece estar en territorio español "
            f"(centroide: lat={c_lat:.3f}, lon={c_lon:.3f}). "
            "Esta herramienta solo cubre España peninsular, Baleares y Canarias."
        )

    print(f"[Validación] Track OK: {n_pts:,} puntos, centroide ({c_lat:.3f}, {c_lon:.3f}).")


# ===========================================================================
# 3. SIMPLIFICACIÓN RAMER-DOUGLAS-PEUCKER
# ===========================================================================

def simplify_track(track: LineString, tolerance_deg: float = 0.0005) -> LineString:
    """
    Simplifica un LineString usando el algoritmo de Ramer-Douglas-Peucker.

    Este paso es esencial para reducir el coste computacional del buffer
    y del spatial join posteriores, eliminando vértices redundantes sin
    perder la forma general de la ruta.

    Parameters
    ----------
    track : LineString
        Geometría original de la ruta en EPSG:4326 (grados decimales).
    tolerance_deg : float
        Tolerancia de simplificación en grados. ~0.0005° ≈ 50 metros en latitud.
        Ajustar según la precisión deseada: menor valor → menos simplificación.

    Returns
    -------
    LineString
        LineString simplificado. Siempre conserva el primer y último punto.
    """
    simplified = track.simplify(tolerance_deg, preserve_topology=True)
    print(
        f"[Simplify] Vertices: {len(track.coords)} --> {len(simplified.coords)} "
        f"(tolerancia={tolerance_deg} deg)"
    )
    return simplified


# ===========================================================================
# 4. MOTOR ESPACIAL (Core GIS)
# ===========================================================================

def build_route_buffer(
    track: LineString,
    buffer_meters: float = 5000.0,
) -> gpd.GeoDataFrame:
    """
    Transforma el track de WGS84 a UTM 30N, aplica un buffer en metros y
    devuelve el polígono resultante en un GeoDataFrame en EPSG:25830.

    ¿Por qué cambiar de EPSG?
    - EPSG:4326 (WGS84) usa grados como unidad → no se puede hacer un buffer
      de "5000 metros" directamente (los grados no son equidistantes).
    - EPSG:25830 (UTM 30N) usa metros como unidad y es la proyección oficial
      para la España peninsular → el buffer es geométricamente correcto.

    Parameters
    ----------
    track : LineString
        Ruta simplificada en EPSG:4326.
    buffer_meters : float
        Radio del buffer en metros.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame con una única fila: el polígono del buffer en EPSG:25830.
    """
    # Crear GeoDataFrame con el track en WGS84
    gdf_track = gpd.GeoDataFrame(geometry=[track], crs=CRS_WGS84)

    # TRANSFORMACIÓN CRS #1: WGS84 (grados) → UTM 30N (metros)
    # Esto permite usar unidades métricas reales en España peninsular.
    gdf_track_utm = gdf_track.to_crs(CRS_UTM30N)

    # Aplicar buffer paramétrico en metros
    gdf_buffer = gdf_track_utm.copy()
    gdf_buffer["geometry"] = gdf_track_utm.buffer(buffer_meters)
    print(
        f"[Buffer] Buffer de {buffer_meters:.0f}m aplicado sobre el track "
        f"(Area aprox: {gdf_buffer.geometry.area.iloc[0]/1e6:.1f} km2)"
    )
    return gdf_buffer


def build_stations_geodataframe(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """
    Convierte el DataFrame de gasolineras del MITECO a un GeoDataFrame
    proyectado en EPSG:25830 (UTM 30N) con índice espacial R-Tree.

    ¿Por qué EPSG:25830?
    - Para que el Spatial Join con el buffer (también en 25830) sea correcto.
    - Si los CRS no coinciden, GeoPandas lanza un error o produce resultados
      silenciosamente erróneos.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame limpio con columnas 'Latitud' y 'Longitud (WGS84)' como float.

    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame en EPSG:25830 con índice espacial R-Tree incorporado
        (GeoPandas lo construye automáticamente al primer uso de sindex).
    """
    # Construir geometría Point desde latitud/longitud
    # Nota: Point(x, y) → Point(longitud, latitud) en convención geográfica
    geometry = [
        Point(lon, lat)
        for lon, lat in zip(df["Longitud (WGS84)"], df["Latitud"])
    ]

    # Crear GeoDataFrame con CRS origen WGS84
    gdf_stations = gpd.GeoDataFrame(df.copy(), geometry=geometry, crs=CRS_WGS84)

    # TRANSFORMACIÓN CRS #2: WGS84 → UTM 30N
    # Imprescindible para que el sjoin con el buffer funcione en el mismo CRS.
    gdf_stations_utm = gdf_stations.to_crs(CRS_UTM30N)

    print(f"[Estaciones] GeoDataFrame en {CRS_UTM30N}: {len(gdf_stations_utm)} estaciones")
    # El índice R-Tree se construye en el primer acceso a .sindex (lazy)
    print(f"[Estaciones] Índice espacial R-Tree: {gdf_stations_utm.sindex}")

    return gdf_stations_utm


def spatial_join_within_buffer(
    gdf_stations: gpd.GeoDataFrame,
    gdf_buffer: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Realiza un Spatial Join (intersección) para filtrar las gasolineras que
    caen dentro del polígono del buffer de la ruta.

    GeoPandas usa internamente el índice R-Tree para pre-filtrar candidatos
    antes de la comprobación geométrica exacta (within), lo que hace la
    operación eficiente incluso con miles de estaciones.

    Parameters
    ----------
    gdf_stations : gpd.GeoDataFrame
        Gasolineras en EPSG:25830.
    gdf_buffer : gpd.GeoDataFrame
        Buffer de la ruta en EPSG:25830.

    Returns
    -------
    gpd.GeoDataFrame
        Subconjunto de gasolineras cuya geometría intersecta con el buffer.
    """
    # Ambos GeoDataFrames deben estar en el mismo CRS (25830)
    assert gdf_stations.crs == gdf_buffer.crs, (
        f"CRS mismatch: estaciones={gdf_stations.crs}, buffer={gdf_buffer.crs}"
    )

    gdf_joined = gpd.sjoin(
        gdf_stations,
        gdf_buffer[["geometry"]],
        how="inner",
        predicate="within",   # Gasolinera completamente dentro del polígono
    )

    # sjoin puede generar duplicados si hay múltiples polígonos en gdf_buffer
    gdf_joined = gdf_joined.drop_duplicates(subset=["geometry"])
    print(f"[SpatialJoin] Gasolineras dentro del buffer: {len(gdf_joined)}")
    return gdf_joined


# ===========================================================================
# 5. FILTRADO DE NEGOCIO
# ===========================================================================

def filter_cheapest_stations(
    gdf: gpd.GeoDataFrame,
    fuel_column: str = "Precio Gasoleo A",
    top_n: int = 5,
    track_utm: Optional[LineString] = None,
    segment_km: float = 0.0,
) -> gpd.GeoDataFrame:
    """
    Filtra las gasolineras con precio válido para el combustible elegido
    y devuelve las top_n más baratas.

    El parámetro fuel_column permite cambiar dinámicamente el tipo de
    combustible, adaptando el script a cualquier vehículo:
      - Peugeot 207 (diésel)  → "Precio Gasoleo A"
      - Benelli TRK 502 (gasolina) → "Precio Gasolina 95 E5"
      - Lleno de gasóleo premium  → "Precio Gasoleo Premium"

    Parameters
    ----------
    gdf : gpd.GeoDataFrame
        Gasolineras dentro del buffer del recorrido (EPSG:25830).
    fuel_column : str
        Nombre exacto de la columna de precio a usar.
    top_n : int
        Número de gasolineras más baratas a devolver.

    Returns
    -------
    gpd.GeoDataFrame
        Top N gasolineras más baratas, ordenadas de menor a mayor precio.
        Incluye la columna de precio seleccionada como 'precio_seleccionado'.
    """
    if fuel_column not in gdf.columns:
        available = [c for c in PRICE_COLUMNS if c in gdf.columns]
        raise ValueError(
            f"Columna '{fuel_column}' no encontrada.\n"
            f"Columnas de precio disponibles: {available}"
        )

    # Coerción numérica estricta — protege contra datos sucios del MITECO
    # (strings residuales como "N/A" o "Agotado" que sobrevivan a la limpieza)
    gdf = gdf.copy()
    gdf[fuel_column] = pd.to_numeric(gdf[fuel_column], errors="coerce")

    # Filtrar filas con precio válido (eliminar NaN y ceros)
    mask = gdf[fuel_column].notna() & (gdf[fuel_column] > 0)
    gdf_valid = gdf[mask].copy()

    if gdf_valid.empty:
        print(f"[Filtrado] [WARN] No hay gasolineras con precio para '{fuel_column}'.")
        return gdf_valid

    # Añadir columna estandarizada para el output
    gdf_valid["precio_seleccionado"] = gdf_valid[fuel_column]
    gdf_valid["combustible"] = fuel_column

    if track_utm is not None:
        import shapely
        # Calcular el punto de la ruta (en metros) al que se proyecta la gasolinera vectorizadamente
        gdf_valid["km_ruta"] = shapely.line_locate_point(track_utm, gdf_valid.geometry) / 1000.0

    # 1. Búsqueda global estándar (Top N global)
    gdf_top_global = gdf_valid.nsmallest(top_n, fuel_column).copy()

    if track_utm is not None and segment_km > 0:
        # Búsqueda segmentada: 1 gasolinera más barata por cada tramo de segment_km
        gdf_valid["tramo"] = (gdf_valid["km_ruta"] // segment_km).astype(int)
        
        # Agrupamos por tramo y obtenemos el índice de la más barata
        idx_top_per_segment = gdf_valid.groupby("tramo")[fuel_column].idxmin()
        gdf_top_segment = gdf_valid.loc[idx_top_per_segment].copy()
        
        # Unimos el Top N global con las obligatorias por tramo
        gdf_top = pd.concat([gdf_top_global, gdf_top_segment])
        
        # Eliminamos duplicados (aquellas que ya estaban en el Top N global)
        gdf_top = gdf_top.drop_duplicates(subset=["geometry"])
        
        # Ordenamos cronológicamente según la ruta para la visualización
        gdf_top = gdf_top.sort_values("km_ruta").reset_index(drop=True)

        print(f"\n[Filtrado] Top {top_n} global + 1 obligatoria cada {segment_km} km para '{fuel_column}':")
        for i, row in gdf_top.iterrows():
            nombre = row.get("Rótulo", row.get("C.P.", "N/A"))
            municipio = row.get("Municipio", "")
            precio = row["precio_seleccionado"]
            km = row["km_ruta"]
            print(f"  Km {km:.1f} | {nombre} ({municipio}) --> {precio:.3f} EUR/L")

    else:
        # Solo Búsqueda global estándar
        gdf_top = gdf_top_global.reset_index(drop=True)

        print(f"\n[Filtrado] Top {top_n} más baratas para '{fuel_column}':")
        for i, row in gdf_top.iterrows():
            nombre = row.get("Rótulo", row.get("C.P.", "N/A"))
            municipio = row.get("Municipio", "")
            precio = row["precio_seleccionado"]
            km_str = f" (Km {row['km_ruta']:.1f})" if "km_ruta" in row else ""
            print(f"  #{i+1} {nombre}{km_str} ({municipio}) --> {precio:.3f} EUR/L")

    return gdf_top


# ===========================================================================
# 5d. EXPORTACIÓN DE RUTAS — Google Maps URL + GPX Enriquecido
# ===========================================================================

_GMAPS_MAX_WAYPOINTS = 9  # Límite documentado de la API de URLs de Google Maps


def generate_google_maps_url(
    track: "LineString",
    gdf_stops: gpd.GeoDataFrame,
) -> tuple[str, int]:
    """
    Genera una URL de Google Maps con la ruta multidestino que incluye las
    paradas de repostaje calculadas por Dijkstra.

    La función transforma las coordenadas de UTM (EPSG:25830) a WGS84
    (EPSG:4326) y construye la URL usando la API de Directions estándar
    de Google Maps, apta para móvil (abre la app) y escritorio (abre la web).

    Parameters
    ----------
    track : LineString
        Track de la ruta en CUALQUIER CRS de coordenadas geográficas (grados).
        Se asume WGS84 si no tiene CRS. Se usan el primer y último vértice
        del LineString como Origen y Destino respectivamente.
    gdf_stops : gpd.GeoDataFrame
        GeoDataFrame con las paradas de repostaje en EPSG:25830 (UTM 30N).
        Se proyectará internamente a WGS84 para extraer coordenadas.

    Returns
    -------
    url : str
        URL completa lista para usar en un <a href> o st.link_button.
    n_truncated : int
        Número de paradas que han sido omitidas por superar el límite de
        9 waypoints de la API. 0 si no se ha truncado ninguna.
    """
    import urllib.parse as _up

    # --- Origen y destino a partir del track (ya está en WGS84) ---
    coords = list(track.coords)
    lat_o, lon_o = coords[0][1], coords[0][0]
    lat_d, lon_d = coords[-1][1], coords[-1][0]

    # --- Paradas: proyectar a WGS84 ---
    n_truncated = 0
    waypoints_str = ""
    if gdf_stops is not None and not gdf_stops.empty:
        gdf_wgs84 = gdf_stops.to_crs("EPSG:4326")
        stops_all = [
            f"{row.geometry.y:.6f},{row.geometry.x:.6f}"
            for _, row in gdf_wgs84.iterrows()
        ]
        if len(stops_all) > _GMAPS_MAX_WAYPOINTS:
            n_truncated = len(stops_all) - _GMAPS_MAX_WAYPOINTS
            stops_all = stops_all[:_GMAPS_MAX_WAYPOINTS]
        waypoints_str = "|".join(stops_all)

    # --- Construir URL (API v1 — compatible con app Android/iOS/Web) ---
    params: dict[str, str] = {
        "api":         "1",
        "origin":      f"{lat_o:.6f},{lon_o:.6f}",
        "destination": f"{lat_d:.6f},{lon_d:.6f}",
        "travelmode":  "driving",
    }
    if waypoints_str:
        params["waypoints"] = waypoints_str

    url = "https://www.google.com/maps/dir/?" + _up.urlencode(params)
    return url, n_truncated


def enrich_gpx_with_stops(
    gpx_bytes: bytes,
    gdf_stops: gpd.GeoDataFrame,
    fuel_column: str = "",
) -> str:
    """
    Inyecta las paradas de repostaje calculadas como Waypoints (<wpt>) dentro 
    del archivo GPX original del usuario. Además, implementa "Track Splicing",
    modificando la espina dorsal geométrica del <trk> original para que este 
    se desvíe físicamente hasta la gasolinera y vuelva a la ruta.

    Parameters
    ----------
    gpx_bytes : bytes
        Contenido binario del archivo GPX original.
    gdf_stops : gpd.GeoDataFrame
        Paradas con geometría en EPSG:25830. Se proyectan a WGS84 internamente.
    fuel_column : str
        Nombre de la columna de combustible usado para incluir precio.

    Returns
    -------
    str
        Cadena XML en formato GPX lista para guardar o descargar.
    """
    import gpxpy
    import gpxpy.gpx as _gpx
    import time
    import requests

    # --- Parsear el GPX original ---
    gpx_obj = gpxpy.parse(gpx_bytes.decode("utf-8", errors="replace"))

    if gdf_stops is None or gdf_stops.empty:
        return gpx_obj.to_xml()

    gdf_wgs84 = gdf_stops.to_crs("EPSG:4326")
    
    # 1. Recopilar paradas y crear los Waypoints
    paradas = []
    for i, (_, row) in enumerate(gdf_wgs84.iterrows(), start=1):
        lat  = row.geometry.y
        lon  = row.geometry.x

        rotulo   = row.get("Rótulo", f"Gasolinera #{i}")
        litros   = row.get("litros_a_repostar", 0.0)
        coste    = row.get("coste_parada_eur",  0.0)
        precio   = row.get(fuel_column, 0.0) if fuel_column else 0.0

        nombre_wpt = (
            f"⛽ {i}. {rotulo} | "
            f"{litros:.1f} L @ {precio:.3f} €/L = {coste:.2f} €"
        ) if litros > 0 else (
            f"⛽ {i}. {rotulo} | {precio:.3f} €/L"
        )

        wpt = _gpx.GPXWaypoint(
            latitude=lat,
            longitude=lon,
            name=nombre_wpt,
            symbol="Fuel",
            description=(
                f"Repostar en {rotulo}. Precio: {precio:.3f} €/L. "
                f"Coste estimado: {coste:.2f} €." if coste > 0 else 
                f"Gasolinera {rotulo}. Precio: {precio:.3f} €/L."
            ),
        )
        gpx_obj.waypoints.append(wpt)
        
        paradas.append({"lon": lon, "lat": lat})

    # 2. Identificar el Punto de Fuga (Split Point) para cada parada
    import numpy as np
    from scipy.spatial import cKDTree

    puntos_ref = []
    indices = []
    for t_idx, track in enumerate(gpx_obj.tracks):
        for s_idx, segment in enumerate(track.segments):
            for p_idx, point in enumerate(segment.points):
                puntos_ref.append((point.longitude, point.latitude))
                indices.append((t_idx, s_idx, p_idx, point.longitude, point.latitude))

    if puntos_ref:
        tree = cKDTree(np.array(puntos_ref))
    else:
        tree = None

    split_points = []
    for parada in paradas:
        station_lon = parada["lon"]
        station_lat = parada["lat"]
        
        if tree is not None:
            dist, idx_kdtree = tree.query([station_lon, station_lat])
            closest_idx = indices[idx_kdtree]
            
            split_points.append({
                "idx": closest_idx,
                "station_lon": station_lon,
                "station_lat": station_lat
            })

    # Ordenar de final a principio para que el splicing no desplace 
    # los índices de los puntos anteriores que aún debemos procesar.
    split_points.sort(key=lambda x: (x["idx"][0], x["idx"][1], x["idx"][2]), reverse=True)

    # 3. Splicing: Enrutamiento del Desvío de Idas y Vueltas
    headers = {
        "User-Agent": "OptimizadorGasolineras/1.0",
        "Accept": "application/json"
    }

    for sp in split_points:
        t_idx, s_idx, p_idx, split_lon, split_lat = sp["idx"]
        station_lon = sp["station_lon"]
        station_lat = sp["station_lat"]
        
        segment = gpx_obj.tracks[t_idx].segments[s_idx]
        
        # Buscar "Punto de Reincorporación" aprox 30-50m adelante 
        # (para evitar U-turns extraños del motor de ruteo)
        reinc_idx = p_idx
        dist_accum = 0.0
        max_search = min(p_idx + 30, len(segment.points) - 1)
        
        for i in range(p_idx, max_search):
            p1 = segment.points[i]
            p2 = segment.points[i+1]
            # Distancia euclídea aproximada en grados a metros (~111.000m por grado)
            d = ((p2.longitude - p1.longitude)**2 + (p2.latitude - p1.latitude)**2)**0.5 * 111000
            dist_accum += d
            reinc_idx = i + 1
            if dist_accum > 35.0:
                break
                
        # Clamp: Si el bucle terminó y la distancia acumulada es bajísima o el track es ralo
        # forzamos el reingreso al menos al punto siguiente para evitar splice circular/atascado
        if dist_accum <= 35.0 and reinc_idx == p_idx:
            reinc_idx = min(p_idx + 1, len(segment.points) - 1)
            
        reinc_lon = segment.points[reinc_idx].longitude
        reinc_lat = segment.points[reinc_idx].latitude
        
        entrada = []
        salida = []
        
        # Tramo Entrada: Punto de Fuga -> Gasolinera
        try:
            url_in = (
                f"{_OSRM_BASE_URL}"
                f"/{split_lon},{split_lat};{station_lon},{station_lat}"
                f"?overview=full&geometries=geojson&alternatives=false&steps=false"
            )
            resp_in = requests.get(url_in, headers=headers, timeout=5.0)
            if resp_in.status_code == 200:
                data_in = resp_in.json()
                if data_in.get("routes"):
                    entrada = data_in["routes"][0]["geometry"]["coordinates"]
        except Exception as e:
            print(f"[GPX Splicing] Fallo entrada OSRM: {e}")
            
        time.sleep(0.3)  # Cortesía con el API pública
        
        # Tramo Salida: Gasolinera -> Punto de Reincorporación
        try:
            url_out = (
                f"{_OSRM_BASE_URL}"
                f"/{station_lon},{station_lat};{reinc_lon},{reinc_lat}"
                f"?overview=full&geometries=geojson&alternatives=false&steps=false"
            )
            resp_out = requests.get(url_out, headers=headers, timeout=5.0)
            if resp_out.status_code == 200:
                data_out = resp_out.json()
                if data_out.get("routes"):
                    salida = data_out["routes"][0]["geometry"]["coordinates"]
        except Exception as e:
            print(f"[GPX Splicing] Fallo salida OSRM: {e}")
            
        new_points = []
        
        # Añadir coordenadas de entrada
        if entrada:
            # saltamos el [0] porque ya existe en el track original (el split point)
            for coords in entrada[1:]: 
                new_points.append(_gpx.GPXTrackPoint(latitude=coords[1], longitude=coords[0]))
                
        # Opcional: inyectar el point exacto de la gasolinera por si OSRM no llega al mismo cm
        if not entrada and not salida:
            new_points.append(_gpx.GPXTrackPoint(latitude=station_lat, longitude=station_lon))

        # Añadir coordenadas de salida
        if salida:
            # En saltar [0], evitamos repetir el punto de la gasolinera
            for coords in salida[1:]:
                new_points.append(_gpx.GPXTrackPoint(latitude=coords[1], longitude=coords[0]))
                
        # 4. Inyección geométrica final
        if new_points:
            # Construimos la nueva lista de puntos del segmento
            segment.points = segment.points[:p_idx+1] + new_points + segment.points[reinc_idx+1:]

    return gpx_obj.to_xml()


# ===========================================================================
# 5b. FILTRO FINO — OSRM Hybrid Funnel
# ===========================================================================

# URL pública gratuita de OSRM. Se puede sustituir por una instancia propia.
_OSRM_BASE_URL = "https://routing.openstreetmap.de/routed-car/route/v1/driving"


def get_real_distance_osrm(
    lon_origen: float,
    lat_origen: float,
    lon_destino: float,
    lat_destino: float,
    timeout: float = 2.0,
) -> Optional[dict]:
    """
    Consulta la API pública de OSRM para obtener distancia y duración reales
    por carretera entre dos puntos.

    Utiliza ``overview=false`` para minimizar el tamaño de la respuesta y
    reducir la latencia. Solo pedimos el resumen (distancia + duración).

    Parameters
    ----------
    lon_origen, lat_origen : float
        Coordenadas WGS84 del punto de partida (punto de la ruta GPX).
    lon_destino, lat_destino : float
        Coordenadas WGS84 del destino (gasolinera).
    timeout : float
        Tiempo máximo de espera en segundos. Por defecto 2 s.

    Returns
    -------
    dict | None
        Diccionario ``{"distance_km": float, "duration_min": float}`` si la
        llamada tiene éxito; ``None`` en cualquier caso de error (timeout,
        rate-limit HTTP 429, error de red, JSON inesperado, etc.).
        La función NUNCA propaga excepciones hacia el caller.
    """
    url = (
        f"{_OSRM_BASE_URL}"
        f"/{lon_origen},{lat_origen}"
        f";{lon_destino},{lat_destino}"
        f"?overview=false&alternatives=false&steps=false"
    )
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 429:
            print("[OSRM] Rate-limit (429). Usando fallback euclidiano.")
            return None
        resp.raise_for_status()
        data = resp.json()

        # Validación defensiva estricta — OSRM puede devolver HTTP 200 con error
        if data.get("code") != "Ok" or not data.get("routes"):
            return None

        route = data["routes"][0]
        if not route.get("legs"):
            return None

        leg = route["legs"][0]
        if "distance" not in leg or "duration" not in leg:
            return None

        distance_km = leg["distance"] / 1000.0   # metros → km
        duration_min = leg["duration"] / 60.0    # segundos → minutos
        return {"distance_km": distance_km, "duration_min": duration_min}
    except Exception as exc:  # noqa: BLE001 — silencio intencional
        print(f"[OSRM] Fallo silencioso ({type(exc).__name__}). Usando fallback euclidiano.")
        return None


def enrich_stations_with_osrm(
    gdf_top: gpd.GeoDataFrame,
    track_original: LineString,
    delay_s: float = 0.12,
) -> gpd.GeoDataFrame:
    """
    Enriquece el GeoDataFrame de gasolineras Top-N con datos reales de
    distancia y tiempo de desvío obtenidos de la API OSRM.

    Para cada gasolinera:
    1. Localiza el punto exacto de la ruta GPX más cercano (usando
       ``LineString.project`` + ``LineString.interpolate`` sobre el track
       original en WGS84 — suficientemente preciso para calcular el punto
       de origen del desvío).
    2. Llama a ``get_real_distance_osrm`` entre ese punto y la gasolinera.
    3. Si falla, deja ``osrm_distance_km`` y ``osrm_duration_min`` como NaN
       para que el caller use el fallback euclidiano de forma transparente.

    Parámetro ``delay_s`` añade una pequeña pausa entre llamadas para no
    saturar el servidor público (cortesía / evitar rate-limit).

    Parameters
    ----------
    gdf_top : gpd.GeoDataFrame
        Gasolineras en EPSG:25830 (salida de filter_cheapest_stations).
    track_original : LineString
        Ruta GPX completa en EPSG:4326 (WGS84).
    delay_s : float
        Pausa en segundos entre llamadas a OSRM. Por defecto 0.12 s.

    Returns
    -------
    gpd.GeoDataFrame
        El mismo GeoDataFrame con dos columnas nuevas:
        ``osrm_distance_km`` y ``osrm_duration_min`` (float, NaN si falló).
    """
    import concurrent.futures

    gdf = gdf_top.copy()
    gdf["osrm_distance_km"] = float("nan")
    gdf["osrm_duration_min"] = float("nan")

    # Reproyectar gasolineras a WGS84 para obtener lon/lat de la gasolinera
    gdf_wgs84 = gdf.to_crs("EPSG:4326")

    def process_station(idx, row_wgs84):
        gas_lon = row_wgs84.geometry.x
        gas_lat = row_wgs84.geometry.y

        # 1. Punto más cercano de la ruta GPX a esta gasolinera
        dist_along = track_original.project(
            Point(gas_lon, gas_lat), normalized=False
        )
        nearest_on_route = track_original.interpolate(dist_along)
        origin_lon = nearest_on_route.x
        origin_lat = nearest_on_route.y

        if delay_s > 0:
            time.sleep(delay_s)

        # 2. Llamada defensiva a OSRM
        result = get_real_distance_osrm(
            lon_origen=origin_lon,
            lat_origen=origin_lat,
            lon_destino=gas_lon,
            lat_destino=gas_lat,
        )
        return idx, result, row_wgs84

    # Circuit Breaker para OSRM
    fallos_consecutivos = 0
    max_fallos = 3

    # max_workers limitado para no exceder rate-limits estáticos de OSRM (1-3 rq/s libres)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(process_station, idx, gdf_wgs84.loc[idx]): idx for idx in gdf.index}
        for future in concurrent.futures.as_completed(futures):
            # Abortamos de facto para no quemar tiempo en UI si la API falla contínuamente
            if fallos_consecutivos >= max_fallos:
                continue

            try:
                idx, result, row_wgs84 = future.result(timeout=10)
                if result is not None:
                    gdf.at[idx, "osrm_distance_km"] = round(result["distance_km"], 2)
                    gdf.at[idx, "osrm_duration_min"] = round(result["duration_min"], 1)
                    fallos_consecutivos = 0
                    print(
                        f"[OSRM] {row_wgs84.get('Rótulo', idx)}: "
                        f"{result['distance_km']:.2f} km / {result['duration_min']:.1f} min"
                    )
                else:
                    fallos_consecutivos += 1
            except Exception as e:
                fallos_consecutivos += 1
                print(f"[OSRM] Fallo detectado: {e}")

    if fallos_consecutivos >= max_fallos:
        print("[OSRM] Circuit Breaker Activado: Demasiados fallos, degradando a distancias de proyección rápida.")

    return gdf


# ===========================================================================
# 6. OUTPUT VISUAL - Mapa Folium
# ===========================================================================

def generate_map(
    track_original: LineString,
    gdf_top_stations: gpd.GeoDataFrame,
    fuel_column: str,
    output_path: Optional[str | Path] = None,
    autonomy_km: float = 0.0,
) -> tuple[Optional[Path], folium.Map]:
    """
    Genera un mapa interactivo en HTML con folium mostrando:
      - La ruta GPX original.
      - Las Top N gasolineras más baratas con markers y popups detallados.

    Para la visualización se re-proyecta todo de vuelta a EPSG:4326 (WGS84),
    que es el sistema de coordenadas que Leaflet/folium entiende nativamente.

    Parameters
    ----------
    track_original : LineString
        Ruta original en EPSG:4326 (antes de cualquier transformación).
    gdf_top_stations : gpd.GeoDataFrame
        Top N gasolineras en EPSG:25830.
    fuel_column : str
        Nombre del combustible seleccionado (para el título del popup).
    output_path : str | Path
        Ruta donde guardar el HTML.

    Returns
    -------
    tuple[Optional[Path], folium.Map]
        Ruta absoluta del archivo HTML generado y el objeto folium.Map.
    """
    if output_path is not None:
        output_path = Path(output_path)

    # --- Centro del mapa: centroide del track original ---
    track_coords = list(track_original.coords)
    center_lon = sum(c[0] for c in track_coords) / len(track_coords)
    center_lat = sum(c[1] for c in track_coords) / len(track_coords)

    mapa = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=12,
        tiles="OpenStreetMap",
    )

    # --- Capa de teselas adicional (satélite ESRI) ---
    folium.TileLayer(
        tiles=(
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}"
        ),
        attr="ESRI World Imagery",
        name="Satélite ESRI",
        overlay=False,
        control=True,
    ).add_to(mapa)

    # --- Dibujar la ruta GPX ---
    route_latlon = [(lat, lon) for lon, lat in track_coords]
    folium.PolyLine(
        locations=route_latlon,
        color="#2563EB",
        weight=4,
        opacity=0.85,
        tooltip="Ruta GPX",
        name="Ruta GPX",
    ).add_to(mapa)

    # --- Zonas de peligro por autonomía ---
    if autonomy_km > 0 and not gdf_top_stations.empty:
        # Reproyectar estaciones a WGS84 para obtener km_ruta en WGS84
        gdf_for_danger = gdf_top_stations.copy()
        if gdf_for_danger.crs and gdf_for_danger.crs.to_epsg() != 4326:
            gdf_for_danger = gdf_for_danger.to_crs(CRS_WGS84)

        # Construir lista de km de ruta donde hay gasolinera
        station_km_list = sorted(gdf_for_danger["km_ruta"].dropna().tolist()) if "km_ruta" in gdf_for_danger.columns else []

        if station_km_list:
            # Calcular longitud total de la ruta
            # Calcular longitud total de la ruta con pyproj (geodésica exacta)
            # — Más preciso que la aproximación «× 111 km/grado» que falla en rutas largas
            _geod = Geod(ellps="WGS84")
            _lons = [c[0] for c in track_coords]
            _lats = [c[1] for c in track_coords]
            _, _, _dist_m = _geod.inv(_lons[:-1], _lats[:-1], _lons[1:], _lats[1:])
            track_length_km = sum(_dist_m) / 1000.0  # metros → km (geodésico exacto)
            # Puntos de referencia: km 0, cada gasolinera y el fin de ruta
            checkpoints = [0.0] + station_km_list + [track_length_km]

            # Acumular segmentos entre checkpoints donde la brecha supera la autonomía
            danger_segments = []
            for j in range(len(checkpoints) - 1):
                gap = checkpoints[j + 1] - checkpoints[j]
                if gap > autonomy_km:
                    # Localizar los puntos de la polilínea que caen en ese intervalo
                    total_pts = len(route_latlon)
                    seg_start_idx = int((checkpoints[j] / track_length_km) * total_pts)
                    seg_end_idx = int((checkpoints[j + 1] / track_length_km) * total_pts)
                    seg_start_idx = max(0, min(seg_start_idx, total_pts - 1))
                    seg_end_idx = max(seg_start_idx + 1, min(seg_end_idx, total_pts))
                    danger_segments.append(route_latlon[seg_start_idx:seg_end_idx])

            for seg in danger_segments:
                if len(seg) >= 2:
                    folium.PolyLine(
                        locations=seg,
                        color="#ef4444",
                        weight=6,
                        opacity=0.85,
                        dash_array="10 6",
                        tooltip=f"⚠️ Tramo sin gasolineras en {autonomy_km:.0f} km",
                        name="Zonas de riesgo",
                    ).add_to(mapa)

    # Marcadores de inicio y fin de ruta
    folium.Marker(
        location=route_latlon[0],
        tooltip="Inicio de ruta",
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
    ).add_to(mapa)
    folium.Marker(
        location=route_latlon[-1],
        tooltip="Fin de ruta",
        icon=folium.Icon(color="red", icon="stop", prefix="fa"),
    ).add_to(mapa)

    # --- Dibujar gasolineras Top N ---
    # TRANSFORMACIÓN CRS #3: UTM 30N → WGS84
    # Necesario para devolver las coordenadas al sistema geográfico que
    # Leaflet (y por tanto folium) necesita para pintar los puntos en el mapa.
    gdf_wgs84 = gdf_top_stations.to_crs(CRS_WGS84)

    # ---------------------------------------------------------------------------
    # Gradiente de color basado en precio: verde (barato) → amarillo → rojo (caro)
    # Se normaliza el precio de cada gasolinera entre el mín y máx del conjunto
    # y se interpola la Hue en HSL: 120° (verde puro) → 60° (amarillo) → 0° (rojo)
    # ---------------------------------------------------------------------------
    precio_min = gdf_wgs84["precio_seleccionado"].min()
    precio_max = gdf_wgs84["precio_seleccionado"].max()

    def price_to_hex_color(precio: float) -> str:
        """Convierte un precio a un color hex del gradiente verde→amarillo→rojo."""
        if precio_max == precio_min:
            # Todos los precios son iguales → verde neutro (precio único)
            return "#16a34a"
        # t = 0.0 (más barato) → 1.0 (más caro)
        t = (precio - precio_min) / (precio_max - precio_min)
        # Hue: 120° (verde) a 0° (rojo) pasando por 60° (amarillo)
        hue = 120 * (1.0 - t)   # 120 → 0
        saturation = 88          # % saturación alta para colores vivos
        lightness = 40           # % luminosidad media para buen contraste
        # Conversión HSL → RGB → HEX
        h = hue / 360.0
        s = saturation / 100.0
        l = lightness / 100.0
        if s == 0:
            r = g = b = l
        else:
            def hue_to_rgb(p: float, q: float, t_val: float) -> float:
                t_val = t_val % 1.0
                if t_val < 1/6: return p + (q - p) * 6 * t_val
                if t_val < 1/2: return q
                if t_val < 2/3: return p + (q - p) * (2/3 - t_val) * 6
                return p
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

    # Ordenar por precio para asignar rank visual correcto (1 = más barato)
    precios_ordenados = gdf_wgs84["precio_seleccionado"].rank(method="min", ascending=True).fillna(1).astype(int)

    # Para que las más baratas aparezcan por encima al solaparse en el mapa,
    # Leaflet necesita que se dibujen las últimas. Como gdf_wgs84 está ordenado
    # de más barato a más caro (índice 0 es la más barata), iteramos al revés.
    for i in range(len(gdf_wgs84) - 1, -1, -1):
        row = gdf_wgs84.iloc[i]
        rank_visual = i + 1
        lat = row.geometry.y
        lon = row.geometry.x
        precio = row.get("precio_seleccionado", float("nan"))
        nombre = row.get("Rótulo", "Sin nombre")
        municipio = row.get("Municipio", "")
        provincia = row.get("Provincia", "")
        direccion = row.get("Dirección", "")
        horario = row.get("Horario", "")
        color = price_to_hex_color(precio)

        # Datos de OSRM (pueden ser NaN o None si la llamada falló)
        osrm_dist = row.get("osrm_distance_km", float("nan"))
        osrm_dur  = row.get("osrm_duration_min", float("nan"))
        # Proteger contra None: math.isnan(None) lanza TypeError
        try:
            _osrm_ok = not _math.isnan(osrm_dist) and not _math.isnan(osrm_dur)
        except TypeError:
            _osrm_ok = False
        if _osrm_ok:
            osrm_line = (
                f'<div style="margin:6px 0; padding:6px 8px; background:#eff6ff; '
                f'border-left:3px solid #2563eb; border-radius:4px; font-size:0.82em; color:#1e40af;">'
                f"&#128652; <b>Desvío real:</b> {osrm_dist:.1f} km &nbsp;·&nbsp; {osrm_dur:.0f} min</div>"
            )
        else:
            osrm_line = ""

        # ------- Popup: tarjeta profesional ---------------------------------
        maps_url = f"https://maps.google.com/?q={lat},{lon}"
        badge_color = "#16a34a" if rank_visual == 1 else ("#2563eb" if rank_visual <= 3 else color)
        badge_label = "⭐ Más Barata" if rank_visual == 1 else f"#{rank_visual}"

        popup_html = f"""
        <div style="font-family:'Segoe UI',Arial,sans-serif; min-width:240px; max-width:280px;">

            <!-- Header: nombre + badge -->
            <div style="display:flex; align-items:center; justify-content:space-between;
                        margin-bottom:8px;">
                <b style="font-size:1rem; color:#0f172a;">{nombre}</b>
                <span style="background:{badge_color}; color:white; font-size:0.7rem;
                             font-weight:700; padding:2px 7px; border-radius:99px;
                             white-space:nowrap; margin-left:6px;">{badge_label}</span>
            </div>

            <!-- Precio destacado -->
            <div style="text-align:center; background:#f8fafc; border-radius:8px;
                        padding:10px 0; margin-bottom:8px;">
                <div style="font-size:2rem; font-weight:800; color:{color};
                            line-height:1;">{f"{precio:.3f}" if not _math.isnan(precio) else "N/A"} €/L</div>
                <div style="font-size:0.78rem; color:#64748b; margin-top:2px;">
                    {fuel_column.replace("Precio ", "")} &nbsp;·&nbsp;
                    Km {row.get('km_ruta', 0):.1f} en ruta</div>
            </div>

            {osrm_line}

            <!-- Dirección -->
            <div style="font-size:0.82em; color:#475569; margin:4px 0;">
                &#128205; {direccion}<br>{municipio}, {provincia}
            </div>

            <!-- Horario -->
            <div style="font-size:0.78em; color:#94a3b8; margin:4px 0;">
                &#128336; {horario if horario else '—'}
            </div>

            <!-- CTA: Llévame -->
            <a href="{maps_url}" target="_blank" style="
                display:block; margin-top:10px; padding:8px;
                background:#2563eb; color:white; text-align:center;
                text-decoration:none; border-radius:6px;
                font-size:0.85em; font-weight:600;
            ">&#128652;&nbsp; Llévame aquí (Google Maps)</a>
        </div>
        """

        # El CircleMarker dibuja el fondo de color
        circle_border_color = "gold" if rank_visual == 1 else "white"
        circle_border_weight = 4 if rank_visual == 1 else 2
        folium.CircleMarker(
            location=[lat, lon],
            radius=20 if rank_visual == 1 else 17,
            color=circle_border_color,
            weight=circle_border_weight,
            fill=True,
            fill_color=color,
            fill_opacity=0.95,
            tooltip=f"#{rank_visual} {nombre} — {precio:.3f} €/L",
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(mapa)

        # El DivIcon muestra el PRECIO encima del círculo (visible sin hacer clic)
        precio_str = f"{precio:.2f}€" if not _math.isnan(precio) else "–"
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size:10px; font-weight:700;
                    color:white; text-align:center;
                    line-height:40px; width:40px;
                    border-radius:50%;
                    text-shadow: 0 1px 2px rgba(0,0,0,0.5);
                ">{precio_str}</div>
                """,
                icon_size=(40, 40),
                icon_anchor=(20, 20),
            ),
            tooltip=f"#{rank_visual} {nombre} — {precio:.3f} €/L",
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(mapa)

    # Leyenda con gradiente de precio
    legend_html = f"""
    <div style="
        position:fixed; bottom:30px; left:30px;
        z-index:1000; background:white;
        padding:14px 18px; border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,0.2);
        font-family:sans-serif; font-size:13px;
        min-width: 200px;
    ">
        <b>Optimizador de Gasolineras</b><br>
        <span style="color:#2563EB;">──</span> Ruta GPX<br><br>
        <b>Precio {fuel_column.replace("Precio ", "")}:</b><br>
        <div style="
            background: linear-gradient(to right, #16a34a, #eab308, #dc2626);
            height: 12px; border-radius: 4px; margin: 5px 0;
            border: 1px solid #ddd;
        "></div>
        <div style="display:flex; justify-content:space-between; font-size:11px; color:#555;">
            <span>&#9679; {precio_min:.3f}€ (más barato)</span>
            <span>{precio_max:.3f}€ &#9679;</span>
        </div>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(legend_html))

    # --- Control de capas ---
    folium.LayerControl().add_to(mapa)

    if output_path is not None:
        mapa.save(str(output_path))
        print(f"\n[Mapa] [SUCCESS] Mapa guardado en: {output_path.resolve()}")

    return (output_path.resolve() if output_path else None), mapa


# ===========================================================================
# PIPELINE COMPLETO
# ===========================================================================

def run_pipeline(
    gpx_path: str | Path,
    fuel_column: str = "Precio Gasoleo A",
    buffer_meters: float = 5000.0,
    top_n: int = 5,
    simplify_tolerance: float = 0.0005,
    output_html: Optional[str | Path] = None,
    segment_km: float = 0.0,
) -> dict:
    """
    Ejecuta el pipeline completo de extremo a extremo:
    ingesta → GPX → simplificación → buffer → spatial join → filtrado → mapa.

    Parameters
    ----------
    gpx_path : str | Path
        Ruta al archivo .gpx del track.
    fuel_column : str
        Columna de precio a usar (ej. "Precio Gasoleo A").
    buffer_meters : float
        Radio del buffer alrededor del track en metros.
    top_n : int
        Número de gasolineras más baratas a mostrar.
    simplify_tolerance : float
        Tolerancia RDP en grados (~0.0005° ≈ 50m).
    output_html : Optional[str | Path]
        Ruta de salida del mapa HTML (opcional).

    Returns
    -------
    dict
        Diccionario con los resultados: track, buffer, estaciones_filtradas,
        top_n_gdf y ruta_html.
    """
    print("=" * 60)
    print(" OPTIMIZADOR DE GASOLINERAS EN RUTA -- Espana")
    print("=" * 60)

    # 1. Ingesta del MITECO
    df_gasolineras = fetch_gasolineras()

    # 2. Cargar y procesar el GPX
    track_original = load_gpx_track(gpx_path)

    # 3. Simplificación Ramer-Douglas-Peucker
    track_simplified = simplify_track(track_original, tolerance_deg=simplify_tolerance)

    # 4a. Buffer en UTM 30N (metros reales)
    gdf_buffer = build_route_buffer(track_simplified, buffer_meters=buffer_meters)

    # 4b. Construir GeoDataFrame de gasolineras con índice R-Tree en UTM 30N
    gdf_stations_utm = build_stations_geodataframe(df_gasolineras)

    # 4c. Spatial Join: gasolineras dentro del buffer
    gdf_within = spatial_join_within_buffer(gdf_stations_utm, gdf_buffer)

    # 4d. Extraer track en UTM
    gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simplified], crs=CRS_WGS84).to_crs(CRS_UTM30N)
    track_utm = gdf_track_utm.geometry.iloc[0]

    # 5. Filtrado de negocio: Top N más baratas por combustible o por tramos
    gdf_top = filter_cheapest_stations(
        gdf_within, 
        fuel_column=fuel_column, 
        top_n=top_n,
        track_utm=track_utm,
        segment_km=segment_km,
    )

    # 6. Generar mapa HTML
    ruta_html = None
    mapa_obj = None
    if not gdf_top.empty:
        ruta_html, mapa_obj = generate_map(
            track_original=track_original,
            gdf_top_stations=gdf_top,
            fuel_column=fuel_column,
            output_path=output_html,
        )
    else:
        print("[Mapa] [WARN] Sin gasolineras válidas para generar el mapa.")

    print("\n" + "=" * 60)
    print(" PIPELINE COMPLETADO")
    print("=" * 60)

    return {
        "track_original": track_original,
        "track_simplified": track_simplified,
        "gdf_buffer": gdf_buffer,
        "gdf_stations_utm": gdf_stations_utm,
        "gdf_within_buffer": gdf_within,
        "gdf_top_n": gdf_top,
        "output_html": ruta_html,
        "mapa_obj": mapa_obj,
    }


# ===========================================================================
# ENTRY POINT
# ===========================================================================

if __name__ == "__main__":
    # ----------------------------------------------------------------
    # CONFIGURACION POR DEFECTO
    # ----------------------------------------------------------------
    GPX_FILE = "ruta_miraflores.gpx"
    FUEL_COLUMN = "Precio Gasoleo A"
    BUFFER_METROS = 5000.0
    TOP_N = 5
    SIMPLIFY_TOL = 0.0005
    # OUTPUT_HTML = "mapa_gasolineras.html"  # Desactivado por defecto

    print("=" * 60)
    print(" OPTIMIZADOR DE GASOLINERAS EN RUTA -- Espana")
    print("=" * 60)

    # ----------------------------------------------------------------
    # SELECTOR DE COMBUSTIBLE
    # ----------------------------------------------------------------
    fuel_options = [
        ("Gasoleo A (Diesel normal)", "Precio Gasoleo A"),
        ("Gasoleo B (Agricola)", "Precio Gasoleo B"),
        ("Gasoleo Premium", "Precio Gasoleo Premium"),
        ("Gasolina 95 E5", "Precio Gasolina 95 E5"),
        ("Gasolina 95 E10", "Precio Gasolina 95 E10"),
        ("Gasolina 98 E5", "Precio Gasolina 98 E5"),
        ("Gasolina 98 E10", "Precio Gasolina 98 E10"),
        ("GLP (Autogas)", "Precio Gases licuados del petroleo"),
        ("GNC (Gas Natural Comprimido)", "Precio Gas Natural Comprimido"),
        ("GNL (Gas Natural Licuado)", "Precio Gas Natural Licuado"),
        ("Hidrogeno", "Precio Hidrogeno"),
    ]

    print("\nSelecciona el tipo de combustible:")
    for i, (name, _) in enumerate(fuel_options, 1):
        print(f"  {i}. {name}")
    
    while True:
        try:
            choice = input(f"\nElige una opcion (1-{len(fuel_options)}) [Default 1]: ").strip()
            if not choice:
                selected_fuel = fuel_options[0][1]
                break
            idx = int(choice)
            if 1 <= idx <= len(fuel_options):
                selected_fuel = fuel_options[idx-1][1]
                break
            else:
                print(f"[!] Introduce un numero entre 1 y {len(fuel_options)}.")
        except ValueError:
            print("[!] Por favor, introduce un numero valido.")

    # ----------------------------------------------------------------
    # OTROS PARAMETROS
    # ----------------------------------------------------------------
    print("\n--- Parametros adicionales (pulsa ENTER para usar el valor por defecto) ---")
    
    u_gpx = input(f"Ruta al archivo GPX [{GPX_FILE}]: ").strip()
    if u_gpx: GPX_FILE = u_gpx
    
    u_buf = input(f"Radio del buffer en metros [{int(BUFFER_METROS)}]: ").strip()
    if u_buf:
        try: BUFFER_METROS = float(u_buf)
        except ValueError: print(f"  [!] Valor no valido, usando {BUFFER_METROS}m.")

    u_top = input(f"Numero de gasolineras mas baratas a mostrar [{TOP_N}]: ").strip()
    if u_top:
        try: TOP_N = int(u_top)
        except ValueError: print(f"  [!] Valor no valido, usando {TOP_N}.")

    # ----------------------------------------------------------------
    # COMPROBACION Y EJECUCION
    # ----------------------------------------------------------------
    gpx_path = Path(GPX_FILE)
    if not gpx_path.exists():
        print(f"\n[WARN] No se encontro '{GPX_FILE}'.")
        print("Crea un GPX de prueba ejecutando: python crear_gpx_prueba.py")
    else:
        resultados = run_pipeline(
            gpx_path=gpx_path,
            fuel_column=selected_fuel,
            buffer_meters=float(BUFFER_METROS),
            top_n=int(TOP_N),
            simplify_tolerance=float(SIMPLIFY_TOL),
            output_html=None,
        )

        print(f"\n[RESUMEN FINAL]:")
        print(f"  - Combustible: {selected_fuel}")
        print(f"  - Gasolineras encontradas: {len(resultados['gdf_within_buffer'])}")
        print(f"  - Top {TOP_N} mas baratas mostradas en el mapa.")
        if resultados["output_html"]:
            print(f"  - Mapa guardado en: {resultados['output_html']}")


# ===========================================================================
# FUNCIONES AUXILIARES: RADAR DE AUTONOMÍA
# ===========================================================================

def calculate_autonomy_radar(track: LineString, gdf_top: gpd.GeoDataFrame, autonomia_km: float) -> tuple[list[dict], float]:
    """
    Calcula los intervalos y segmentos geográficos en función de la autonomía de un vehículo,
    desacoplando esta lógica analítica espacial (GIS) del script app.py de Streamlit.

    Parameters
    ----------
    track : LineString
        Ruta original completa.
    gdf_top : gpd.GeoDataFrame
        Gasolineras identificadas.
    autonomia_km : float
        Límite del depósito del usuario en km.

    Returns
    -------
    tuple[list[dict], float]
        Una lista de diccionarios representando los tramos del viaje, y la longitud total del track.
    """
    import pyproj as _pyproj

    _geod_radar = _pyproj.Geod(ellps="WGS84")
    _track_coords = list(track.coords)
    _lons = [c[0] for c in _track_coords]
    _lats = [c[1] for c in _track_coords]
    _, _, _dists_m = _geod_radar.inv(_lons[:-1], _lats[:-1], _lons[1:], _lats[1:])
    route_total_km = sum(_dists_m) / 1000.0

    station_km_list: list[float] = []
    if not gdf_top.empty and "km_ruta" in gdf_top.columns:
        station_km_list = sorted(gdf_top["km_ruta"].dropna().tolist())

    checkpoints = [0.0] + station_km_list + [route_total_km]
    tramos: list[dict] = []

    for j in range(len(checkpoints) - 1):
        km_inicio = checkpoints[j]
        km_fin    = checkpoints[j + 1]
        gap_km    = km_fin - km_inicio

        if autonomia_km > 0:
            pct = gap_km / autonomia_km
            if pct >= 1.0:
                nivel = "critico"
                emoji = "🔴"
                label = "CRÍTICO"
            elif pct >= 0.80:
                nivel = "atencion"
                emoji = "🟡"
                label = "ATENCIÓN"
            else:
                nivel = "seguro"
                emoji = "🟢"
                label = "SEGURO"
        else:
            pct = 0.0
            nivel = "seguro"
            emoji = "🟢"
            label = "—"

        if j == 0 and station_km_list:
            nombre_origen = "Inicio de ruta"
            nombre_destino = gdf_top.sort_values("km_ruta").iloc[0].get("Rótulo", f"Gasolinera #{j+1}")
        elif j == len(checkpoints) - 2 and station_km_list:
            nombre_origen = gdf_top.sort_values("km_ruta").iloc[j - 1].get("Rótulo", f"Gasolinera #{j}") if j > 0 else "Inicio"
            nombre_destino = "Fin de ruta"
        elif station_km_list and 0 < j < len(station_km_list):
            sorted_gdf = gdf_top.sort_values("km_ruta")
            nombre_origen  = sorted_gdf.iloc[j - 1].get("Rótulo", f"Gasolinera #{j}") if j > 0 else "Inicio"
            nombre_destino = sorted_gdf.iloc[j].get("Rótulo", f"Gasolinera #{j+1}")
        else:
            nombre_origen  = f"Km {km_inicio:.0f}"
            nombre_destino = f"Km {km_fin:.0f}"

        tramos.append({
            "km_inicio":    km_inicio,
            "km_fin":       km_fin,
            "gap_km":       gap_km,
            "nivel":        nivel,
            "pct":          pct,
            "emoji":        emoji,
            "label":        label,
            "origen":       nombre_origen,
            "destino":      nombre_destino,
        })

    return tramos, route_total_km
