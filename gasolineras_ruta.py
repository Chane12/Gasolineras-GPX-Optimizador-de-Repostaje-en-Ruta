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

import math
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

    El JSON devuelto tiene una clave "ListaEESSPrecio" con los registros.
    Los campos numéricos (precios y coordenadas) usan coma como separador
    decimal en lugar de punto, por lo que hay que limpiarlos.

    Parameters
    ----------
    timeout : int
        Segundos de espera máximos para la petición HTTP.

    Returns
    -------
    pd.DataFrame
        DataFrame con todas las gasolineras y coordenadas ya como float.
        Las filas sin latitud o longitud válida son eliminadas.
    """
    import subprocess
    import json
    import sys

    print(f"[MITECO] Descargando datos via PowerShell (Invoke-RestMethod)...")
    
    # Usamos shell=True y redirección para evitar problemas de buffer en algunos entornos
    ps_command = (
        f'$ProgressPreference = "SilentlyContinue"; '
        f'Invoke-RestMethod -Uri "{MITECO_API_URL}" -Method Get | ConvertTo-Json -Depth 10'
    )
    
    try:
        # Usamos run con capture_output=True pero sin text=True para manejar bytes
        # y evitar errores de encoding automáticos
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            check=True
        )
        
        if not result.stdout:
            print(f"[MITECO] ERROR: PowerShell no devolvió datos.")
            print(f"STDERR: {result.stderr.decode('cp1252', errors='replace')}")
            raise ValueError("PowerShell returned no data")

        # El encoding de PowerShell en máquinas Windows españolas suele ser cp1252 o similar
        # Usamos errors='replace' para no bloquearnos por un caracter mal formado
        raw_data = result.stdout.decode('cp1252', errors='replace')
        
        data = json.loads(raw_data)
    except Exception as e:
        print(f"[MITECO] Error crítico: {e}")
        if 'result' in locals():
            print(f"Detalle STDERR: {result.stderr.decode('cp1252', errors='replace')[:500]}")
        raise e
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

    with open(gpx_path, "r", encoding="utf-8") as f:
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

    # Ordenar y seleccionar Top N
    gdf_top = gdf_valid.nsmallest(top_n, fuel_column).reset_index(drop=True)

    print(f"\n[Filtrado] Top {top_n} más baratas para '{fuel_column}':")
    for i, row in gdf_top.iterrows():
        nombre = row.get("Rótulo", row.get("C.P.", "N/A"))
        municipio = row.get("Municipio", "")
        precio = row["precio_seleccionado"]
        print(f"  #{i+1} {nombre} ({municipio}) --> {precio:.3f} EUR/L")

    return gdf_top


# ===========================================================================
# 6. OUTPUT VISUAL - Mapa Folium
# ===========================================================================

def generate_map(
    track_original: LineString,
    gdf_top_stations: gpd.GeoDataFrame,
    fuel_column: str,
    output_path: str | Path = "mapa_gasolineras.html",
) -> Path:
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
    tuple[Path, folium.Map]
        Ruta absoluta del archivo HTML generado y el objeto folium.Map.
    """
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
    # Folium/Leaflet usa (lat, lon), no (lon, lat) como Shapely.
    route_latlon = [(lat, lon) for lon, lat in track_coords]
    folium.PolyLine(
        locations=route_latlon,
        color="#2563EB",    # azul
        weight=4,
        opacity=0.85,
        tooltip="Ruta GPX",
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

    # Colores degradados para el ranking (verde=barato, rojo=caro)
    rank_colors = ["#16a34a", "#65a30d", "#ca8a04", "#ea580c", "#dc2626"]

    for rank, (_, row) in enumerate(gdf_wgs84.iterrows()):
        lat = row.geometry.y
        lon = row.geometry.x
        precio = row.get("precio_seleccionado", float("nan"))
        nombre = row.get("Rótulo", "Sin nombre")
        municipio = row.get("Municipio", "")
        provincia = row.get("Provincia", "")
        direccion = row.get("Dirección", "")
        horario = row.get("Horario", "")
        color = rank_colors[rank] if rank < len(rank_colors) else "#6b7280"

        popup_html = f"""
        <div style="font-family:sans-serif; min-width:220px;">
            <h4 style="margin:0 0 6px; color:{color};">
                #{rank+1} {nombre}
            </h4>
            <p style="margin:2px 0;">
                <b>💰 {fuel_column.replace("Precio ", "")}:</b>
                <span style="color:{color}; font-size:1.1em; font-weight:bold;">
                    {precio:.3f} €/L
                </span>
            </p>
            <p style="margin:2px 0;"><b>📍</b> {direccion}</p>
            <p style="margin:2px 0;">
                {municipio}, {provincia}
            </p>
            <p style="margin:2px 0; color:#6b7280;">
                🕐 {horario}
            </p>
        </div>
        """

        folium.CircleMarker(
            location=[lat, lon],
            radius=14,
            color="white",
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            tooltip=f"#{rank+1} {nombre} -- {precio:.3f} EUR/L",
            popup=folium.Popup(popup_html, max_width=280),
        ).add_to(mapa)

        # Número de ranking encima del círculo
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size:11px; font-weight:bold;
                    color:white; text-align:center;
                    line-height:28px; width:28px;
                ">#{rank+1}</div>
                """,
                icon_size=(28, 28),
                icon_anchor=(14, 14),
            ),
        ).add_to(mapa)

    # Leyenda
    legend_html = f"""
    <div style="
        position:fixed; bottom:30px; left:30px;
        z-index:1000; background:white;
        padding:14px 18px; border-radius:8px;
        box-shadow:0 2px 8px rgba(0,0,0,0.2);
        font-family:sans-serif; font-size:13px;
    ">
        <b>Optimizador de Gasolineras</b><br>
        <span style="color:#2563EB;">--</span> Ruta GPX<br>
        <span style="color:#16a34a;">o</span> Gasolineras mas baratas<br>
        <i style="font-size:11px; color:#888;">
            Combustible: {fuel_column.replace("Precio ", "")}
        </i>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(legend_html))

    # --- Control de capas ---
    folium.LayerControl().add_to(mapa)

    mapa.save(str(output_path))
    print(f"\n[Mapa] [SUCCESS] Mapa guardado en: {output_path.resolve()}")
    return output_path.resolve(), mapa


# ===========================================================================
# PIPELINE COMPLETO
# ===========================================================================

def run_pipeline(
    gpx_path: str | Path,
    fuel_column: str = "Precio Gasoleo A",
    buffer_meters: float = 5000.0,
    top_n: int = 5,
    simplify_tolerance: float = 0.0005,
    output_html: str | Path = "mapa_gasolineras.html",
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
    output_html : str | Path
        Ruta de salida del mapa HTML.

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

    # 5. Filtrado de negocio: Top N más baratas por combustible
    gdf_top = filter_cheapest_stations(gdf_within, fuel_column=fuel_column, top_n=top_n)

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
    OUTPUT_HTML = "mapa_gasolineras.html"

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
            output_html=OUTPUT_HTML,
        )

        print(f"\n[RESUMEN FINAL]:")
        print(f"  - Combustible: {selected_fuel}")
        print(f"  - Gasolineras encontradas: {len(resultados['gdf_within_buffer'])}")
        print(f"  - Top {TOP_N} mas baratas mostradas en el mapa.")
        if resultados["output_html"]:
            print(f"  - Mapa guardado en: {resultados['output_html']}")
