"""
src/optimizer/export.py
=======================
Export utilities: Google Maps URL generation, GPX enrichment with stops,
OSRM detour calculation, and trip plan GeoDataFrame preparation.
"""

from __future__ import annotations

import concurrent.futures
import random
import time
import urllib.parse as _up

import geopandas as gpd
import gpxpy
import gpxpy.gpx as _gpx
import pandas as pd
import requests
from shapely.geometry import LineString, Point

from src.config import GMAPS_MAX_WAYPOINTS, OSRM_BASE_URL
from src.spatial.nearest import build_kdtree_from_points, query_nearest


def prepare_export_gdf(
    mis_paradas: list[dict],
    fuel_column: str,
    precio_col_label: str,
) -> gpd.GeoDataFrame:
    """
    Convierte la lista de paradas en memoria a un GeoDataFrame en EPSG:4326
    listo para ser inyectado en GPX o en URL de Google Maps.
    """
    if not mis_paradas:
        return gpd.GeoDataFrame()

    df_plan = pd.DataFrame(mis_paradas)
    if "Km en Ruta" in df_plan.columns:
        df_plan = df_plan.sort_values("Km en Ruta").reset_index(drop=True)

    geometrias = [Point(row["_geom_x"], row["_geom_y"]) for _, row in df_plan.iterrows()]
    gdf_export = gpd.GeoDataFrame(df_plan, geometry=geometrias, crs="EPSG:4326")

    if "Marca" in gdf_export.columns:
        gdf_export["Rótulo"] = gdf_export["Marca"]
    else:
        gdf_export["Rótulo"] = "Gasolinera Seleccionada"

    if precio_col_label in gdf_export.columns:
        gdf_export[fuel_column] = gdf_export[precio_col_label]

    return gdf_export


def generate_google_maps_url(
    track: LineString,
    gdf_stops: gpd.GeoDataFrame,
) -> tuple[str, int]:
    """
    Genera una URL de Google Maps con la ruta multidestino.

    Parameters
    ----------
    track : LineString
        Track de la ruta en WGS84.
    gdf_stops : gpd.GeoDataFrame
        GeoDataFrame con las paradas de repostaje.

    Returns
    -------
    tuple[str, int]
        (url, n_truncated) — URL completa y nº de paradas omitidas.
    """
    coords = list(track.coords)
    lat_o, lon_o = coords[0][1], coords[0][0]
    lat_d, lon_d = coords[-1][1], coords[-1][0]

    n_truncated = 0
    waypoints_str = ""
    if gdf_stops is not None and not gdf_stops.empty:
        gdf_wgs84 = gdf_stops.to_crs("EPSG:4326")
        stops_all = [f"{row.geometry.y:.6f},{row.geometry.x:.6f}" for _, row in gdf_wgs84.iterrows()]
        if len(stops_all) > GMAPS_MAX_WAYPOINTS:
            n_truncated = len(stops_all) - GMAPS_MAX_WAYPOINTS
            stops_all = stops_all[:GMAPS_MAX_WAYPOINTS]
        waypoints_str = "|".join(stops_all)

    params: dict[str, str] = {
        "api": "1",
        "origin": f"{lat_o:.6f},{lon_o:.6f}",
        "destination": f"{lat_d:.6f},{lon_d:.6f}",
        "travelmode": "driving",
    }
    if waypoints_str:
        params["waypoints"] = waypoints_str

    url = "https://www.google.com/maps/dir/?" + _up.urlencode(params)
    return url, n_truncated


def get_real_distance_osrm(
    lon_origen: float,
    lat_origen: float,
    lon_destino: float,
    lat_destino: float,
    timeout: float = 5.0,
) -> dict | None:
    """
    Consulta la API pública de OSRM para obtener distancia y duración reales.

    Returns
    -------
    dict | None
        {"distance_km": float, "duration_min": float} o None si falla.
    """
    url = (
        f"{OSRM_BASE_URL}"
        f"/{lon_origen},{lat_origen}"
        f";{lon_destino},{lat_destino}"
        f"?overview=false&alternatives=false&steps=false"
    )
    headers = {"User-Agent": "OptimizadorGasolineras/1.0", "Accept": "application/json"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 429:
            print("[OSRM] Rate-limit (429). Usando fallback euclidiano.")
            return None
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != "Ok" or not data.get("routes"):
            return None

        route = data["routes"][0]
        if not route.get("legs"):
            return None

        leg = route["legs"][0]
        if "distance" not in leg or "duration" not in leg:
            return None

        return {
            "distance_km": leg["distance"] / 1000.0,
            "duration_min": leg["duration"] / 60.0,
        }
    except Exception as exc:
        print(f"[OSRM] Fallo silencioso ({type(exc).__name__}). Usando fallback euclidiano.")
        return None


def enrich_stations_with_osrm(
    gdf_top: gpd.GeoDataFrame,
    track_original: LineString,
    delay_s: float = 0.5,
):
    """
    Enriquece el GeoDataFrame de gasolineras con datos reales OSRM.
    Yields (idx, result_dict | None) for each station progresivamente.
    Implementa concurrencia segura y backoff exponencial para evitar saturar la API pública.
    """
    if gdf_top.empty:
        return

    gdf_wgs84 = gdf_top.to_crs("EPSG:4326")

    # Vectorized nearest-point computation (Shapely C-level)
    rutas_origen_dict = {}
    dist_along_array = gdf_wgs84.geometry.apply(lambda geom: track_original.project(geom))
    nearest_points = dist_along_array.apply(lambda d: track_original.interpolate(d))
    for idx, pt in zip(gdf_wgs84.index, nearest_points, strict=False):
        rutas_origen_dict[idx] = (pt.x, pt.y)

    def process_station(idx, row_wgs84):
        gas_lon = row_wgs84.geometry.x
        gas_lat = row_wgs84.geometry.y
        origin_lon, origin_lat = rutas_origen_dict[idx]

        max_retries = 3
        # Jitter aleatorio para desincronizar los workers y evitar picos de peticiones
        current_delay = delay_s + random.uniform(0.1, 0.4)

        for _attempt in range(max_retries):
            time.sleep(current_delay)

            d_ida = get_real_distance_osrm(origin_lon, origin_lat, gas_lon, gas_lat)
            if d_ida is not None:
                time.sleep(0.2) # Pausa mínima entre ida y vuelta
                d_vuelta = get_real_distance_osrm(gas_lon, gas_lat, origin_lon, origin_lat)
                if d_vuelta is not None:
                    return idx, {
                        "distance_km": d_ida["distance_km"] + d_vuelta["distance_km"],
                        "duration_min": d_ida["duration_min"] + d_vuelta["duration_min"],
                    }

            # Si devuelve None (por 429 Too Many Requests o error de ruta), aplicamos backoff
            current_delay *= 2.0

        return idx, None

    # max_workers=3 es conservador para la API pública de OSRM perdiendo latencia general
    # pero manteniendo fiabilidad frente a cuelgues, tal y como se requiere.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(process_station, idx, row): idx
            for idx, row in gdf_wgs84.iterrows()
        }

        # as_completed permite que main thread vaya haciendo el progresivo yield
        # a Streamlit conforme terminan, no esperando a todos al final.
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            try:
                result_idx, result = future.result()
                yield result_idx, result
            except Exception as e:
                print(f"[OSRM] Fallo fatal concurrente en idx {idx}: {e}")
                yield idx, None


def enrich_gpx_with_stops(
    gpx_bytes: bytes,
    gdf_stops: gpd.GeoDataFrame,
    fuel_column: str = "",
) -> str:
    """
    Inyecta las paradas de repostaje como Waypoints (<wpt>) dentro del GPX
    original y realiza Track Splicing via OSRM.

    Returns
    -------
    str
        Cadena XML en formato GPX.
    """
    gpx_obj = gpxpy.parse(gpx_bytes.decode("utf-8", errors="replace"))

    if gdf_stops is None or gdf_stops.empty:
        return gpx_obj.to_xml()

    gdf_wgs84 = gdf_stops.to_crs("EPSG:4326")

    # 1. Create waypoints
    paradas = []
    for i, (_, row) in enumerate(gdf_wgs84.iterrows(), start=1):
        lat = row.geometry.y
        lon = row.geometry.x

        rotulo = row.get("Rótulo", f"Gasolinera #{i}")
        litros = row.get("litros_a_repostar", 0.0)
        coste = row.get("coste_parada_eur", 0.0)
        precio = row.get(fuel_column, 0.0) if fuel_column else 0.0

        nombre_wpt = (
            f"⛽ {i}. {rotulo} | {litros:.1f} L @ {precio:.3f} €/L = {coste:.2f} €"
            if litros > 0
            else f"⛽ {i}. {rotulo} | {precio:.3f} €/L"
        )

        wpt = _gpx.GPXWaypoint(
            latitude=lat,
            longitude=lon,
            name=nombre_wpt,
            symbol="Fuel",
            description=(
                f"Repostar en {rotulo}. Precio: {precio:.3f} €/L. Coste estimado: {coste:.2f} €."
                if coste > 0
                else f"Gasolinera {rotulo}. Precio: {precio:.3f} €/L."
            ),
        )
        gpx_obj.waypoints.append(wpt)
        paradas.append({"lon": lon, "lat": lat})

    # 2. Build KD-Tree from track points for nearest-neighbor splicing
    puntos_ref = []
    indices = []
    for t_idx, track in enumerate(gpx_obj.tracks):
        for s_idx, segment in enumerate(track.segments):
            for p_idx, point in enumerate(segment.points):
                puntos_ref.append((point.longitude, point.latitude))
                indices.append((t_idx, s_idx, p_idx, point.longitude, point.latitude))

    tree = build_kdtree_from_points(puntos_ref) if puntos_ref else None

    split_points = []
    for parada in paradas:
        if tree is not None:
            _, idx_kdtree = query_nearest(tree, (parada["lon"], parada["lat"]))
            closest_idx = indices[idx_kdtree]
            split_points.append({
                "idx": closest_idx,
                "station_lon": parada["lon"],
                "station_lat": parada["lat"],
            })

    split_points.sort(key=lambda x: (x["idx"][0], x["idx"][1], x["idx"][2]), reverse=True)

    # 3. OSRM-based Track Splicing
    headers = {"User-Agent": "OptimizadorGasolineras/1.0", "Accept": "application/json"}

    for sp in split_points:
        t_idx, s_idx, p_idx, split_lon, split_lat = sp["idx"]
        station_lon = sp["station_lon"]
        station_lat = sp["station_lat"]

        segment = gpx_obj.tracks[t_idx].segments[s_idx]

        reinc_idx = p_idx
        dist_accum = 0.0
        max_search = min(p_idx + 150, len(segment.points) - 1)

        for i in range(p_idx, max_search):
            p1 = segment.points[i]
            p2 = segment.points[i + 1]
            d = ((p2.longitude - p1.longitude) ** 2 + (p2.latitude - p1.latitude) ** 2) ** 0.5 * 111000
            dist_accum += d
            reinc_idx = i + 1
            if dist_accum > 1000.0:
                break

        if dist_accum <= 1000.0 and reinc_idx == p_idx:
            reinc_idx = min(p_idx + 1, len(segment.points) - 1)

        reinc_lon = segment.points[reinc_idx].longitude
        reinc_lat = segment.points[reinc_idx].latitude

        entrada = []
        salida = []

        try:
            url_in = (
                f"{OSRM_BASE_URL}"
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

        time.sleep(0.3)

        try:
            url_out = (
                f"{OSRM_BASE_URL}"
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
        if entrada:
            for coords in entrada[1:]:
                new_points.append(_gpx.GPXTrackPoint(latitude=coords[1], longitude=coords[0]))
        if not entrada and not salida:
            new_points.append(_gpx.GPXTrackPoint(latitude=station_lat, longitude=station_lon))
        if salida:
            for coords in salida[1:]:
                new_points.append(_gpx.GPXTrackPoint(latitude=coords[1], longitude=coords[0]))

        if new_points:
            segment.points = segment.points[: p_idx + 1] + new_points + segment.points[reinc_idx:]

    return gpx_obj.to_xml()
