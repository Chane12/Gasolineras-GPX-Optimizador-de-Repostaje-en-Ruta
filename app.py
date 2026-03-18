"""
app.py
======
Interfaz web (Streamlit) para el Optimizador de Gasolineras en Ruta.

Cómo ejecutar:
    streamlit run app.py
"""

import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import ui_components
from src.config import CRS_UTM30N, CRS_WGS84
from src.config import GMAPS_MAX_WAYPOINTS as _GMAPS_MAX_WAYPOINTS
from src.ingestion.miteco import fetch_gasolineras
from src.optimizer.autonomy import calculate_autonomy_radar
from src.optimizer.export import (
    enrich_gpx_with_stops,
    generate_google_maps_url,
    prepare_export_gdf,
)
from src.spatial.engine import build_stations_geodataframe
from src.visualization.folium_map import generate_map
from src.pipeline.runner import execute_spatial_pipeline


@dataclass(frozen=True)
class SpatialEngine:
    gdf: gpd.GeoDataFrame

# ---------------------------------------------------------------------------
# Motor Espacial Unificado
# ---------------------------------------------------------------------------

@st.cache_resource(ttl=1800, show_spinner=False, max_entries=1)
def get_spatial_engine() -> SpatialEngine:
    """
    Descarga MITECO y construye el GeoDataFrame espacial (1 vez cada 30 min).
    Retorna un contenedor inmutable con los datos cargados en R-Tree
    para evitar OOM (Out Of Memory) y desalineación (Race Conditions).
    """
    df = fetch_gasolineras()
    gdf = build_stations_geodataframe(df)
    return SpatialEngine(gdf=gdf)


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
    /* Sticky search button on mobile */
    @media (max-width: 768px) {
        div[data-testid="stButton"].sticky-cta {
            position: sticky;
            bottom: 0;
            z-index: 999;
            padding: 0.5rem 0;
            background: transparent;
        }
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
_top_default = int(qp.get("top", 5))
_top_default = max(1, min(20, _top_default))
_autonomia_default = int(qp.get("autonomia", 0))
_solo24h_default = qp.get("solo24h", "False").lower() == "true"
_desvio_default = qp.get("desvio", "False").lower() == "true"

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
                st.success("✅ Cargada ruta de demo (Sierra de Gredos - 6 Puertos)")



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

            espana_vaciada = st.checkbox(
                "🏜️ Modo España Vaciada",
                value=False,
                key="espana_vaciada_chk",
                help=(
                    "Muestra TODAS las gasolineras que están estrictamente sobre la ruta "
                    "(corredor de 500 m a cada lado), ordenadas por kilómetro en ruta. "
                    "No filtra por precio ni por top-N. "
                    "Ideal para rutas por zonas despobladas donde no puedes permitirte ignorar ninguna estación."
                ),
            )
            calcular_desvio = st.checkbox(
                "⏱️ Calcular tiempos de desvío reales",
                value=_desvio_default,
                help=(
                    "Consulta OSRM (Open Source Routing Machine) para obtener el tiempo real que tardarás en "
                    "llegar a la gasolinera y volver a la ruta. Si se desactiva, la app funcionará más rápido "
                    "pero no mostrará el tiempo de desvío en la tabla."
                ),
                key="calcular_desvio_chk"
            )

        buffer_m = radio_km * 1000

        st.markdown("<br>", unsafe_allow_html=True)
        if is_mobile:
            # Sticky CTA on mobile: wrapped in a div with class
            st.markdown(
                """
                <style>
                .sticky-search-btn button {
                    position: sticky !important;
                    bottom: 0.5rem;
                    left: 0;
                    right: 0;
                    width: 100%;
                    z-index: 9999;
                    font-size: 1.1rem !important;
                    padding: 0.75rem !important;
                    background: linear-gradient(90deg, #FF7F00, #FF5500) !important;
                    border: none !important;
                    box-shadow: 0 -4px 16px rgba(255,127,0,0.4) !important;
                    border-radius: 12px !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            with st.container():
                st.markdown('<div class="sticky-search-btn">', unsafe_allow_html=True)
                run_btn = st.button("🔍 Iniciar Búsqueda", type="primary", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            run_btn = st.button("🔍 Iniciar Búsqueda", type="primary", use_container_width=True)

        # Acciones Extra
        rc1, rc2 = st.columns(2)
        with rc1:
            if st.button("🔗 Compartir ajustes", use_container_width=True):
                st.query_params.update({
                    "fuel":       combustible_elegido,
                    "buffer":     str(radio_km),
                    "top":        str(top_n),
                    "solo24h":    str(solo_24h),
                    "autonomia":  str(autonomia_km),
                    "desvio":     str(calcular_desvio),
                })
                st.toast("✅ URL actualizada. ¡Copia la barra de direcciones para compartirla! 📌", icon="🔗")

        with rc2:
            if st.button("🔄 Reiniciar App", use_container_width=True, type="secondary"):
                st.query_params.clear()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

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
        "run_btn": run_btn,
        "espana_vaciada": espana_vaciada,
        "calcular_desvio": calcular_desvio,
    }

def render_desktop_view():
    with st.sidebar:
        st.markdown("## 🧭 Planificador de Ruta")
        # Fix D2: show active config summary if pipeline has already run
        if "pipeline_results" in st.session_state:
            _r = st.session_state["pipeline_results"]
            ui_components.render_config_summary(
                pipeline_results=_r,
                combustible=st.session_state.get("comb_selectbox", "Gasolina 95"),
                radio_km=st.session_state.get("radio_slider", 5),
                top_n=st.session_state.get("top_slider", 10),
                origen_txt=st.session_state.get("origen_txt", ""),
                destino_txt=st.session_state.get("destino_txt", ""),
                using_gpx=_r.get("using_gpx", False),
                using_demo=_r.get("using_demo", False),
            )
        return render_controls()


def render_mobile_wizard():
    """
    Mejora 1: Wizard de 3 pasos para móvil.
    Gestiona la navegación entre pasos con session_state["wizard_step"].
    Devuelve el mismo dict que render_controls() al completar.
    """
    # Inicializar paso
    if "wizard_step" not in st.session_state:
        st.session_state["wizard_step"] = 1

    step = st.session_state["wizard_step"]
    TOTAL_STEPS = 3

    # --- Barra de progreso del wizard ---
    st.progress(step / TOTAL_STEPS, text=f"Paso {step} de {TOTAL_STEPS}")

    # Persistencia robusta entre pasos: usar claves no-widget (_w_origen, _w_destino)
    # que no se borran cuando el widget deja de renderizarse en paso 2 y 3.
    origen_txt  = st.session_state.get("_w_origen") or st.session_state.get("origen_txt", "")
    destino_txt = st.session_state.get("_w_destino") or st.session_state.get("destino_txt", "")
    gpx_file    = None  # El file_uploader guarda el objeto en session_state["gpx_uploader"]

    # Calcular _input_mode desde las claves guardadas (no desde widget que puede no existir)
    _gpx_upload = st.session_state.get("gpx_uploader")
    if _gpx_upload is not None:
        _input_mode = "gpx"
        gpx_file    = _gpx_upload
    elif st.session_state.get("demo_mode"):
        _input_mode = "demo"
    elif origen_txt or destino_txt:
        _input_mode = "texto"
    else:
        _input_mode = "texto_vacio"

    combustible_elegido = st.session_state.get("_w_combustible") or st.session_state.get("comb_selectbox", _fuel_default)
    fuel_column  = COMBUSTIBLES.get(combustible_elegido, COMBUSTIBLES["Gasolina 95"])

    usar_vehiculo = st.session_state.get("_w_usar_vehiculo") if "_w_usar_vehiculo" in st.session_state else st.session_state.get("limite_autonomia_chk", False)
    autonomia_km = st.session_state.get("_w_autonomia") if "_w_autonomia" in st.session_state else st.session_state.get("autonomia_input", 0)
    if not usar_vehiculo:
        autonomia_km = 0

    radio_km      = st.session_state.get("radio_slider", _buffer_default)
    top_n         = st.session_state.get("top_slider", _top_default)
    solo_24h      = st.session_state.get("solo_24h_chk", _solo24h_default)
    buscar_tramos = st.session_state.get("buscar_tramos_chk", True)
    segment_km    = st.session_state.get("segment_slider", 50) if buscar_tramos else 0.0
    espana_vaciada = st.session_state.get("espana_vaciada_chk", False)
    calcular_desvio = st.session_state.get("calcular_desvio_chk", _desvio_default)
    buffer_m      = radio_km * 1000
    run_btn       = False

    # ══════════════════════════════════════════
    # PASO 1: DEFINICIÓN DE RUTA
    # ══════════════════════════════════════════
    if step == 1:
        # Callbacks on_change: guardan el valor inmediatamente al perder el foco
        # En móvil, al tocar "Siguiente", el campo pierde foco primero y
        # el on_change se dispara antes de procesar el botón. Sin Enter.
        def _save_origen():
            st.session_state["_w_origen"] = st.session_state.get("origen_txt", "")
        def _save_destino():
            st.session_state["_w_destino"] = st.session_state.get("destino_txt", "")

        st.markdown("### 🗺️ Paso 1 — Tu Ruta")
        tab_texto, tab_gpx = st.tabs(["📍 Origen / Destino", "📁 Subir GPX"])
        with tab_texto:
            origen_txt = st.text_input(
                "Origen", placeholder="Ej: Madrid",
                key="origen_txt", on_change=_save_origen
            )

            destino_txt = st.text_input(
                "Destino", placeholder="Ej: Barcelona",
                key="destino_txt", on_change=_save_destino
            )
            if origen_txt or destino_txt:
                _input_mode = "texto"
                gpx_file = None
            else:
                _input_mode = "texto_vacio"
                gpx_file = None
        with tab_gpx:
            gpx_file_upload = st.file_uploader("Elige un archivo .gpx:", type=["gpx"], label_visibility="collapsed", key="gpx_uploader")
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
                st.success("✅ Cargada ruta de demo (Sierra de Gredos - 6 Puertos)")

        st.markdown("")
        if st.button("Siguiente: Vehículo ›", type="primary", use_container_width=True):
            # Guardar explícitamente (doble seguro, on_change ya debería haberlo hecho)
            st.session_state["_w_origen"]  = st.session_state.get("origen_txt", "") or origen_txt
            st.session_state["_w_destino"] = st.session_state.get("destino_txt", "") or destino_txt
            st.session_state["wizard_step"] = 2
            st.rerun()

    # ══════════════════════════════════════════
    # PASO 2: VEHÍCULO Y COMBUSTIBLE
    # ══════════════════════════════════════════
    elif step == 2:
        def _save_step2():
            st.session_state["_w_combustible"] = st.session_state.get("comb_selectbox", _fuel_default)
            st.session_state["_w_usar_vehiculo"] = st.session_state.get("limite_autonomia_chk", False)
            st.session_state["_w_autonomia"] = st.session_state.get("autonomia_input", 0)

        st.markdown("### ⛽ Paso 2 — Tu Vehículo")

        current_comb = st.session_state.get("_w_combustible", _fuel_default)
        if current_comb not in COMBUSTIBLES:
            current_comb = _fuel_default

        combustible_elegido = st.selectbox(
            "Tipo de Combustible:", options=list(COMBUSTIBLES.keys()),
            index=list(COMBUSTIBLES.keys()).index(current_comb),
            key="comb_selectbox",
            on_change=_save_step2
        )
        fuel_column = COMBUSTIBLES[combustible_elegido]

        usar_vehiculo = st.checkbox(
            "Activar Radar de Autonomía",
            value=st.session_state.get("_w_usar_vehiculo", st.session_state.get("limite_autonomia_chk", False)),
            help="Mostrar zonas de peligro en el mapa.",
            key="limite_autonomia_chk",
            on_change=_save_step2
        )
        if usar_vehiculo:
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
                "Autonomía del Vehículo (km)", min_value=10, max_value=2000,
                value=auto_val, step=10, disabled=(perfil != "Manual"), key="autonomia_input"
            )
        else:
            autonomia_km = 0

        st.markdown("")
        col_prev, col_next = st.columns(2)
        with col_prev:
            if st.button("‹ Ruta", use_container_width=True):
                st.session_state["wizard_step"] = 1
                st.rerun()
        with col_next:
            if st.button("Siguiente: Filtros ›", type="primary", use_container_width=True):
                st.session_state["wizard_step"] = 3
                st.rerun()

    # ══════════════════════════════════════════
    # PASO 3: FILTROS + BÚSQUEDA
    # ══════════════════════════════════════════
    elif step == 3:
        st.markdown("### 🛠️ Paso 3 — Filtros")
        radio_km = st.slider("Desvío máximo (km)", min_value=1, max_value=15, value=_buffer_default, step=1, key="radio_slider")
        top_n = st.slider("Gasolineras a mostrar max.", min_value=1, max_value=20, value=_top_default, step=1, key="top_slider")
        solo_24h = st.checkbox("Solo estaciones abiertas 24H", value=_solo24h_default, key="solo_24h_chk")
        if buscar_tramos:
            segment_km = st.slider("Intervalo de seguridad (km)", min_value=10, max_value=300, value=50, step=10, key="segment_slider")
        else:
            segment_km = 0.0
        espana_vaciada = st.checkbox("🏜️ Modo España Vaciada", value=False, key="espana_vaciada_chk")
        calcular_desvio = st.checkbox("⏱️ Calcular tiempos de desvío reales", value=_desvio_default, key="calcular_desvio_chk")
        buffer_m = radio_km * 1000

        st.markdown("")
        col_prev2, col_search = st.columns([1, 2])
        with col_prev2:
            if st.button("‹ Vehículo", use_container_width=True):
                st.session_state["wizard_step"] = 2
                st.rerun()
        with col_search:
            run_btn = st.button("🔍 Iniciar Búsqueda", type="primary", use_container_width=True)

        # Acciones Extra (al final del paso 3)
        st.markdown("---")
        rc1, rc2 = st.columns(2)
        with rc1:
            if st.button("🔗 Compartir ajustes", use_container_width=True):
                st.query_params.update({
                    "fuel": combustible_elegido, "buffer": str(radio_km),
                    "top": str(top_n), "solo24h": str(solo_24h), "autonomia": str(autonomia_km),
                    "desvio": str(calcular_desvio),
                })
                st.toast("✅ URL actualizada. ¡Copia la barra de direcciones! 📌", icon="🔗")
        with rc2:
            if st.button("🔄 Reiniciar App", use_container_width=True, type="secondary"):
                st.query_params.clear()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()

        st.caption("Datos en tiempo real del MITECO.")

    # Si el pipeline ya tuvo resultados y el usuario vuelve, resetear wizard al paso 1
    if run_btn and "wizard_step" in st.session_state:
        st.session_state["wizard_step"] = 1

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
        "run_btn": run_btn,
        "espana_vaciada": espana_vaciada,
        "calcular_desvio": calcular_desvio,
    }


def render_mobile_view():
    st.markdown("## 🧭 Planificador de Ruta")
    return render_mobile_wizard()


# Detección responsiva eliminada para evitar refrescos JS asíncronos
is_mobile = False

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
espana_vaciada = ctrl["espana_vaciada"]
calcular_desvio = ctrl["calcular_desvio"]

# ---------------------------------------------------------------------------
# Pipeline de cálculo
# ---------------------------------------------------------------------------
_is_demo_first_run = st.session_state.get("demo_mode") and "pipeline_results" not in st.session_state
origen_txt = str(origen_txt) if origen_txt is not None else ""
destino_txt = str(destino_txt) if destino_txt is not None else ""
_pipeline_active = run_btn or _is_demo_first_run

if run_btn:
    st.session_state.pop("pipeline_results", None)

_using_demo = (_pipeline_active and _input_mode in ("demo", "gpx_vacio") and st.session_state.get("demo_mode"))

if _pipeline_active:
    try:
        results = execute_spatial_pipeline(
            engine=get_spatial_engine(),
            origen_txt=origen_txt,
            destino_txt=destino_txt,
            _input_mode=_input_mode,
            gpx_file=gpx_file,
            combustible_elegido=combustible_elegido,
            fuel_column=fuel_column,
            radio_km=radio_km,
            top_n=top_n,
            solo_24h=solo_24h,
            buscar_tramos=buscar_tramos,
            segment_km=segment_km,
            buffer_m=buffer_m,
            espana_vaciada=espana_vaciada,
            calcular_desvio=calcular_desvio,
            _using_demo=_using_demo,
        )
        st.session_state["pipeline_results"] = results
        st.rerun()

    except Exception as exc:
        st.error(f"Fallo crítico en el pipeline espacial: {exc}")
        st.stop()

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
    espana_vaciada  = _r.get("espana_vaciada", False)

    if _using_demo:
        st.info("🧭 **Modo Demo activo** — Ruta Circular Sierra de Gredos (6 Puertos). Sube tu propio GPX desde el panel lateral cuando quieras.")
    if espana_vaciada:
        st.info(
            "🏜️ **Modo España Vaciada activo** — Mostrando **todas** las gasolineras en un corredor de 500 m a "
            "cada lado de tu ruta, ordenadas por kilómetro. No se aplica ningún filtro de precio ni límite de cantidad."
        )
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
        # Robustez tipos
        _autonomia_val = float(autonomia_km) if autonomia_km is not None else 0.0
        header_map = "🗺️ Mapa Interactivo de la Ruta"
        if _autonomia_val > 0:
            header_map += f"  ·  ⚠️ Zonas de riesgo con {_autonomia_val:.0f} km de autonomía"
        st.subheader(header_map)

        _sel = st.session_state.get("map_selected_station", {})
        map_center = _sel.get("center", _default_center)
        map_zoom   = _sel.get("zoom", 8)

        if _sel.get("nombre"):
            st.caption(f"📍 Centrado en: **{_sel['nombre']}** — haz clic en otro marcador o fila de la tabla para cambiar.")
        elif _autonomia_val > 0:
            st.caption(
                "Los segmentos **rojos discontinuos** indican tramos donde no hay gasolinera "
                f"dentro de tus {_autonomia_val:.0f} km de autonomía."
            )

        # Fix M1: toggle visible, desactivado por defecto en móvil
        if is_mobile:
            st.info(
                "👆 **El mapa está en modo lectura.** "
                "Activa el interruptor de abajo para poder hacer zoom y arrastrar.",
            )
        map_active = st.toggle(
            "🖱️ Activar interacción con el mapa (zoom / arrastrar)",
            value=not is_mobile,
            help=(
                "En móvil está desactivado por defecto para que puedas hacer scroll "
                "sin que el mapa capture el gesto. Activa el interruptor cuando quieras "
                "explorar el mapa o hacer zoom."
            ),
        )
        map_height = 700 if map_active else 380
        if not is_mobile:
            # En PC siempre mostramos el mapa alto
            map_height = 700 if map_active else 420
        else:
            map_height = 480 if map_active else 300

        # Regenerar mapa de forma determinista para la vista
        _, mapa_view = generate_map(
            track_original=track,
            gdf_top_stations=gdf_top,
            fuel_column=fuel_column,
            autonomy_km=float(autonomia_km) if autonomia_km is not None and not isinstance(autonomia_km, bool) else 0.0,
            gdf_all_stations=_r.get("gdf_within")
        )

        st_folium(
            mapa_view,
            width="100%",
            height=map_height,
            returned_objects=[],
        )
        if not map_active:
            st.caption("👆 Activa el interruptor de arriba para hacer zoom y desplazarte por el mapa.")

    render_map_view()

    st.divider()

    # -----------------------------------------------------------------------
    # 4. Tabla de resultados
    # -----------------------------------------------------------------------

    COLS = {
        "km_ruta":            "Km en Ruta",
        "Rótulo":             "Marca",
        "Municipio":          "Municipio",
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

    # Combinar Marca + Municipio en una sola columna "Marca"
    if "Marca" in df_show.columns and "Municipio" in df_show.columns:
        df_show["Marca"] = df_show.apply(
            lambda r: f"{r['Marca']}, {r['Municipio']}" if pd.notna(r['Municipio']) and str(r['Municipio']).strip() else str(r['Marca']),
            axis=1,
        )
        df_show = df_show.drop(columns=["Municipio"])

    # --- Fix: pre-formatear la columna Desvío como texto -----------------------
    # NumberColumn con format="%.0f min" no sabe renderizar NaN y muestra "None".
    # La solución correcta es convertir los valores a cadenas antes de entregar
    # el DataFrame a Streamlit: valores reales → "X min", sin dato → "—".
    _desvio_col = col_map.get("osrm_duration_min")
    if _desvio_col and _desvio_col in df_show.columns:
        _raw = pd.to_numeric(df_show[_desvio_col], errors="coerce")
        if _raw.isna().all():
            # OSRM falló completamente → ocultar la columna
            df_show = df_show.drop(columns=[_desvio_col])
            col_map.pop("osrm_duration_min", None)
        else:
            # Formatear: número → "X min", NaN → "—"
            df_show[_desvio_col] = _raw.apply(
                lambda x: f"{int(round(x))} min" if pd.notna(x) else "—"
            )


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
    # Vectorizar coordenadas con operaciones de serie (más rápido que iterrows)
    station_coords = list(zip(gdf_top_wgs84.geometry.y, gdf_top_wgs84.geometry.x))

    @st.fragment
    def render_ranking_table():
        if is_mobile:
            # Mejora 2: Vista de tarjetas táctiles en móvil
            st.subheader("🏆 Gasolineras Más Baratas")
            st.caption("Pulsa ‘Añadir’ para incluir la parada en tu plan de repostaje.")
            parada_result = ui_components.render_station_cards(
                df_show,
                precio_col_label=precio_col_label,
                station_coords=station_coords,
                mis_paradas=st.session_state["mis_paradas"],
            )
            if parada_result is not None:
                _idx, _cx, _cy, _row = parada_result
                parada_dict = _row.to_dict()
                parada_dict["_geom_x"] = _cx
                parada_dict["_geom_y"] = _cy
                st.session_state["mis_paradas"].append(parada_dict)
                st.toast(f"✅ {_row.get('Marca', 'Estación')} añadida al plan")
                st.rerun()
        else:
            st.subheader("🏆 Ranking de Gasolineras")
            st.caption(
                "Haz clic en una fila para centrar el mapa en esa gasolinera (se actualiza en el próximo render). "
                "Haz clic en los marcadores del mapa para ver más detalles."
            )
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
            "Desvío (min)": st.column_config.TextColumn(
                "Desvío (min)",
                help="Tiempo estimado de desvío ida+vuelta (vacío si el servicio de routing no estuvo disponible).",
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
        }
        # Eliminar del config las columnas que no existen en df_show
        # (None en column_config oculta la columna sin eliminarla del df)
        col_config_dict = {k: v for k, v in col_config.items() if k in df_show.columns or v is None}

        table_event = st.dataframe(
            df_show,
            width="stretch",
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
            coords_y, coords_x = station_coords[sel_idx]

            ya_en_plan = any(
                p.get("_geom_x") == coords_x and p.get("_geom_y") == coords_y
                for p in st.session_state["mis_paradas"]
            )

            if ya_en_plan:
                st.info(f"✅ Esta estación **{sel_nombre_cart}** ya está en tu Plan de Viaje.")
            else:
                if st.button(f"➕ Añadir **{sel_nombre_cart}** a Mi Plan de Viaje", type="primary"):
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
            tramos_km = []
            for km in df_plan["Km en Ruta"]:
                tramos_km.append(km - km_prev)
                km_prev = km
            df_plan["Tramo (km)"] = tramos_km

            # --- Renderizar filas manualmente con botón borrar por parada (Fix D6) ---
            st.markdown("**Tus paradas de repostaje:**")
            for i, row in df_plan.iterrows():
                marca = row.get("Marca", "Estación")
                precio_val = row.get(precio_col_label, None)
                tramo_val = row.get("Tramo (km)", 0)
                km_val = row.get("Km en Ruta", 0)
                precio_str = f"{precio_val:.3f} €/L" if precio_val is not None else "—"
                with st.container(border=True):
                    c_info, c_del = st.columns([5, 1])
                    with c_info:
                        st.markdown(f"**⛽ {marca}** &nbsp;&nbsp; `{precio_str}`")
                        st.caption(f"Km {km_val:.1f} en ruta · Tramo desde anterior: {tramo_val:.1f} km")
                    with c_del:
                        if st.button("🗑️", key=f"del_parada_{i}", help=f"Eliminar {marca} del plan"):
                            # Eliminar por índice en la lista original (ordenada igual)
                            parada_a_borrar = st.session_state["mis_paradas"]
                            geom_x = row.get("_geom_x")
                            geom_y = row.get("_geom_y")
                            st.session_state["mis_paradas"] = [
                                p for p in parada_a_borrar
                                if not (p.get("_geom_x") == geom_x and p.get("_geom_y") == geom_y)
                            ]
                            st.toast(f"🗑️ {marca} eliminada del plan")
                            st.rerun()

            # --- Ahorro total estimado (Mejora 3) ---
            if precio_zona_max > 0 and precio_col_label in df_plan.columns:
                _precios_validos = pd.to_numeric(df_plan[precio_col_label], errors="coerce").dropna()
                if not _precios_validos.empty:
                    _precio_medio_plan = float(_precios_validos.mean())
                    # Estimación: depósito de 50L como referencia estándar
                    _litros_ref = 50
                    _ahorro_total = precio_zona_max - _precio_medio_plan
                    _ahorro_total_eur = max(0.0, _ahorro_total * _litros_ref)
                    st.metric(
                        label=f"💰 Ahorro estimado vs. la más cara de la zona (depósito {_litros_ref}L)",
                        value=f"{_ahorro_total_eur:.2f} €",
                        delta=f"{_ahorro_total:.3f} €/L más barato",
                        help="Estimación basada en un depósito de referencia de 50L. El ahorro real depende del tamaño real de tu depósito."
                    )

            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("🗑️ Vaciar Mi Plan", type="secondary"):
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


            gmaps_url, omitidas = generate_google_maps_url(track, gdf_export)
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

            if _using_gpx and _gpx_bytes:
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
    # 6. 🏍️ Radar de Autonomía Crítica (Supervivencia Geográfica Real)
    st.subheader("🏍️ Radar de Autonomía Crítica")
    st.caption(
        "Análisis de los tramos entre gasolineras comparado con tu autonomía. "
        "Los tramos **rojos** en el mapa marcan zonas donde podrías quedarte sin combustible."
    )

    tramos, route_total_km = calculate_autonomy_radar(track, _r.get("gdf_within", gdf_top), autonomia_km)

    # --- Autonomy Radar UI Components ---
    ui_components.render_autonomy_radar_ui(tramos, route_total_km, autonomia_km)

    st.markdown("---")

else:
    # -----------------------------------------------------------------------
    # PANTALLA INICIAL — Estado vacío con CTA activo (Zero-Friction Onboarding)
    # -----------------------------------------------------------------------
    ui_components.render_welcome_screen(is_mobile=is_mobile)

    # ----- Demo CTA -------------------------------------------------------
    # Psicología: reducir la barrera de entrada («¿Y si no tengo un GPX ahora?»)
    # con un botón de prueba inmediata que carga una ruta real de 55 km.
    st.markdown("<br>", unsafe_allow_html=True)
    _demo_col, _ = st.columns([2, 3])
    with _demo_col:
        if st.button(
            "🚗  Probar herramienta con ruta Circular Sierra de Gredos",
            use_container_width=True,
            help="Carga automáticamente una ruta real circular de 6 puertos para que veas la app en funcionamiento sin necesidad de subir un GPX.",
        ):
            # Activar modo demo y relanzar la app para que el pipeline lo detecte
            st.session_state["demo_mode"] = True
            st.rerun()
