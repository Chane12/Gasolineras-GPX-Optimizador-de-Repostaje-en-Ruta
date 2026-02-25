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
                resp = requests.get(proxy_url, headers=headers, timeout=timeout + 30)
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
        _track = track_utm
        # Calcular el punto de la ruta (en metros) al que se proyecta la gasolinera
        gdf_valid["km_ruta"] = gdf_valid.geometry.apply(lambda geom: _track.project(geom) / 1000.0)

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
# 5b. FILTRO FINO — OSRM Hybrid Funnel
# ===========================================================================

# URL pública gratuita de OSRM. Se puede sustituir por una instancia propia.
_OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"


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
        route = data.get("routes", [None])[0]
        if route is None:
            return None
        leg = route.get("legs", [None])[0]
        if leg is None:
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
    import math as _math
    gdf = gdf_top.copy()
    gdf["osrm_distance_km"] = float("nan")
    gdf["osrm_duration_min"] = float("nan")

    # Reproyectar gasolineras a WGS84 para obtener lon/lat de la gasolinera
    gdf_wgs84 = gdf.to_crs("EPSG:4326")

    for idx in gdf.index:
        row_wgs84 = gdf_wgs84.loc[idx]
        gas_lon = row_wgs84.geometry.x
        gas_lat = row_wgs84.geometry.y

        # 1. Punto más cercano de la ruta GPX a esta gasolinera
        #    ``project`` devuelve la distancia curvilínea (en grados, pero
        #    suficiente para encontrar el índice relativo del waypoint exacto).
        dist_along = track_original.project(
            Point(gas_lon, gas_lat), normalized=False
        )
        nearest_on_route = track_original.interpolate(dist_along)
        origin_lon = nearest_on_route.x
        origin_lat = nearest_on_route.y

        # 2. Llamada defensiva a OSRM
        result = get_real_distance_osrm(
            lon_origen=origin_lon,
            lat_origen=origin_lat,
            lon_destino=gas_lon,
            lat_destino=gas_lat,
        )

        if result is not None:
            gdf.at[idx, "osrm_distance_km"] = round(result["distance_km"], 2)
            gdf.at[idx, "osrm_duration_min"] = round(result["duration_min"], 1)
            print(
                f"[OSRM] {row_wgs84.get('Rótulo', idx)}: "
                f"{result['distance_km']:.2f} km / {result['duration_min']:.1f} min"
            )

        if delay_s > 0:
            time.sleep(delay_s)

    return gdf


# ===========================================================================
# 5c. PLANIFICADOR DE PARADAS — Price-Optimal Lazy Greedy
# ===========================================================================

class ImpossibleRouteError(ValueError):
    """Se lanza cuando no existe ninguna gasolinera alcanzable desde la posición actual."""


def calculate_optimal_stops(
    gdf_within: gpd.GeoDataFrame,
    fuel_column: str,
    autonomia_actual_km: float,
    rango_util_maximo_km: float,
    distancia_total_ruta_km: float,
    deposito_total_l: float,
    consumo_l100km: float,
) -> tuple[list[dict], gpd.GeoDataFrame]:
    """
    Genera un itinerario de repostaje óptimo usando el algoritmo
    "Price-Optimal Lazy Greedy":

    - **Lazy**: no para antes de lo necesario (maximiza la distancia entre
      paradas, minimizando el número de paradas).
    - **Price-Optimal**: dentro de la zona de búsqueda, elige siempre la
      gasolinera más barata.

    Estrategia de ventana
    ----------------------
    En cada iteración la "zona de confort" es la segunda mitad del rango
    útil disponible:  [km_actual + R * 0.5, km_actual + R].
    Buscar en la segunda mitad (50-100 % del rango) garantiza que no
    pararemos antes de tiempo, mientras dejamos margen para encontrar
    candidatos baratos.  Si esa ventana está vacía se hace backtracking
    progresivo (desde R hasta 1 km) para encontrar la gasolinera más
    próxima al límite máximo alcanzable.

    Parámetros
    ----------
    gdf_within : gpd.GeoDataFrame
        Gasolineras filtradas por buffer (EPSG:25830), con columna ``km_ruta``
        (distancia proyectada sobre el track en km) y precio válido.
    fuel_column : str
        Columna de precio activa.
    autonomia_actual_km : float
        Kilómetros que puedes recorrer con el combustible de salida.
    rango_util_maximo_km : float
        Kilómetros máximos con el depósito lleno con margen de reserva
        (típicamente ``autonomía_máxima * 0.85``).
    distancia_total_ruta_km : float
        Longitud total de la ruta en km.
    deposito_total_l : float
        Capacidad total del depósito en litros.
    consumo_l100km : float
        Consumo del vehículo en L/100 km.

    Devuelve
    -------
    tuple[list[dict], gpd.GeoDataFrame]
        - Lista de paradas ordenadas. Cada elemento es un dict con:
          ``nombre``, ``municipio``, ``km_ruta``, ``precio``,
          ``litros_repostados``, ``coste_parada``.
        - GeoDataFrame con las gasolineras de las paradas seleccionadas
          (para renderizar en el mapa con generate_map).

    Lanza
    -----
    ImpossibleRouteError
        Si en algún punto no se puede alcanzar ninguna gasolinera dentro
        de la autonomía disponible.
    ValueError
        Si la columna de precio no existe o no hay precios válidos.
    """
    # --- Sanidad de inputs ---
    if fuel_column not in gdf_within.columns:
        raise ValueError(f"Columna '{fuel_column}' no encontrada en gdf_within.")

    mask = gdf_within[fuel_column].notna() & (gdf_within[fuel_column] > 0)
    gdf_valid = gdf_within[mask].copy()

    if "km_ruta" not in gdf_valid.columns:
        raise ValueError(
            "gdf_within debe contener la columna 'km_ruta'. "
            "Asegúrate de llamar a filter_cheapest_stations con track_utm."
        )

    if gdf_valid.empty:
        raise ImpossibleRouteError(
            "No hay gasolineras con precio válido dentro del corredor de la ruta."
        )

    # Columna estandarizada de precio
    gdf_valid["precio_seleccionado"] = gdf_valid[fuel_column]
    gdf_valid = gdf_valid.sort_values("km_ruta").reset_index(drop=True)

    # --- Estado inicial ---
    km_actual: float = 0.0
    R: float = autonomia_actual_km          # autonomía disponible en este instante
    paradas: list[dict] = []
    selected_indices: list[int] = []

    iter_count = 0
    MAX_ITER = 500   # protección contra bucles infinitos

    print(f"\n[Greedy] Ruta: {distancia_total_ruta_km:.1f} km | "
          f"Autonomía inicial: {autonomia_actual_km:.1f} km | "
          f"Rango útil máx: {rango_util_maximo_km:.1f} km")

    while km_actual + R < distancia_total_ruta_km:
        iter_count += 1
        if iter_count > MAX_ITER:
            raise ImpossibleRouteError(
                "El algoritmo no convergió. Comprueba los parámetros de autonomía y ruta."
            )

        limite_max = km_actual + R           # no podemos ir más lejos
        zona_confort_inicio = km_actual + R * 0.5   # mitad del rango disponible

        # --- Zona de confort: [50% R, 100% R] desde posición actual ---
        candidatos = gdf_valid[
            (gdf_valid["km_ruta"] >= zona_confort_inicio) &
            (gdf_valid["km_ruta"] <= limite_max)
        ]

        # --- Backtracking progresivo si la zona de confort está vacía ---
        if candidatos.empty:
            print(f"[Greedy] Zona de confort vacía en km {km_actual:.1f}. "
                  f"Buscando en rango completo [km_actual+1, {limite_max:.1f}]...")
            candidatos = gdf_valid[
                (gdf_valid["km_ruta"] > km_actual) &
                (gdf_valid["km_ruta"] <= limite_max)
            ]

        if candidatos.empty:
            raise ImpossibleRouteError(
                f"Imposible completar la ruta: no hay gasolineras alcanzables "
                f"desde km {km_actual:.1f} con {R:.1f} km de autonomía. "
                f"Prueba a ampliar el radio de búsqueda o a revisar los datos del vehículo."
            )

        # --- Selección: la más barata dentro de los candidatos ---
        mejor_idx = candidatos["precio_seleccionado"].idxmin()
        mejor = gdf_valid.loc[mejor_idx]

        km_gas = float(mejor["km_ruta"])
        precio = float(mejor["precio_seleccionado"])
        nombre = str(mejor.get("Rótulo", "Sin nombre"))
        municipio = str(mejor.get("Municipio", ""))

        # Litros consumidos para llegar a esta gasolinera
        km_recorridos = km_gas - km_actual
        litros_consumidos = km_recorridos * consumo_l100km / 100.0
        # Llenamos el depósito (asumimos llenado completo en cada parada)
        litros_restantes_al_llegar = (R - km_recorridos) * consumo_l100km / 100.0
        litros_repostados = max(0.0, deposito_total_l - litros_restantes_al_llegar)
        coste_parada = litros_repostados * precio

        parada = {
            "numero": len(paradas) + 1,
            "nombre": nombre,
            "municipio": municipio,
            "km_ruta": km_gas,
            "precio_eur_l": precio,
            "litros_repostados": round(litros_repostados, 2),
            "coste_parada_eur": round(coste_parada, 2),
            "osrm_distance_km": float(mejor.get("osrm_distance_km", float("nan"))),
            "osrm_duration_min": float(mejor.get("osrm_duration_min", float("nan"))),
        }
        paradas.append(parada)
        selected_indices.append(mejor_idx)

        print(
            f"[Greedy] Parada {len(paradas)}: Km {km_gas:.1f} | "
            f"{nombre} ({municipio}) | {precio:.3f} €/L | "
            f"~{litros_repostados:.1f} L repostados (~{coste_parada:.2f} €)"
        )

        # Actualizar estado
        km_actual = km_gas
        R = rango_util_maximo_km   # depósito lleno tras cada parada

    print(f"\n[Greedy] ✅ Itinerario: {len(paradas)} paradas. "
          f"Coste total estimado: {sum(p['coste_parada_eur'] for p in paradas):.2f} €")

    # GeoDataFrame de paradas para la visualización en el mapa
    gdf_stops = gdf_valid.loc[selected_indices].copy().reset_index(drop=True)
    return paradas, gdf_stops


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
            track_length_km = LineString(track_coords).length * 111.0  # grados → km aprox
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

        # Datos de OSRM (pueden ser NaN si la llamada falló)
        import math as _math
        osrm_dist = row.get("osrm_distance_km", float("nan"))
        osrm_dur = row.get("osrm_duration_min", float("nan"))
        if not _math.isnan(osrm_dist) and not _math.isnan(osrm_dur):
            osrm_line = (
                f'<p style="margin:4px 0; background:#f0fdf4; border-radius:4px; '
                f'padding:4px 6px; font-size:0.9em;">'
                f"🚗 <b>Desvío real:</b> {osrm_dist:.1f} km ({osrm_dur:.0f} min)</p>"
            )
        else:
            osrm_line = ""

        popup_html = f"""
        <div style="font-family:sans-serif; min-width:220px;">
            <h4 style="margin:0 0 6px; color:{color};">
                #{rank_visual} {nombre}
            </h4>
            <p style="margin:2px 0;">
                <b>💰 {fuel_column.replace("Precio ", "")}:</b>
                <span style="color:{color}; font-size:1.1em; font-weight:bold;">
                    {precio:.3f} €/L
                </span>
            </p>
            {osrm_line}
            <p style="margin:2px 0;"><b>📍</b> {direccion}</p>
            <p style="margin:2px 0;">
                {municipio}, {provincia}
            </p>
            <p style="margin:2px 0; color:#6b7280;">
                🕐 {horario}
            </p>
        </div>
        """

        # El CircleMarker dibuja el fondo de color
        folium.CircleMarker(
            location=[lat, lon],
            radius=18,
            color="white",
            weight=3,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=f"#{rank_visual} {nombre} -- {precio:.3f} EUR/L",
            popup=folium.Popup(popup_html, max_width=280),
        ).add_to(mapa)

        # El DivIcon superpone el número.
        # Le añadimos EL MISMO POPUP y TOOLTIP para que, si el usuario hace clic o hover 
        # en el número (que está por encima en el z-index), también funcione perfectamente.
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size:13px; font-weight:bold;
                    color:white; text-align:center;
                    line-height:36px; width:36px;
                    border-radius:50%; /* Ayuda a que la forma coincida con el círculo */
                ">#{rank_visual}</div>
                """,
                icon_size=(36, 36),
                icon_anchor=(18, 18),
            ),
            tooltip=f"#{rank_visual} {nombre} -- {precio:.3f} EUR/L",
            popup=folium.Popup(popup_html, max_width=280),
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
