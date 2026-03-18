"""
src/pipeline/runner.py
======================
Pipeline central que maneja la lógica geoespacial y de búsqueda de la aplicación.
"""

import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st

from src.config import CRS_UTM30N, CRS_WGS84
from src.ingestion.geocoder import RouteTextError, get_route_from_text
from src.ingestion.gpx_parser import load_gpx_track, simplify_track, validate_gpx_track
from src.optimizer.cheapest import filter_all_stations_on_route, filter_cheapest_stations
from src.optimizer.export import enrich_stations_with_osrm
from src.spatial.engine import build_route_buffer, spatial_join_within_buffer


def execute_spatial_pipeline(
    engine,
    origen_txt: str,
    destino_txt: str,
    _input_mode: str,
    gpx_file,
    combustible_elegido: str,
    fuel_column: str,
    radio_km: float,
    top_n: int,
    solo_24h: bool,
    buscar_tramos: bool,
    segment_km: float,
    buffer_m: float,
    espana_vaciada: bool,
    calcular_desvio: bool,
    _using_demo: bool,
):
    """
    Ejecuta el pipeline de análisis espacial y procesamiento de rutas.
    Devuelve un diccionario con los resultados para ser persistido en st.session_state.
    Termina internamente con st.stop() si encuentra errores bloqueantes.
    """
    if buffer_m > 20000:
        st.error("🚨 La zona de búsqueda es demasiado amplia. Por favor, reduce el radio de desvío a un máximo de 20 km.")
        st.stop()

    if _input_mode == "texto":
        if len(origen_txt.strip()) < 3 or len(destino_txt.strip()) < 3:
            st.error("📍 Los nombres de origen y destino deben tener al menos 3 caracteres.")
            st.stop()
        if origen_txt.strip().lower() == destino_txt.strip().lower():
            st.error("📍 El origen y el destino no pueden ser iguales.")
            st.stop()

    if _input_mode == "texto_vacio":
        st.error("📍 Escribe el origen y el destino, o sube un archivo GPX.")
        st.stop()
        
    if _input_mode in ("gpx_vacio",) and not st.session_state.get("demo_mode"):
        st.error("📂 Sube tu archivo GPX o escribe origen y destino en la pestaña de texto.")
        st.stop()

    tmp_path = None
    _gpx_bytes = None
    track = None
    _hay_ruta_texto = _input_mode == "texto" and bool(origen_txt.strip()) and bool(destino_txt.strip())

    if _input_mode == "texto" and _hay_ruta_texto:
        with st.status("🗺️ Calculando la ruta por carretera…", expanded=True) as _status_txt:
            st.write(f" Geocodificando **{origen_txt}** y **{destino_txt}**…")
            try:
                track = get_route_from_text(origen_txt.strip(), destino_txt.strip())
                _status_txt.update(label="✅ Ruta calculada", state="complete", expanded=True)
            except RouteTextError as exc:
                _status_txt.update(label="❌ No se pudo calcular la ruta", state="error", expanded=True)
                st.error(f"🚧 **No hemos podido trazar la ruta entre estas ciudades.**\\n\\n{exc}")
                st.stop()
            except Exception as exc:
                _status_txt.update(label="❌ Error inesperado", state="error", expanded=True)
                st.error(f"⚠️ Error inesperado al trazar la ruta: {exc}")
                st.stop()
    else:
        if _using_demo:
            # Resolving relative to main package directory assuming runner.py is in src/pipeline
            demo_gpx_path = Path(__file__).parent.parent.parent / "sierra_gredos.gpx"
            if not demo_gpx_path.exists():
                st.error("⚠️ No se encontró el archivo de demo.")
                st.stop()
            tmp_path = demo_gpx_path
            with open(demo_gpx_path, "rb") as f:
                _gpx_bytes = f.read()
        else:
            _is_file = (gpx_file is not None and
                       not isinstance(gpx_file, (bool, str, int, float)) and
                       hasattr(gpx_file, "read"))
            if _is_file:
                _gpx_bytes = gpx_file.read()
            else:
                _gpx_bytes = b""
                st.error("❌ No se pudo localizar o leer el archivo GPX. Intenta volver a subirlo.")
                st.stop()
                
            if len(_gpx_bytes) > 5 * 1024 * 1024:
                st.error("❌ El archivo GPX excede el límite de 5MB. Por seguridad, ha sido bloqueado.")
                st.stop()

            try:
                content = _gpx_bytes[:1024].decode('utf-8', errors='ignore')
                if "<gpx" not in content.lower():
                    raise ValueError("Not a GPX file")
            except Exception:
                st.error("❌ El archivo subido no parece ser un GPX válido o está corrupto.")
                st.stop()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".gpx") as tmp:
                tmp.write(_gpx_bytes)
                tmp_path = Path(tmp.name)

    # ---------------- Motor Espacial ----------------
    with st.status("⛽ Analizando tu ruta…", expanded=True) as status:
        try:
            status.update(label="⛽ Arrancando Motor Espacial…", state="running")
            
            if track is None:
                status.update(label="📍 Leyendo y validando GPX…", state="running")
                track = load_gpx_track(tmp_path)
                validate_gpx_track(track)

            status.update(label="📐 Procesando geometría…", state="running")
            track_simp = simplify_track(track, tolerance_deg=0.0005)

            _ESPANA_VACIADA_BUFFER_M = 500

            status.update(label="🔍 Buscando gasolineras en tu corredor…", state="running")
            gdf_buffer = build_route_buffer(track_simp, buffer_meters=buffer_m)
            gdf_within = spatial_join_within_buffer(engine.gdf, gdf_buffer)

            if solo_24h:
                gdf_within = gdf_within[gdf_within["Horario"].str.contains("24H|24 H", case=False, na=False)]

            if gdf_within.empty and not espana_vaciada:
                status.update(label="⚠️ Sin resultados", state="error", expanded=True)
                st.warning(f"No encontramos gasolineras con precio de **{combustible_elegido}** en ese radio.")
                st.stop()

            gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simp], crs=CRS_WGS84).to_crs(CRS_UTM30N)
            track_utm = gdf_track_utm.geometry.iloc[0]

            if not gdf_within.empty and fuel_column in gdf_within.columns and not gdf_within[fuel_column].isna().all():
                status.update(label="🏆 Ordenando por precio…", state="running")
                gdf_top = filter_cheapest_stations(
                    gdf_within,
                    fuel_column=fuel_column,
                    top_n=top_n,
                    track_utm=track_utm,
                    segment_km=segment_km if buscar_tramos else 0.0,
                )
            else:
                gdf_top = gdf_within.iloc[0:0].copy()

            if espana_vaciada:
                status.update(label="🏜️ Modo España Vaciada…", state="running")
                gdf_buffer_narrow = build_route_buffer(track_simp, buffer_meters=_ESPANA_VACIADA_BUFFER_M)
                gdf_narrow = spatial_join_within_buffer(engine.gdf, gdf_buffer_narrow)
                if solo_24h:
                    gdf_narrow = gdf_narrow[gdf_narrow["Horario"].str.contains("24H|24 H", case=False, na=False)]
                if not gdf_narrow.empty:
                    gdf_narrow_all = filter_all_stations_on_route(
                        gdf_narrow, fuel_column=fuel_column, track_utm=track_utm
                    )
                    gdf_top = gpd.GeoDataFrame(
                        pd.concat([gdf_top, gdf_narrow_all], ignore_index=True),
                        crs=gdf_top.crs if not gdf_top.empty else gdf_narrow_all.crs,
                    ).drop_duplicates(subset=["geometry"])
                    if "km_ruta" in gdf_top.columns:
                        gdf_top = gdf_top.sort_values("km_ruta").reset_index(drop=True)

            if gdf_top.empty:
                status.update(label="⚠️ Sin resultados", state="error", expanded=True)
                st.warning("No hay gasolineras en la zona de búsqueda.")
                st.stop()

            if calcular_desvio:
                st.write("🛣️ Calculando tiempos de desvío reales…")
                gdf_top["osrm_distance_km"] = float("nan")
                gdf_top["osrm_duration_min"] = float("nan")
                try:
                    osrm_progress = st.progress(0.0, text="Calculando desvíos…")
                    total_osrm = len(gdf_top)
                    completed = 0
                    for idx, result in enrich_stations_with_osrm(gdf_top, track_original=track):
                        completed += 1
                        osrm_progress.progress(completed / total_osrm, text=f"Recabando distancias reales: {completed}/{total_osrm}")
                        if result:
                            gdf_top.at[idx, "osrm_distance_km"] = round(result["distance_km"], 2)
                            gdf_top.at[idx, "osrm_duration_min"] = round(result["duration_min"], 1)
                    osrm_progress.empty()
                except Exception:
                    pass
            else:
                gdf_top["osrm_distance_km"] = float("nan")
                gdf_top["osrm_duration_min"] = float("nan")

            status.update(label="✅ Tu ruta ha sido analizada", state="complete", expanded=True)

            _precio_max_zona = (
                float(gdf_within[fuel_column].max())
                if not gdf_within.empty and fuel_column in gdf_within.columns
                else 0.0
            )

            gdf_survival = gdf_within.copy()
            if fuel_column in gdf_survival.columns:
                gdf_survival[fuel_column] = pd.to_numeric(gdf_survival[fuel_column], errors="coerce")
                gdf_survival = gdf_survival[gdf_survival[fuel_column].notna() & (gdf_survival[fuel_column] > 0)].copy()
            else:
                gdf_survival = gdf_survival.iloc[0:0].copy()

            return {
                "gdf_top":          gdf_top,
                "gdf_within":       gdf_survival,
                "gdf_within_count": len(gdf_within),
                "precio_zona_max":  _precio_max_zona,
                "track":            track,
                "track_utm":        track_utm,
                "using_demo":       _using_demo,
                "using_gpx":        _input_mode in ("gpx", "demo"),
                "gpx_bytes":        _gpx_bytes,
                "espana_vaciada":   espana_vaciada,
            }

        except RouteTextError as exc:
            status.update(label="❌ Ruta imposible", state="error", expanded=True)
            st.error(f"🚧 **Ruta imposible:** {exc}")
            st.stop()
        except Exception as exc:
            status.update(label="❌ Error inesperado", state="error", expanded=True)
            st.error(f"Se produjo un error inesperado.\\n\\n*Detalle técnico: {exc}*")
            st.stop()
        finally:
            if tmp_path is not None and not _using_demo and _input_mode == "gpx":
                tmp_path.unlink(missing_ok=True)
