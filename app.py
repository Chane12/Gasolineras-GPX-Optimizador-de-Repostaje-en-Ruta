"""
app.py
======
Interfaz web (Streamlit) para el Optimizador de Gasolineras en Ruta.

Cómo ejecutar:
    streamlit run app.py
"""

import tempfile
import urllib.parse
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import streamlit as st
import streamlit_javascript as st_js
from streamlit_folium import st_folium

import ui_components

from gasolineras_ruta import (
    CRS_UTM30N,
    CRS_WGS84,
    RouteTextError,
    build_route_buffer,
    build_stations_geodataframe,
    enrich_gpx_with_stops,
    enrich_stations_with_osrm,
    fetch_gasolineras,
    filter_cheapest_stations,
    generate_google_maps_url,
    generate_map,
    get_route_from_text,
    load_gpx_track,
    prepare_export_gdf,
    simplify_track,
    spatial_join_within_buffer,
    validate_gpx_track,
    calculate_autonomy_radar,
    _GMAPS_MAX_WAYPOINTS,
)

# ---------------------------------------------------------------------------
# Caché de datos — evitar recalcular en cada interacción
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False, max_entries=1)
def cached_fetch_gasolineras() -> object:
    """Descarga todas las gasolineras con caché de 30 minutos."""
    return fetch_gasolineras()


@st.cache_resource(ttl=1800, show_spinner=False, max_entries=1)
def cached_build_stations_gdf(_df) -> object:
    """
    Construye el GeoDataFrame con índice R-Tree (una vez cada 30 min).
    Usamos cache_resource (no cache_data) porque los objetos Shapely y el
    índice espacial GEOS no deben ser clonados por pickle — evita fugas
    de memoria en servidores con 1 GB de RAM como Streamlit Cloud.
    """
    return build_stations_geodataframe(_df)


# ---------------------------------------------------------------------------
# Configuración de la página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Gasolineras en Ruta",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS (Movido a ui_components y componentes nativos)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Prevent map from trapping scroll on touch devices */
    @media (max-width: 768px) {
        iframe { touch-action: pan-y !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Cabecera principal
# ---------------------------------------------------------------------------
if "mis_paradas" not in st.session_state:
    st.session_state["mis_paradas"] = []

st.title("⛽ Gasolineras en Ruta Dashboard")
st.markdown("Encuentra las estaciones de servicio más económicas a lo largo de tu viaje.")

# ---------------------------------------------------------------------------
# Tipos de combustible
# ---------------------------------------------------------------------------
COMBUSTIBLES = {
    "Gasolina 95":                    "Precio Gasolina 95 E5",
    "Gasolina 95 Premium":            "Precio Gasolina 95 E5 Premium",
    "Gasolina 98":                    "Precio Gasolina 98 E5",
    "Diésel (Gasoil A)":             "Precio Gasoleo A",
    "Diésel Premium":                 "Precio Gasoleo Premium",
    "GLP / Autogas":                  "Precio Gases licuados del petroleo",
    "Gas Natural Comprimido (GNC)":   "Precio Gas Natural Comprimido",
    "Gas Natural Licuado (GNL)":      "Precio Gas Natural Licuado",
    "Gasoil B (agrícola/industrial)": "Precio Gasoleo B",
    "Gasolina 95 E10":                "Precio Gasolina 95 E10",
    "Gasolina 98 E10":                "Precio Gasolina 98 E10",
    "Hidrógeno":                      "Precio Hidrogeno",
}

# ---------------------------------------------------------------------------
# Leer parámetros de URL (F2: Compartir por URL)
# ---------------------------------------------------------------------------
qp = st.query_params
_fuel_default = qp.get("fuel", "Gasolina 95")
_fuel_default = _fuel_default if _fuel_default in COMBUSTIBLES else "Gasolina 95"
_buffer_default = int(qp.get("buffer", 5))
_buffer_default = max(1, min(15, _buffer_default))
_top_default = int(qp.get("top", 10))
_top_default = max(1, min(20, _top_default))
_autonomia_default = int(qp.get("autonomia", 0))
_solo24h_default = qp.get("solo24h", "False").lower() == "true"

# ---------------------------------------------------------------------------
# BARRA LATERAL / MAIN VIEWS — Controles de Configuración
# ---------------------------------------------------------------------------

def render_controls():
    _search_done = "pipeline_results" in st.session_state
    
    with st.expander("⚙️ Modificar Búsqueda" if _search_done else "🛠️ Configuración (Paso 1 y 2)", expanded=not _search_done):
        # -----------------------------------------------
        # PASO 1: DEFINICIÓN DE RUTA
        # -----------------------------------------------
        st.markdown('#### Paso 1: Definición de Ruta', unsafe_allow_html=True)
        tab_texto, tab_gpx = st.tabs(["📍 Origen / Destino", "📁 Subir GPX"])

        with tab_texto:
            origen_txt  = st.text_input(
                "Origen",
                placeholder="Ej: Madrid",
                key="origen_txt",
            )
            destino_txt = st.text_input(
                "Destino",
                placeholder="Ej: Barcelona",
                key="destino_txt",
            )
            if origen_txt or destino_txt:
                _input_mode = "texto"
                gpx_file = None
            else:
                _input_mode = "texto_vacio"
                gpx_file = None

        with tab_gpx:
            gpx_file_upload = st.file_uploader(
                "Elige un archivo .gpx:", type=["gpx"], label_visibility="collapsed", key="gpx_uploader"
            )
            if gpx_file_upload is not None:
                _input_mode = "gpx"
                gpx_file = gpx_file_upload
            elif st.session_state.get("demo_mode") and _input_mode not in ("gpx",):
                _input_mode = "demo"
                gpx_file = None
            elif _input_mode not in ("texto", "texto_vacio"):
                _input_mode = "gpx_vacio"
                gpx_file = None

            if gpx_file is None and st.session_state.get("demo_mode"):
                st.success("✅ Cargada ruta de demo (Madrid - Valencia ~356 km)")
                


        st.divider()

        # -----------------------------------------------
        # PASO 2: PARÁMETROS DEL VEHÍCULO Y COMBUSTIBLE
        # -----------------------------------------------
        st.markdown('#### Paso 2: Parámetros del Vehículo', unsafe_allow_html=True)
        
        combustible_elegido = st.selectbox(
            "Tipo de Combustible:", options=list(COMBUSTIBLES.keys()),
            index=list(COMBUSTIBLES.keys()).index(_fuel_default),
            key="comb_selectbox"
        )
        fuel_column = COMBUSTIBLES[combustible_elegido]

        usar_vehiculo = st.checkbox(
            "Activar Radar de Autonomía",
            value=st.session_state.get("usar_vehiculo", False),
            help="Mostrar zonas de peligro en el mapa donde corres el riesgo de quedarte sin combustible.",
            key="limite_autonomia_chk"
        )
        
        if usar_vehiculo:
            # Perfiles de Autonomía (Mobile-First UI via selectbox or radio)
            perfil = st.radio("Perfil de Vehículo", ["Moto (🔥 250km)", "Coche Standard (🚗 600km)", "Coche Gran Autonomía (🔋 900km)", "Manual"], horizontal=False, index=3, key="perfil_vh")
            
            if "Moto" in perfil:
                auto_val = 250
            elif "Standard" in perfil:
                auto_val = 600
            elif "Gran" in perfil:
                auto_val = 900
            else:
                auto_val = _autonomia_default if _autonomia_default > 0 else 500
                
            if perfil != "Manual":
                st.session_state["autonomia_input"] = auto_val
                
            autonomia_km = st.number_input(
                "Autonomía del Vehículo (km)",
                min_value=10, max_value=2000,
                value=auto_val,
                step=10,
                help="¿Cuántos kilómetros puede hacer tu vehículo con el depósito completamente lleno?",
                disabled=(perfil != "Manual"),
                key="autonomia_input"
            )
        else:
            autonomia_km = 0

        st.divider()

        # -----------------------------------------------
        # PASO 3: FILTROS AVANZADOS
        # -----------------------------------------------
        with st.expander("🛠️ Filtros Avanzados", expanded=False):
            radio_km = st.slider(
                "Distancia máxima de desvío (km)",
                min_value=1, max_value=15, value=_buffer_default, step=1,
                help="Distancia lateral máxima al track para incluir gasolineras.",
                key="radio_slider"
            )
            top_n = st.slider("Gasolineras a mostrar max.", min_value=1, max_value=20, value=_top_default, step=1, key="top_slider")
            
            st.markdown("---")
            solo_24h = st.checkbox(
                "Solo estaciones abiertas 24H", 
                value=_solo24h_default, 
                key="solo_24h_chk"
            )
            buscar_tramos = st.checkbox(
                "Añadir obligatoriamente 1 por sub-tramo",
                value=True,
                help="Añade la gasolinera más barata por tramo. Ideal para asegurar autonomía en rutas largas.",
                key="buscar_tramos_chk"
            )
            if buscar_tramos:
                segment_km = st.slider("Intervalo de seguridad (km)", min_value=10, max_value=300, value=50, step=10, key="segment_slider")
            else:
                segment_km = 0.0

        buffer_m = radio_km * 1000

        # Botón búsqueda prominente
        st.markdown("<br>", unsafe_allow_html=True)
        run_btn = st.button("🔍 Iniciar Búsqueda", type="primary", use_container_width=True)

        st.markdown("---")

        # Botón para compartir configuración por URL
        if st.button("🔗 Compartir enlace", use_container_width=True):
            st.query_params.update({
                "fuel":       combustible_elegido,
                "buffer":     str(radio_km),
                "top":        str(top_n),
                "solo24h":    str(solo_24h),
                "autonomia":  str(autonomia_km),
            })
            st.toast("✅ URL actualizada. ¡Copia la barra de direcciones para compartirla! 📌", icon="🔗")

        st.caption("Datos en tiempo real del MITECO · Ministerio de Transición Ecológica.")

    return {
        "origen_txt": origen_txt,
        "destino_txt": destino_txt,
        "_input_mode": _input_mode,
        "gpx_file": gpx_file,
        "combustible_elegido": combustible_elegido,
        "fuel_column": fuel_column,
        "autonomia_km": autonomia_km,
        "usar_vehiculo": usar_vehiculo,
        "radio_km": radio_km,
        "top_n": top_n,
        "solo_24h": solo_24h,
        "buscar_tramos": buscar_tramos,
        "segment_km": segment_km,
        "buffer_m": buffer_m,
        "run_btn": run_btn
    }

def render_desktop_view():
    with st.sidebar:
        st.markdown("## 🧭 Planificador de Ruta")
        return render_controls()

def render_mobile_view():
    st.markdown("## 🧭 Planificador de Ruta")
    # En móvil eliminamos el "Mostrar Controles de Búsqueda" previo extra, el render_controls ya tiene un expander colapsable
    return render_controls()

# Detección responsiva de ancho
viewport_width = st_js.st_javascript("window.innerWidth", key="viewport_width")
is_mobile = False
if viewport_width and viewport_width > 0 and viewport_width < 768:
    is_mobile = True

if is_mobile:
    ctrl = render_mobile_view()
else:
    ctrl = render_desktop_view()

# Extracción de variables para el pipeline
origen_txt = ctrl["origen_txt"]
destino_txt = ctrl["destino_txt"]
_input_mode = ctrl["_input_mode"]
gpx_file = ctrl["gpx_file"]
combustible_elegido = ctrl["combustible_elegido"]
fuel_column = ctrl["fuel_column"]
autonomia_km = ctrl["autonomia_km"]
usar_vehiculo = ctrl["usar_vehiculo"]
radio_km = ctrl["radio_km"]
top_n = ctrl["top_n"]
solo_24h = ctrl["solo_24h"]
buscar_tramos = ctrl["buscar_tramos"]
segment_km = ctrl["segment_km"]
buffer_m = ctrl["buffer_m"]
run_btn = ctrl["run_btn"]

# ---------------------------------------------------------------------------
# Pipeline de cálculo
# ---------------------------------------------------------------------------
_is_demo_first_run = st.session_state.get("demo_mode") and "pipeline_results" not in st.session_state
_hay_ruta_texto = _input_mode == "texto" and bool(origen_txt.strip()) and bool(destino_txt.strip())
_pipeline_active = run_btn or _is_demo_first_run

if run_btn:
    st.session_state.pop("pipeline_results", None)

_using_demo = (_pipeline_active and _input_mode in ("demo", "gpx_vacio") and st.session_state.get("demo_mode"))

if _pipeline_active:
    # ---------------- EARLY VALIDATORS ----------------
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

    # Validar que haya una fuente de ruta válida
    if _input_mode == "texto_vacio":
        st.error("📍 Escribe el origen y el destino, o sube un archivo GPX.")
        st.stop()
    if _input_mode in ("gpx_vacio",) and not st.session_state.get("demo_mode"):
        st.error("📂 Sube tu archivo GPX o escribe origen y destino en la pestaña de texto.")
        st.stop()

    tmp_path = None    # solo se usa en modo GPX
    _gpx_bytes = None  # para inyectar paradas luego

    if _input_mode == "texto" and _hay_ruta_texto:
        # ---- MODO TEXTO: obtener track vía Nominatim + OSRM ----
        with st.status("🗺️ Trazando tu ruta…", expanded=True) as _status_txt:
            st.write(f" Geocodificando **{origen_txt}** y **{destino_txt}**…")
            try:
                track = get_route_from_text(origen_txt.strip(), destino_txt.strip())
                _status_txt.update(label="✅ Ruta trazada", state="complete", expanded=False)
            except RouteTextError as exc:
                _status_txt.update(label="❌ Error al trazar la ruta", state="error", expanded=True)
                st.error(f"🚧 **No hemos podido trazar la ruta entre estas ciudades.**\n\n{exc}")
                st.stop()
            except Exception as exc:
                _status_txt.update(label="❌ Error inesperado", state="error", expanded=True)
                st.error(f"⚠️ Error inesperado al trazar la ruta: {exc}")
                st.stop()
    else:
        if _using_demo:
            demo_gpx_path = Path(__file__).parent / "demo_route.gpx"
            if not demo_gpx_path.exists():
                st.error("⚠️ No se encontró el archivo de demo.")
                st.stop()
            tmp_path = demo_gpx_path
            with open(demo_gpx_path, "rb") as f:
                _gpx_bytes = f.read()
        else:
            _gpx_bytes = gpx_file.read()
            if len(_gpx_bytes) > 5 * 1024 * 1024:
                st.error("❌ El archivo GPX excede el límite de 5MB. Por seguridad contra degradación de memoria, ha sido bloqueado.")
                st.stop()
                
            try:
                # Verificación temprana de integridad GPX
                content = _gpx_bytes.decode('utf-8', errors='ignore')
                if "<gpx" not in content.lower():
                    raise ValueError("Not a GPX file")
            except Exception:
                st.error("❌ El archivo subido no parece ser un archivo GPX válido o está corrupto. Intenta volver a exportarlo.")
                st.stop()
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=".gpx") as tmp:
                tmp.write(_gpx_bytes)
                tmp_path = Path(tmp.name)
        track = None   # se asigna en el bloque try más abajo

    with st.status("⛽ Iniciando pipeline de procesamiento...", expanded=True) as status:
        try:
            status.update(label="⏬ Descargando precios en tiempo real del MITECO…", state="running")
            # Proteger contra Memory Leaks aislando el DataFrame de posibles mutaciones posteriores
            # (NOTA: Se tratan los datos cacheados como solo-lectura; los filtros subsecuentes crean copias seguras superficiales)
            df_gas = cached_fetch_gasolineras()

            # --- Carga del track (solo GPX; en modo texto ya está listo) ---
            if track is None:
                status.update(label="🗺️ Leyendo y validando tu ruta GPX…", state="running")
                track = load_gpx_track(tmp_path)
                validate_gpx_track(track)

            status.update(label="✂️ Simplificando y procesando la geometría de la ruta…", state="running")
            track_simp = simplify_track(track, tolerance_deg=0.0005)

            status.update(label="📡 Cruzando con estaciones de servicio cercanas a tu ruta…", state="running")
            gdf_buffer = build_route_buffer(track_simp, buffer_meters=buffer_m)
            # T1: El GeoDataFrame con R-Tree se construye solo una vez (caché), lo leemos en modo solo-lectura
            gdf_utm = cached_build_stations_gdf(df_gas)
            gdf_within = spatial_join_within_buffer(gdf_utm, gdf_buffer)

            if solo_24h:
                # Filtrar asumiendo que el MITECO pone "24H" o "24 H" en el string horario
                # (Genera copia superficial transparente)
                gdf_within = gdf_within[gdf_within["Horario"].str.contains("24H|24 H", case=False, na=False)]

            if fuel_column not in gdf_within.columns or gdf_within.empty or gdf_within[fuel_column].isna().all():
                status.update(label="⚠️ Sin resultados para ese filtro", state="error", expanded=True)
                st.warning(
                    f"No encontramos gasolineras con precio de **{combustible_elegido}** "
                    f"en un radio de {radio_km} km (abiertas 24H: {solo_24h}). "
                    "Prueba a ampliar la distancia o relajar los filtros avanzados."
                )
                st.stop()

            status.update(label="💰 Calculando el ranking de las más baratas…", state="running")
            gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simp], crs=CRS_WGS84).to_crs(CRS_UTM30N)
            track_utm = gdf_track_utm.geometry.iloc[0]

            gdf_top = filter_cheapest_stations(
                gdf_within,
                fuel_column=fuel_column,
                top_n=top_n,
                track_utm=track_utm,
                segment_km=segment_km,
            )

            if gdf_top.empty:
                status.update(label="⚠️ Sin resultados", state="error", expanded=True)
                st.warning(
                    "No hay gasolineras con ese tipo de combustible en la zona de búsqueda. "
                    "Prueba con otro combustible o amplía la distancia de búsqueda."
                )
                st.stop()

            # ---- OSRM: Filtro Fino — Distancia real por carretera ----
            st.write("�️ Calculando desvíos reales por carretera (Puede tardar un poco)…")
            gdf_top["osrm_distance_km"] = float("nan")
            gdf_top["osrm_duration_min"] = float("nan")
            
            try:
                osrm_progress = st.progress(0.0, text="Llamando a OSRM para filtros finos...")
                total_osrm = len(gdf_top)
                completed_osrm = 0
                
                for idx, result in enrich_stations_with_osrm(
                    gdf_top,
                    track_original=track,
                ):
                    completed_osrm += 1
                    osrm_progress.progress(
                        completed_osrm / total_osrm, 
                        text=f"Recabando distancias reales: {completed_osrm}/{total_osrm}"
                    )
                    
                    if result is not None:
                        gdf_top.at[idx, "osrm_distance_km"] = round(result["distance_km"], 2)
                        gdf_top.at[idx, "osrm_duration_min"] = round(result["duration_min"], 1)
                        
                osrm_progress.empty()
            except Exception:  # silencio total: si falla OSRM el mapa sigue funcionando
                pass

            status.update(label="🖼️ Generando mapa interactivo…", state="running")
            _, mapa_obj = generate_map(
                track_original=track,
                gdf_top_stations=gdf_top,
                fuel_column=fuel_column,
                autonomy_km=float(autonomia_km),  # F3: Zonas de peligro por autonomía
            )

            status.update(label="✅ ¡Ruta analizada y optimizada!", state="complete", expanded=False)

            # --- Guardar resultados en session_state para sobrevivir reruns ---
            # OMITIMOS guardar el mapa completo (Leaflet) para evitar Memory Leaks en Streamlit
            st.session_state["pipeline_results"] = {
                "gdf_top":        gdf_top,
                "gdf_within_count": len(gdf_within),
                "precio_zona_max": float(gdf_within[fuel_column].max()) if not gdf_within.empty else 0.0,
                "track":          track,
                "track_utm":      track_utm,
                "using_demo":     _using_demo,
                "using_gpx":      _input_mode in ("gpx", "demo"),
                "gpx_bytes":      _gpx_bytes,
            }

        except RouteTextError as exc:
            status.update(label="❌ Ruta imposible", state="error", expanded=True)
            st.error(f"🚧 **Ruta imposible:** {exc}")
            st.stop()
        except ValueError as exc:
            status.update(label="❌ Error de datos", state="error", expanded=True)
            st.error(f"⚠️ {exc}")
            st.stop()
        except FileNotFoundError:
            status.update(label="❌ Archivo no encontrado", state="error", expanded=True)
            st.error("No se pudo leer el archivo GPX. Asegúrate de que sea un archivo GPX válido.")
            st.stop()
        except Exception as exc:
            status.update(label="❌ Error inesperado", state="error", expanded=True)
            st.error(
                "Se produjo un error inesperado. Comprueba tu conexión a Internet "
                f"e inténtalo de nuevo.\n\n*Detalle técnico: {exc}*"
            )
            st.stop()
        finally:
            # Solo borrar el archivo temporal en modo GPX real
            if tmp_path is not None and not _using_demo and _input_mode == "gpx":
                tmp_path.unlink(missing_ok=True)

# -----------------------------------------------------------------------
# Dashboard — se renderiza si hay resultados en session_state
# (tanto tras el pipeline como en reruns por interacción con la UI)
# -----------------------------------------------------------------------
if "pipeline_results" in st.session_state:
    _r              = st.session_state["pipeline_results"]
    gdf_top         = _r["gdf_top"]
    
    # Restituimos variables derivadas ligeras en lugar del gdf_within completo
    total_zona      = _r.get("gdf_within_count", 0)
    precio_zona_max = _r.get("precio_zona_max", 0.0)
    
    track           = _r["track"]
    track_utm       = _r["track_utm"]
    _using_demo     = _r["using_demo"]
    _using_gpx      = _r.get("using_gpx", False)
    _gpx_bytes      = _r.get("gpx_bytes")

    if _using_demo:
        st.info("🧭 **Modo Demo activo** — Escapada Madrid - Valencia (~356 km). Sube tu propio GPX desde el panel lateral cuando quieras.")
    st.success("✅ Ruta analizada con éxito")

    # --- Centro del mapa (persiste entre reruns via session_state) ---
    _track_coords_default = list(track.coords)
    _default_center = [
        sum(c[1] for c in _track_coords_default) / len(_track_coords_default),
        sum(c[0] for c in _track_coords_default) / len(_track_coords_default),
    ]
    _sel = st.session_state.get("map_selected_station", {})
    map_center = _sel.get("center", _default_center)
    map_zoom   = _sel.get("zoom", 8)

    # 1. KPIs principales
    precio_top_min = float(gdf_top[fuel_column].min()) if not gdf_top.empty else 0.0
    total_mostradas = len(gdf_top)
    ahorro_vs_caro = precio_zona_max - precio_top_min

    ui_components.render_metric_cards(precio_top_min, ahorro_vs_caro, total_mostradas, total_zona, radio_km, fuel_column)

    st.divider()

    # -----------------------------------------------------------------------
    # 3. Mapa — aparece primero para impacto visual inmediato
    # -----------------------------------------------------------------------
    @st.fragment
    def render_map_view():
        header_map = "🗺️ Mapa Interactivo de la Ruta"
        if autonomia_km > 0:
            header_map += f"  ·  ⚠️ Zonas de riesgo con {autonomia_km} km de autonomía"
        st.subheader(header_map)
        
        _sel = st.session_state.get("map_selected_station", {})
        map_center = _sel.get("center", _default_center)
        map_zoom   = _sel.get("zoom", 8)

        if _sel.get("nombre"):
            st.caption(f"📍 Centrado en: **{_sel['nombre']}** — haz clic en otro marcador o fila de la tabla para cambiar.")
        elif autonomia_km > 0:
            st.caption(
                "Los segmentos **rojos discontinuos** indican tramos donde no hay gasolinera "
                f"dentro de tus {autonomia_km} km de autonomía."
            )

        map_active = st.checkbox(
            "🖱️ Activar interacción con el mapa (zoom / arrastrar)",
            value=True,
            help=(
                "En móvil, desáctivalo para poder hacer scroll en la página "
                "sin que el mapa capture el gesto."
            ),
        )
        map_height = 580 if map_active else 340

        # Regenerar mapa de forma determinista para la vista
        _, mapa_view = generate_map(
            track_original=track,
            gdf_top_stations=gdf_top,
            fuel_column=fuel_column,
            autonomy_km=float(autonomia_km)
        )

        st_folium(
            mapa_view,
            width="100%",
            height=map_height,
            center=map_center,
            zoom=map_zoom,
            returned_objects=[],
        )
        if not map_active:
            st.caption("ℹ️ Activa la interacción arriba para hacer zoom y desplazarte por el mapa.")

    render_map_view()

    st.divider()

    # -----------------------------------------------------------------------
    # 4. Tabla de resultados
    # -----------------------------------------------------------------------
    @st.fragment
    def render_ranking_and_plan_view():
        st.subheader("🏆 Ranking de Gasolineras")
        st.caption(
            "Haz clic en una fila para centrar el mapa en esa gasolinera (se actualiza en el próximo render). "
            "Haz clic en los marcadores del mapa para ver más detalles."
        )

    COLS = {
        "km_ruta":            "Km en Ruta",
        "Rótulo":             "Marca",
        fuel_column:          f"Precio {combustible_elegido} (€/L)",
        "osrm_duration_min":  "Desvío (min)",
        "Horario":            "Horario",
    }

    col_map = {}
    for campo, etiqueta in COLS.items():
        if campo in gdf_top.columns:
            col_map[campo] = etiqueta

    df_show = gdf_top[list(col_map.keys())].copy()
    df_show = df_show.rename(columns=col_map)
    
    precio_col_label = f"Precio {combustible_elegido} (€/L)"

    # Add relative savings
    if precio_zona_max > 0 and precio_col_label in df_show.columns:
        df_show["Ahorro (€/L)"] = precio_zona_max - df_show[precio_col_label]
        # Filtrar posibles ahorros negativos marginales por diferencias de FP
        df_show["Ahorro (€/L)"] = df_show["Ahorro (€/L)"].apply(lambda x: max(0.0, float(x)))

    # Construir URL de Google Maps para cada dirección (columna LinkColumn)
    if "Dirección" in df_show.columns and "Municipio" in df_show.columns:
        df_show["_maps_url"] = df_show.apply(
            lambda r: "https://maps.google.com/?q=" + urllib.parse.quote_plus(
                f"{r.get('Dirección', '')}, {r.get('Municipio', '')}"
            ),
            axis=1,
        )
    elif "Dirección" in df_show.columns:
        df_show["_maps_url"] = df_show["Dirección"].apply(
            lambda d: "https://maps.google.com/?q=" + urllib.parse.quote_plus(str(d))
        )

    # Coordenadas WGS84 de cada gasolinera (para el zoom del mapa)
    gdf_top_wgs84 = gdf_top.to_crs("EPSG:4326")
    station_coords = [
        (row.geometry.y, row.geometry.x)
        for _, row in gdf_top_wgs84.iterrows()
    ]

    @st.fragment
    def render_ranking_table():
        # --- column_config ---
        _precio_min = float(df_show[precio_col_label].min()) if precio_col_label in df_show.columns else 0.0
        _precio_max = float(df_show[precio_col_label].max()) if precio_col_label in df_show.columns else 2.0

        col_config = {
            precio_col_label: st.column_config.ProgressColumn(
                precio_col_label,
                help="Precio en €/L. Barra proporcional: menos llena = más barato.",
                format="%.3f €",
                min_value=_precio_min * 0.98,
                max_value=_precio_max * 1.02,
            ),
            "Ahorro (€/L)": st.column_config.NumberColumn(
                "Ahorro (€/L)",
                help="Ahorro estimado por litro comparado con la media/máxima de la zona.",
                format="%.3f €",
            ),
            "Km en Ruta": st.column_config.NumberColumn(
                "Km en Ruta",
                help="Distancia desde el inicio de la ruta hasta la gasolinera.",
                format="%.1f km",
            ),
            "Desvío (min)": st.column_config.NumberColumn(
                "Desvío (min)",
                help="Tiempo estimado de desvío ida+vuelta.",
                format="%.0f min",
            ),
            "Marca": st.column_config.TextColumn(
                "Marca",
                help="Nombre comercial de la gasolinera.",
            ),
            # La dirección se muestra como enlace a Google Maps
            "_maps_url": st.column_config.LinkColumn(
                "Ruta Google",
                help="Abre Google Maps para navegar hasta esta estación.",
                display_text="Ver en Maps ↗"
            ),
            # Ocultar la columna de texto plano (ya está en el enlace)
            "Dirección": None,
            "Municipio": None,
        }
        # Eliminar del config las columnas que no existen en df_show
        # (None en column_config oculta la columna sin eliminarla del df)
        col_config_dict = {k: v for k, v in col_config.items() if k in df_show.columns or v is None}

        table_event = st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config=col_config_dict,
        )

        # Determinar el centro del mapa según la selección y persistir en session_state
        selected_rows = table_event.selection.get("rows", [])
        if selected_rows:
            sel_idx = selected_rows[0]
            # Evitar bucle infinito de reruns comprobando si ya lo hemos procesado
            if st.session_state.get("last_selected_idx") != sel_idx:
                sel_nombre = df_show.iloc[sel_idx].get("Marca", "la gasolinera")
                st.session_state["map_selected_station"] = {
                    "center": list(station_coords[sel_idx]),
                    "zoom":   15,
                    "nombre": sel_nombre,
                }
                st.session_state["last_selected_idx"] = sel_idx
                st.toast(f"📍 Recentrando mapa en **{sel_nombre}**…")
                # Al estar en un fragment, este rerun solo recarga la app completa si es necesario
                # Para que el mapa lo vea, en este caso sí necesitamos que rerun se propague al mapa.
                st.rerun()

            st.write("")
            sel_row = df_show.iloc[sel_idx]
            sel_nombre_cart = sel_row.get("Marca", "Estación de servicio")
            
            ya_en_plan = any(p.get("Marca") == sel_nombre_cart for p in st.session_state["mis_paradas"])
            
            if ya_en_plan:
                st.info(f"✅ **{sel_nombre_cart}** ya está en tu Plan de Viaje.")
            else:
                if st.button(f"➕ Añadir **{sel_nombre_cart}** a Mi Plan de Viaje", type="primary"):
                    coords_y, coords_x = station_coords[sel_idx]
                    parada_dict = sel_row.to_dict()
                    parada_dict["_geom_y"] = coords_y
                    parada_dict["_geom_x"] = coords_x
                    st.session_state["mis_paradas"].append(parada_dict)
                    st.toast(f"✅ Parada añadida: {sel_nombre_cart}")
                    # Ya no forzamos rerun global aquí. La reactividad del fragment 'render_trip_plan' 
                    # lo pillaría si tuviera scope global, pero como está abajo, es mejor disparar rerun
                    st.rerun()
        else:
            # Cuando el usuario deselecciona (haciendo click fuera)
            if "last_selected_idx" in st.session_state:
                del st.session_state["last_selected_idx"]
                if "map_selected_station" in st.session_state:
                    del st.session_state["map_selected_station"]
                st.rerun()

    render_ranking_table()
    st.divider()

    # -----------------------------------------------------------------------
    # 5. Mi Plan de Viaje (Carrito)
    # -----------------------------------------------------------------------
    st.subheader("🛒 Mi Plan de Viaje")
    st.caption("Añade gasolineras de la tabla superior para diseñar tu propia estrategia de repostaje.")
    
    @st.fragment
    def render_trip_plan():
        if not st.session_state["mis_paradas"]:
            st.info("Aún no has añadido ninguna parada. Selecciona una fila en la tabla superior y haz clic en 'Añadir a Mi Plan de Viaje'.")
        else:
            df_plan = pd.DataFrame(st.session_state["mis_paradas"])
            df_plan = df_plan.sort_values("Km en Ruta").reset_index(drop=True)
            
            # Calcular km desde la parada anterior
            km_prev = 0.0
            tramos = []
            for km in df_plan["Km en Ruta"]:
                tramos.append(km - km_prev)
                km_prev = km
            df_plan["Tramo (km)"] = tramos

            col_config_plan = {
                "Tramo (km)": st.column_config.NumberColumn(format="%.1f km"),
                "Km en Ruta": st.column_config.NumberColumn(format="%.1f km"),
                precio_col_label: st.column_config.NumberColumn(format="%.3f €/L"),
            }
            
            st.dataframe(
                df_plan[["Tramo (km)", "Km en Ruta", "Marca", precio_col_label]],
                use_container_width=True,
                hide_index=True,
                column_config=col_config_plan
            )
            
            c1, c2 = st.columns([1, 1])
            with c1:
                # Si borramos el plan, forzamos un rerun del scope de la base principal o del fragmento
                if st.button("🗑️ Vaciar Mi Plan"):
                    st.session_state["mis_paradas"] = []
                    st.rerun()
                    
            st.write("")
            st.markdown("**📤 Exportar Ruta**")
            
            # Reconstruir un GDF temporal para la exportación usando EPSG:4326 a través de un módulo puro
            gdf_export = prepare_export_gdf(
                st.session_state["mis_paradas"],
                fuel_column=fuel_column,
                precio_col_label=precio_col_label
            )
                
                
            if not _using_gpx:
                gmaps_url, omitidas = generate_google_maps_url(track_utm, gdf_export)
                st.link_button(
                    "📱 Abrir Ruta en Google Maps con mis paradas",
                    url=gmaps_url,
                    type="primary",
                    help="Abre la ruta con todas las paradas en Google Maps web o en tu app móvil."
                )
                if omitidas > 0:
                    st.warning(
                        f"⚠️ **Atención:** Tu ruta tiene demasiadas paradas. Google Maps solo admite un máximo "
                        f"de {_GMAPS_MAX_WAYPOINTS} repostajes por enlace. Se han omitido los {omitidas} últimos."
                    )
            else:
                if _gpx_bytes:
                    gpx_xml_con_paradas = enrich_gpx_with_stops(
                        _gpx_bytes,
                        gdf_export,
                        fuel_column=fuel_column
                    )
                    st.download_button(
                        label="💾 Descargar GPX Original + Mis Paradas",
                        data=gpx_xml_con_paradas,
                        file_name="ruta_optimizada.gpx",
                        mime="application/gpx+xml"
                    )

    render_trip_plan()
    st.divider()
    # 6. 🏍️ Radar de Autonomía Crítica
    st.subheader("🏍️ Radar de Autonomía Crítica")
    st.caption(
        "Análisis de los tramos entre gasolineras comparado con tu autonomía. "
        "Los tramos **rojos** en el mapa marcan zonas donde podrías quedarte sin combustible."
    )

    tramos, route_total_km = calculate_autonomy_radar(track, gdf_top, autonomia_km)

    # --- Autonomy Radar UI Components ---
    ui_components.render_autonomy_radar_ui(tramos, route_total_km, autonomia_km)

    st.markdown("---")

else:
    # -----------------------------------------------------------------------
    # PANTALLA INICIAL — Estado vacío con CTA activo (Zero-Friction Onboarding)
    # -----------------------------------------------------------------------
    ui_components.render_welcome_screen()

    # ----- Demo CTA -------------------------------------------------------
    # Psicología: reducir la barrera de entrada («¿Y si no tengo un GPX ahora?»)
    # con un botón de prueba inmediata que carga una ruta real de 55 km.
    st.markdown("<br>", unsafe_allow_html=True)
    _demo_col, _ = st.columns([2, 3])
    with _demo_col:
        if st.button(
            "🚗  Probar herramienta con ruta de Escapada (Madrid - Valencia)",
            use_container_width=True,
            help="Carga automáticamente una ruta real de ~356 km para que veas la app en funcionamiento sin necesidad de subir un GPX.",
        ):
            # Activar modo demo y relanzar la app para que el pipeline lo detecte
            st.session_state["demo_mode"] = True
            st.rerun()
