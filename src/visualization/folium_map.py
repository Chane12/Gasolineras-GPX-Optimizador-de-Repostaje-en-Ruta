"""
src/visualization/folium_map.py
===============================
Folium map generation for the route and fuel stations.
"""

from __future__ import annotations

import math
from pathlib import Path

import folium
import geopandas as gpd
import pandas as pd
from pyproj import Geod
from shapely.geometry import LineString

from src.config import CRS_WGS84


def generate_map(
    track_original: LineString,
    gdf_top_stations: gpd.GeoDataFrame,
    fuel_column: str,
    output_path: str | Path | None = None,
    autonomy_km: float = 0.0,
    gdf_all_stations: gpd.GeoDataFrame | None = None,
) -> tuple[Path | None, folium.Map]:
    """
    Genera un mapa interactivo en HTML con folium.

    Parameters
    ----------
    track_original : LineString
        Ruta GPX original en EPSG:4326.
    gdf_top_stations : gpd.GeoDataFrame
        Top N gasolineras en EPSG:25830.
    fuel_column : str
        Nombre del combustible seleccionado.
    output_path : str | Path
        Ruta donde guardar el HTML (opcional).
    autonomy_km : float
        Kilómetros de autonomía del vehículo (0 = desactivado).
    gdf_all_stations : gpd.GeoDataFrame | None
        Conjunto total de estaciones para pintar zonas de riesgo.

    Returns
    -------
    tuple[Optional[Path], folium.Map]
        Ruta del archivo HTML y el objeto folium.Map.
    """
    if output_path is not None:
        output_path = Path(output_path)

    track_coords = list(track_original.coords)
    center_lon = sum(c[0] for c in track_coords) / len(track_coords)
    center_lat = sum(c[1] for c in track_coords) / len(track_coords)

    mapa = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles="OpenStreetMap")

    lats_all = [c[1] for c in track_coords]
    lons_all = [c[0] for c in track_coords]
    mapa.fit_bounds([[min(lats_all), min(lons_all)], [max(lats_all), max(lons_all)]], padding=(30, 30))

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="ESRI World Imagery",
        name="Satélite ESRI",
        overlay=False,
        control=True,
        show=False,
    ).add_to(mapa)

    route_latlon = [(lat, lon) for lon, lat in track_coords]
    folium.PolyLine(
        locations=route_latlon, color="#2563EB", weight=4, opacity=0.85, tooltip="Ruta GPX", name="Ruta GPX"
    ).add_to(mapa)

    # --- Danger zones ---
    if autonomy_km > 0:
        _source_gdf = gdf_all_stations if gdf_all_stations is not None else gdf_top_stations

        if not _source_gdf.empty and fuel_column in _source_gdf.columns:
            _source_gdf = _source_gdf.copy()
            _source_gdf[fuel_column] = pd.to_numeric(_source_gdf[fuel_column], errors="coerce")
            _source_gdf = _source_gdf[_source_gdf[fuel_column].notna() & (_source_gdf[fuel_column] > 0)]

        station_km_list = []
        if not _source_gdf.empty:
            gdf_for_danger = _source_gdf.copy()
            if gdf_for_danger.crs and gdf_for_danger.crs.to_epsg() != 4326:
                gdf_for_danger = gdf_for_danger.to_crs(CRS_WGS84)
            if "km_ruta" in gdf_for_danger.columns:
                station_km_list = sorted(gdf_for_danger["km_ruta"].dropna().tolist())

        if station_km_list:
            _geod = Geod(ellps="WGS84")
            _lons = [c[0] for c in track_coords]
            _lats = [c[1] for c in track_coords]
            _, _, _dist_m = _geod.inv(_lons[:-1], _lats[:-1], _lons[1:], _lats[1:])
            track_length_km = sum(_dist_m) / 1000.0
            checkpoints = [0.0] + station_km_list + [track_length_km]

            danger_segments = []
            for j in range(len(checkpoints) - 1):
                gap = checkpoints[j + 1] - checkpoints[j]
                if gap > autonomy_km:
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

    # Start/end markers
    folium.Marker(
        location=route_latlon[0], tooltip="Inicio de ruta", icon=folium.Icon(color="green", icon="play", prefix="fa")
    ).add_to(mapa)
    folium.Marker(
        location=route_latlon[-1], tooltip="Fin de ruta", icon=folium.Icon(color="red", icon="stop", prefix="fa")
    ).add_to(mapa)

    # --- Station markers ---
    gdf_wgs84 = gdf_top_stations.to_crs(CRS_WGS84)

    precio_min = gdf_wgs84["precio_seleccionado"].min()
    precio_max = gdf_wgs84["precio_seleccionado"].max()

    def price_to_hex_color(precio: float) -> str:
        if precio_max == precio_min:
            return "#16a34a"
        t = (precio - precio_min) / (precio_max - precio_min)
        hue = 120 * (1.0 - t)
        saturation = 88
        lightness = 40
        h = hue / 360.0
        s = saturation / 100.0
        l_val = lightness / 100.0
        if s == 0:
            r = g = b = l_val
        else:

            def hue_to_rgb(p: float, q: float, t_val: float) -> float:
                t_val = t_val % 1.0
                if t_val < 1 / 6:
                    return p + (q - p) * 6 * t_val
                if t_val < 1 / 2:
                    return q
                if t_val < 2 / 3:
                    return p + (q - p) * (2 / 3 - t_val) * 6
                return p

            q = l_val * (1 + s) if l_val < 0.5 else l_val + s - l_val * s
            p = 2 * l_val - q
            r = hue_to_rgb(p, q, h + 1 / 3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1 / 3)
        return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

    gdf_wgs84["_rank_temp"] = (
        gdf_wgs84["precio_seleccionado"].rank(method="min", ascending=True).fillna(9999).astype(int)
    )
    gdf_wgs84 = gdf_wgs84.sort_values(by=["_rank_temp", "precio_seleccionado"], ascending=[False, False])

    for _, row in gdf_wgs84.iterrows():
        rank_visual = int(row["_rank_temp"])
        lat = row.geometry.y
        lon = row.geometry.x
        precio = row.get("precio_seleccionado", float("nan"))
        nombre = row.get("Rótulo", "Sin nombre")
        municipio = row.get("Municipio", "")
        provincia = row.get("Provincia", "")
        direccion = row.get("Dirección", "")
        horario = row.get("Horario", "")
        color = price_to_hex_color(precio)

        osrm_dist = row.get("osrm_distance_km", float("nan"))
        osrm_dur = row.get("osrm_duration_min", float("nan"))
        try:
            _osrm_ok = not math.isnan(osrm_dist) and not math.isnan(osrm_dur)
        except TypeError:
            _osrm_ok = False
        osrm_line = (
            f'<div class="popup-osrm-box">&#128652; <b>Desvío real:</b> {osrm_dist:.1f} km &nbsp;·&nbsp; {osrm_dur:.0f} min</div>'
            if _osrm_ok
            else ""
        )

        maps_url = f"https://maps.google.com/?q={lat},{lon}"
        badge_color = "#16a34a" if rank_visual == 1 else ("#2563eb" if rank_visual <= 3 else color)
        badge_label = "⭐ Más Barata" if rank_visual == 1 else f"#{rank_visual}"

        popup_html = f"""
        <div class="custom-popup" style="font-family:'Segoe UI',Arial,sans-serif; min-width:240px; max-width:280px;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
                <b style="font-size:1rem; margin-right: 4px;" class="popup-title">{nombre}</b>
                <span style="background:{badge_color}; color:white; font-size:0.7rem;
                             font-weight:700; padding:2px 7px; border-radius:99px;
                             white-space:nowrap; margin-left:6px;">{badge_label}</span>
            </div>
            <div class="popup-price-box" style="text-align:center; border-radius:8px; padding:10px 0; margin-bottom:8px;">
                <div style="font-size:2rem; font-weight:800; color:{color}; line-height:1;">{f"{precio:.3f}" if not math.isnan(precio) else "N/A"} €/L</div>
                <div class="popup-price-subtitle" style="font-size:0.78rem; margin-top:2px;">
                    {fuel_column.replace("Precio ", "")} &nbsp;·&nbsp; Km {row.get('km_ruta', 0):.1f} en ruta</div>
            </div>
            {osrm_line}
            <div class="popup-text" style="font-size:0.82em; margin:4px 0;">
                &#128205; {direccion}<br>{municipio}, {provincia}</div>
            <div class="popup-text-muted" style="font-size:0.78em; margin:4px 0;">
                &#128336; {horario if horario else '—'}</div>
            <a href="{maps_url}" target="_blank" class="popup-btn" style="
                display:block; margin-top:10px; padding:8px;
                background:#2563eb; color:white; text-align:center;
                text-decoration:none; border-radius:6px;
                font-size:0.85em; font-weight:600;">&#128652;&nbsp; Llévame aquí (Google Maps)</a>
        </div>
        """

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

        precio_str = f"{precio:.2f}€" if not math.isnan(precio) else "–"
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

    # Legend
    legend_html = f"""
    <div class="folium-legend" style="
        position:fixed; bottom:30px; left:30px;
        z-index:9999; padding:14px 18px; border-radius:8px;
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
            border: 1px solid rgba(128,128,128,0.3);
        "></div>
        <div style="display:flex; justify-content:space-between; font-size:11px;">
            <span>&#9679; {precio_min:.3f}€ (más barato)</span>
            <span>{precio_max:.3f}€ &#9679;</span>
        </div>
    </div>
    """
    mapa.get_root().html.add_child(folium.Element(legend_html))

    dark_mode_css = """
    <style>
    .popup-osrm-box { margin:6px 0; padding:6px 8px; background:#eff6ff; border-left:3px solid #2563eb; border-radius:4px; font-size:0.82em; color:#1e40af; }
    .popup-title { color: #0f172a; }
    .popup-price-box { background: #f8fafc; }
    .popup-price-subtitle { color: #64748b; }
    .popup-text { color: #475569; }
    .popup-text-muted { color: #94a3b8; }
    .folium-legend { background: white; color: #111827; }
    @media (max-width: 600px) {
        .folium-legend {
            font-size: 10px !important; padding: 6px 8px !important;
            min-width: 0 !important; max-width: 130px !important;
            bottom: 10px !important; left: 8px !important;
        }
        .folium-legend b { font-size: 10px !important; }
    }
    </style>
    """
    mapa.get_root().html.add_child(folium.Element(dark_mode_css))
    folium.LayerControl().add_to(mapa)

    if output_path is not None:
        mapa.save(str(output_path))
        print(f"\n[Mapa] [SUCCESS] Mapa guardado en: {output_path.resolve()}")

    return (output_path.resolve() if output_path else None), mapa
