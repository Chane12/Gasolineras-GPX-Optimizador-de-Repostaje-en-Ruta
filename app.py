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
import streamlit as st
from streamlit_folium import st_folium

from gasolineras_ruta import (
    CRS_UTM30N,
    CRS_WGS84,
    RouteTextError,
    build_route_buffer,
    build_stations_geodataframe,
    calculate_global_optimal_stops,
    enrich_gpx_with_stops,
    enrich_stations_with_osrm,
    fetch_gasolineras,
    filter_cheapest_stations,
    generate_google_maps_url,
    generate_map,
    get_route_from_text,
    load_gpx_track,
    simplify_track,
    spatial_join_within_buffer,
    validate_gpx_track,
    _GMAPS_MAX_WAYPOINTS,
)

# ---------------------------------------------------------------------------
# Caché de datos — evitar recalcular en cada interacción
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def cached_fetch_gasolineras() -> object:
    """Descarga todas las gasolineras con caché de 30 minutos."""
    return fetch_gasolineras()


@st.cache_resource(ttl=1800, show_spinner=False)
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
# CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .sidebar-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 1.2rem;
        margin-bottom: 0.4rem;
    }

    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; color: #0f172a; }
    div[data-testid="stMetricLabel"] {
        font-size: 0.78rem; font-weight: 500; color: #64748b;
        text-transform: uppercase; letter-spacing: 0.025em;
    }

    div.stButton > button {
        background: #2563eb !important;
        color: white !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        height: 2.75rem !important;
        border: none !important;
        box-shadow: 0 4px 6px -1px rgba(37,99,235,0.2) !important;
        transition: all 0.2s ease-in-out !important;
        margin-top: 0.5rem;
    }
    div.stButton > button:hover {
        background: #1d4ed8 !important;
        transform: translateY(-1px);
        box-shadow: 0 10px 15px -3px rgba(37,99,235,0.3) !important;
    }

    /* --- Welcome screen --- */
    .welcome-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3rem 2rem;
        text-align: center;
        background: white;
        border: 1px dashed #cbd5e1;
        border-radius: 12px;
        margin-top: 2rem;
    }
    .welcome-icon  { font-size: 3.5rem; margin-bottom: 0.8rem; }
    .welcome-title { font-size: 1.4rem; font-weight: 700; color: #1e293b; margin-bottom: 0.5rem; }
    .welcome-text  { font-size: 0.95rem; color: #64748b; max-width: 560px; line-height: 1.6; margin-bottom: 1.5rem; }

    /* --- Cost box: MOBILE-FIRST grid --- */
    .cost-box {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        border: 1px solid #86efac;
        border-radius: 10px;
        padding: 18px 20px;
        margin: 12px 0;
    }
    .cost-box-title { font-weight: 700; color: #166534; font-size: 1rem; margin-bottom: 6px; }
    .cost-saving    { font-size: 1.4rem; font-weight: 800; color: #16a34a; }

    /* Cost grid snaps to single column on narrow screens */
    .cost-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        margin-top: 10px;
    }
    /* Cost breakdown row also wraps on small screens */
    .cost-breakdown {
        margin-top: 14px;
        padding-top: 12px;
        border-top: 1px solid #86efac;
        display: flex;
        flex-wrap: wrap;
        gap: 1.5rem;
    }

    /* --- Scroll-trap guard: disable pointer events on map iframe touch --- */
    .map-guard {
        position: relative;
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }
    .map-guard-overlay {
        position: absolute;
        inset: 0;
        background: rgba(255,255,255,0.01);
        z-index: 999;
        display: flex;
        align-items: flex-end;
        justify-content: center;
        padding-bottom: 12px;
        pointer-events: none;
    }

    .stDataFrame { border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0; }

    /* ============================================================
       MOBILE BREAKPOINTS — target < 768px (tablets / phones)
       ============================================================ */
    @media (max-width: 768px) {
        /* Stack cost grid vertically */
        .cost-grid { grid-template-columns: 1fr !important; }
        /* Stack breakdown items too */
        .cost-breakdown { flex-direction: column; gap: 0.75rem; }
        /* Smaller headings */
        .welcome-title { font-size: 1.2rem; }
        .welcome-text  { font-size: 0.88rem; }
        /* Prevent map from trapping scroll on touch devices */
        iframe { touch-action: pan-y !important; }
    }

    /* Extra small phones (320–480px) */
    @media (max-width: 480px) {
        .cost-box { padding: 14px 12px; }
        .cost-saving { font-size: 1.15rem; }
        div[data-testid="stMetricValue"] { font-size: 1.2rem; }
        .welcome-container { padding: 2rem 1rem; }
    }

    /* === Radar de Autonomía Crítica === */
    .radar-header {
        font-size: 1.1rem; font-weight: 700; color: #0f172a;
        display: flex; align-items: center; gap: 0.5rem;
        margin-bottom: 12px;
    }
    .radar-summary {
        display: flex; gap: 16px; flex-wrap: wrap;
        margin-bottom: 14px;
    }
    .radar-chip {
        padding: 6px 14px; border-radius: 99px;
        font-size: 0.82rem; font-weight: 700;
    }
    .radar-safe   { background: #dcfce7; color: #166534;  border: 1px solid #86efac; }
    .radar-warn   { background: #fef9c3; color: #854d0e;  border: 1px solid #fde047; }
    .radar-crit   { background: #fee2e2; color: #991b1b;  border: 1px solid #fca5a5; }
    .radar-box {
        background: white; border: 1px solid #e2e8f0;
        border-radius: 10px; padding: 16px 20px; margin-bottom: 8px;
    }
    .radar-box-crit { border-left: 4px solid #ef4444; }
    .radar-box-warn { border-left: 4px solid #eab308; }
    .radar-box-safe { border-left: 4px solid #22c55e; }
    .radar-km-badge {
        font-size: 1.6rem; font-weight: 800; color: #0f172a;
    }
    .radar-detail { font-size: 0.82rem; color: #64748b; margin-top: 2px; }
    @media (max-width: 768px) {
        .radar-summary { flex-direction: column; gap: 8px; }
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Cabecera principal
# ---------------------------------------------------------------------------
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
_litros_default = float(qp.get("litros", 20.0))
_consumo_default = float(qp.get("consumo", 4.5))
_inicio_pct_default = int(qp.get("inicio_pct", 100))
_autonomia_default = int(qp.get("autonomia", 0))

# ---------------------------------------------------------------------------
# BARRA LATERAL — Controles de Configuración
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Configuración del Viaje")
    st.markdown("---")

    # 1. Entrada de ruta (tabs: Texto | GPX)
    st.markdown('<p class="sidebar-title">1. Ruta</p>', unsafe_allow_html=True)
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
            "Elige un archivo .gpx:", type=["gpx"], label_visibility="collapsed"
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
        with st.expander("¿Cómo obtengo mi archivo GPX?"):
            st.markdown(
                """
                - **Wikiloc**: ruta → Descargar → *.gpx*
                - **Komoot**: ruta → ⋯ → *Exportar como GPX*
                - **Garmin**: actividad → *Exportar GPX*
                - **Strava**: actividad → ⋯ → *Exportar GPX*
                - **Google Maps**: usa mapstogpx.com
                """
            )

    # 2. Combustible
    st.markdown('<p class="sidebar-title">2. Tipo de Combustible</p>', unsafe_allow_html=True)
    combustible_elegido = st.selectbox(
        "Combustible:", options=list(COMBUSTIBLES.keys()),
        index=list(COMBUSTIBLES.keys()).index(_fuel_default),
        label_visibility="collapsed",
    )
    fuel_column = COMBUSTIBLES[combustible_elegido]

    # 3. Datos del vehículo (para estimador de coste y autonomía)
    st.markdown('<p class="sidebar-title">3. Tu Vehículo</p>', unsafe_allow_html=True)
    usar_vehiculo = st.checkbox(
        "Introducir datos de mi vehículo",
        value=False,
        help="Activa esta opción para calcular el consumo estimado y el coste del repostaje.",
    )
    if usar_vehiculo:
        with st.expander("Parámetros del depósito y consumo", expanded=True):
            deposito_total_l = st.number_input(
                "Capacidad del depósito (litros)",
                min_value=5.0, max_value=300.0,
                value=max(5.0, _litros_default) if _litros_default > 0 else 20.0,
                step=1.0,
                help="Litros totales que cabe en el depósito de tu vehículo.",
            )
            consumo_l100km = st.number_input(
                "Consumo aproximado (L/100 km)",
                min_value=1.0, max_value=40.0,
                value=_consumo_default,
                step=0.5,
                help="Consumo medio de tu vehículo. Consúltalo en el cuadro de mandos o en la ficha técnica.",
            )
            fuel_inicio_pct = st.slider(
                "Combustible disponible al salir (%)",
                min_value=0, max_value=100,
                value=_inicio_pct_default,
                step=5,
                help="Nivel de combustible en el depósito al inicio de la ruta.",
            )
            combustible_actual_l = deposito_total_l * fuel_inicio_pct / 100.0
            st.caption(
                f"▸ Tienes **{combustible_actual_l:.1f} L** disponibles "
                f"→ autonomía estimada de **{(combustible_actual_l / consumo_l100km * 100):.0f} km**"
                if consumo_l100km > 0 else ""
            )
        autonomia_km = int(combustible_actual_l / consumo_l100km * 100) if consumo_l100km > 0 else 0
    else:
        # Valores neutros cuando el vehículo no está configurado
        deposito_total_l = 0.0
        consumo_l100km = 0.0
        fuel_inicio_pct = 100
        combustible_actual_l = 0.0
        autonomia_km = 0
    st.markdown('<p class="sidebar-title">4. Filtros Avanzados</p>', unsafe_allow_html=True)
    with st.expander("Ajustar parámetros de búsqueda", expanded=False):
        radio_km = st.slider(
            "Distancia máxima a la ruta (km)",
            min_value=1, max_value=15, value=_buffer_default, step=1,
            help="Distancia lateral máxima al track para incluir gasolineras.",
        )
        top_n = st.slider("Gasolineras a mostrar", min_value=1, max_value=20, value=_top_default, step=1)
        st.markdown("---")
        buscar_tramos = st.checkbox(
            "Buscar gasolinera obligatoriamente cada X km",
            value=True,
            help="Añade la gasolinera más barata por tramo. Ideal para asegurar autonomía en rutas largas o vehículos con depósitos pequeños."
        )
        if buscar_tramos:
            segment_km = st.slider("Intervalo de seguridad (km)", min_value=10, max_value=300, value=50, step=10)
        else:
            segment_km = 0.0

    buffer_m = radio_km * 1000

    # Botón búsqueda
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("🔍 Iniciar Búsqueda", use_container_width=True)

    st.markdown("---")

    # Botón para compartir configuración por URL (F2)
    if st.button("🔗 Copiar enlace con esta configuración", use_container_width=True):
        st.query_params.update({
            "fuel":       combustible_elegido,
            "buffer":     str(radio_km),
            "top":        str(top_n),
            "litros":     str(int(deposito_total_l)),
            "consumo":    str(consumo_l100km),
            "inicio_pct": str(fuel_inicio_pct),
            "autonomia":  str(autonomia_km),
        })
        st.toast("✅ URL actualizada. ¡Copia la barra de direcciones para compartirla! 📌", icon="🔗")

    st.caption("Datos en tiempo real del MITECO · Ministerio de Transición Ecológica.")

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
            with tempfile.NamedTemporaryFile(delete=False, suffix=".gpx") as tmp:
                tmp.write(_gpx_bytes)
                tmp_path = Path(tmp.name)
        track = None   # se asigna en el bloque try más abajo

    with st.status("⛽ Buscando las mejores gasolineras para tu viaje…", expanded=True) as status:
        try:
            st.write("⏬ Descargando precios en tiempo real del MITECO…")
            df_gas = cached_fetch_gasolineras()

            # --- Carga del track (solo GPX; en modo texto ya está listo) ---
            if track is None:
                st.write("🗺️ Leyendo y validando tu ruta GPX…")
                track = load_gpx_track(tmp_path)
                validate_gpx_track(track)

            st.write("✂️ Simplificando y procesando la geometría de la ruta…")
            track_simp = simplify_track(track, tolerance_deg=0.0005)

            st.write("📡 Cruzando con estaciones de servicio cercanas a tu ruta…")
            gdf_buffer = build_route_buffer(track_simp, buffer_meters=buffer_m)
            # T1: El GeoDataFrame con R-Tree se construye solo una vez (caché)
            gdf_utm = cached_build_stations_gdf(df_gas)
            gdf_within = spatial_join_within_buffer(gdf_utm, gdf_buffer)

            if fuel_column not in gdf_within.columns or gdf_within[fuel_column].isna().all():
                status.update(label="⚠️ Sin resultados para ese combustible", state="error", expanded=True)
                st.warning(
                    f"No encontramos gasolineras con precio de **{combustible_elegido}** "
                    f"en un radio de {radio_km} km. "
                    "Prueba a ampliar la distancia en las opciones avanzadas."
                )
                st.stop()

            st.write("💰 Calculando el ranking de las más baratas…")
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
            try:
                gdf_top = enrich_stations_with_osrm(
                    gdf_top,
                    track_original=track,
                )
            except Exception:  # silencio total: si falla OSRM el mapa sigue funcionando
                pass

            # ---- Dijkstra: Plan de Repostaje con Óptimo Global ----
            gdf_dijkstra: object | None = None
            coste_dijkstra: float | None = None
            dijkstra_error: str | None = None
            if usar_vehiculo and deposito_total_l > 0 and consumo_l100km > 0:
                st.write("🧮 Calculando plan de repostaje óptimo (Dijkstra)…")
                try:
                    gdf_dijkstra, coste_dijkstra = calculate_global_optimal_stops(
                        gdf_within=gdf_within,
                        fuel_column=fuel_column,
                        track_utm=track_utm,
                        deposito_total_l=deposito_total_l,
                        consumo_100km=consumo_l100km,
                        combustible_actual_l=combustible_actual_l,
                        reserva_minima_pct=10.0,
                    )
                except ValueError as exc:
                    dijkstra_error = str(exc)
                except Exception as exc:
                    dijkstra_error = f"Error inesperado en el optimizador: {exc}"

            st.write("🖼️ Generando mapa interactivo…")
            _, mapa_obj = generate_map(
                track_original=track,
                gdf_top_stations=gdf_top,
                fuel_column=fuel_column,
                autonomy_km=float(autonomia_km),  # F3: Zonas de peligro por autonomía
            )

            status.update(label="✅ ¡Ruta analizada y optimizada!", state="complete", expanded=False)

            # --- Guardar resultados en session_state para sobrevivir reruns ---
            st.session_state["pipeline_results"] = {
                "gdf_top":        gdf_top,
                "gdf_within":     gdf_within,
                "mapa_obj":       mapa_obj,
                "track":          track,
                "track_utm":      track_utm,
                "using_demo":     _using_demo,
                "using_gpx":      _input_mode in ("gpx", "demo"),
                "gpx_bytes":      _gpx_bytes,
                "gdf_dijkstra":   gdf_dijkstra,
                "coste_dijkstra": coste_dijkstra,
                "dijkstra_error": dijkstra_error,
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
    gdf_within      = _r["gdf_within"]
    mapa_obj        = _r["mapa_obj"]
    track           = _r["track"]
    track_utm       = _r["track_utm"]
    _using_demo     = _r["using_demo"]
    _using_gpx      = _r.get("using_gpx", False)
    _gpx_bytes      = _r.get("gpx_bytes")
    gdf_dijkstra    = _r.get("gdf_dijkstra")
    coste_dijkstra  = _r.get("coste_dijkstra")
    dijkstra_error  = _r.get("dijkstra_error")

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
    precio_top_min = gdf_top[fuel_column].min()
    precio_top_max = gdf_top[fuel_column].max()
    precio_zona_max = gdf_within[fuel_column].max()
    total_zona = len(gdf_within)
    total_mostradas = len(gdf_top)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Mejor Precio Encontrado", f"{precio_top_min:.3f} €/L")
    with col2:
        ahorro_vs_caro = precio_zona_max - precio_top_min
        st.metric(
            "Ahorro vs. Más Cara de la Zona",
            f"{ahorro_vs_caro:.3f} €/L",
            delta=None,
        )
    with col3:
        st.metric("Estaciones Sugeridas", f"{total_mostradas}")
    with col4:
        st.metric(f"Total en ±{radio_km} km", f"{total_zona} Est.")

    # 2. Estimador de coste inteligente basado en el vehículo
    if usar_vehiculo and deposito_total_l > 0 and consumo_l100km > 0:
        # Longitud real de la ruta en km (usando el track UTM ya proyectado)
        ruta_km = track_utm.length / 1000.0

        litros_necesarios_ruta = ruta_km * consumo_l100km / 100.0
        litros_a_repostar = max(0.0, litros_necesarios_ruta - combustible_actual_l)
        necesita_reposte = litros_a_repostar > 0

        coste_barata = litros_a_repostar * precio_top_min if necesita_reposte else 0.0
        coste_libre   = litros_a_repostar * precio_zona_max if necesita_reposte else 0.0
        ahorro_total  = coste_libre - coste_barata

        # Estado de la barra de combustible
        pct_actual = min(100, int(fuel_inicio_pct))
        pct_necesario = min(100, int((litros_necesarios_ruta / deposito_total_l) * 100)) if deposito_total_l > 0 else 0

        color_estado = "#16a34a" if not necesita_reposte else "#dc2626"
        label_estado = "✅ Llegas sin repostar" if not necesita_reposte else f"⛽ Necesitas reponer ~{litros_a_repostar:.1f} L"

        # Pre-calcular el bloque HTML condicional ANTES del f-string principal.
        # Anidar un f'''...''' dentro de un f"""...""" hace que Streamlit lo
        # trate como texto plano en lugar de HTML — esto lo evita.
        if necesita_reposte:
            cost_breakdown_html = (
                '<div class="cost-breakdown">'
                f'<div><div style="font-size:0.78rem;color:#166534;font-weight:600;">REPOSTANDO EN LA MÁS BARATA</div>'
                f'<div class="cost-saving">{coste_barata:.2f} €</div></div>'
                f'<div><div style="font-size:0.78rem;color:#991b1b;font-weight:600;">SI REPOSTARAS EN LA MÁS CARA</div>'
                f'<div style="font-size:1.3rem;font-weight:800;color:#dc2626;">{coste_libre:.2f} €</div></div>'
                f'<div><div style="font-size:0.78rem;color:#1e40af;font-weight:600;">AHORRO POTENCIAL</div>'
                f'<div style="font-size:1.3rem;font-weight:800;color:#2563eb;">{ahorro_total:.2f} €</div></div>'
                '</div>'
            )
        else:
            cost_breakdown_html = (
                '<div style="margin-top:10px;font-size:0.9rem;color:#166534;">'
                "Con el combustible actual llegas al destino. ¡No necesitas parar!</div>"
            )

        st.markdown(
            f"""
            <div class="cost-box">
                <div class="cost-box-title">🚗 Análisis de Combustible para esta Ruta ({ruta_km:.1f} km)</div>
                <div class="cost-grid">
                    <div>
                        <div style="font-size:0.78rem;color:#475569;font-weight:600;">DEPÓSITO AL SALIR</div>
                        <div style="font-size:1.3rem;font-weight:800;color:#1e293b;">{combustible_actual_l:.1f} L <span style="font-size:0.9rem;font-weight:500;color:#64748b;">({fuel_inicio_pct}%)</span></div>
                    </div>
                    <div>
                        <div style="font-size:0.78rem;color:#475569;font-weight:600;">CONSUMO ESTIMADO</div>
                        <div style="font-size:1.3rem;font-weight:800;color:#1e293b;">{litros_necesarios_ruta:.1f} L <span style="font-size:0.9rem;font-weight:500;color:#64748b;">({consumo_l100km} L/100km)</span></div>
                    </div>
                    <div>
                        <div style="font-size:0.78rem;color:{color_estado};font-weight:600;">ESTADO</div>
                        <div style="font-size:1.1rem;font-weight:700;color:{color_estado};">{label_estado}</div>
                    </div>
                </div>
                {cost_breakdown_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.divider()

    # -----------------------------------------------------------------------
    # 2b. Plan de Repostaje Óptimo (Dijkstra) — solo si hay datos de vehículo
    # -----------------------------------------------------------------------
    if usar_vehiculo and deposito_total_l > 0 and consumo_l100km > 0:
        st.subheader("🧮 Plan de Repostaje Óptimo (Dijkstra)")
        st.caption(
            "Secuencia de paradas de **coste mínimo global** calculada con el algoritmo de Dijkstra "
            "sobre un grafo dirigido acíclico. Garantiza el óptimo global frente a la heurística greedy."
        )

        if dijkstra_error:
            st.warning(
                f"⚠️ El optimizador no pudo calcular un plan de paradas:\n\n*{dijkstra_error}*\n\n"
                "Prueba a aumentar el radio de búsqueda de gasolineras o a salir con más combustible."
            )
        elif gdf_dijkstra is not None:
            ruta_km = track_utm.length / 1000.0
            litros_ruta = ruta_km * consumo_l100km / 100.0
            litros_a_repostar_total = max(0.0, litros_ruta - combustible_actual_l)

            if gdf_dijkstra.empty:
                # No hace falta repostar
                st.success(
                    f"✅ **No necesitas parar a repostar.** "
                    f"Con los **{combustible_actual_l:.1f} L** que llevas llegas al destino. "
                    f"Coste adicional de combustible: **0,00 €**"
                )
            else:
                n_paradas = len(gdf_dijkstra)
                # Precio medio de la zona para comparar
                precio_medio_zona = float(gdf_within[fuel_column].dropna().mean()) if not gdf_within.empty else 0.0
                coste_medio_zona = litros_a_repostar_total * precio_medio_zona if litros_a_repostar_total > 0 else 0.0
                ahorro_dijkstra = coste_medio_zona - coste_dijkstra if coste_dijkstra is not None else 0.0

                # --- Métricas resumen del plan ---
                dk_col1, dk_col2, dk_col3 = st.columns(3)
                with dk_col1:
                    st.metric("Paradas Óptimas", f"{n_paradas}")
                with dk_col2:
                    st.metric("Coste Total Estimado", f"{coste_dijkstra:.2f} €")
                with dk_col3:
                    if ahorro_dijkstra > 0:
                        st.metric("Ahorro vs. Precio Medio Zona", f"{ahorro_dijkstra:.2f} €", delta=f"-{ahorro_dijkstra:.2f} €")
                    else:
                        st.metric("Ahorro vs. Precio Medio Zona", "—")

                st.markdown("**Secuencia de paradas:**")

                # --- Tabla de paradas óptimas ---
                _dk_cols = {
                    "km_ruta":            "Km en Ruta",
                    "Rótulo":             "Gasolinera",
                    "Municipio":          "Municipio",
                    fuel_column:          "€/L",
                    "litros_a_repostar":  "Litros a Repostar",
                    "coste_parada_eur":   "Coste Parada (€)",
                }
                _dk_col_map = {k: v for k, v in _dk_cols.items() if k in gdf_dijkstra.columns}
                df_dk = gdf_dijkstra[list(_dk_col_map.keys())].copy()
                df_dk = df_dk.rename(columns=_dk_col_map)

                _dk_precio_min = float(df_dk["€/L"].min()) if "€/L" in df_dk.columns else 0.0
                _dk_precio_max = float(df_dk["€/L"].max()) if "€/L" in df_dk.columns else 2.0

                dk_table_event = st.dataframe(
                    df_dk,
                    use_container_width=True,
                    hide_index=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    column_config={
                        "Km en Ruta": st.column_config.NumberColumn(format="%.1f km"),
                        "€/L": st.column_config.ProgressColumn(
                            "€/L",
                            help="Precio en €/L",
                            format="%.3f €",
                            min_value=_dk_precio_min * 0.98,
                            max_value=_dk_precio_max * 1.02,
                        ),
                        "Litros a Repostar": st.column_config.NumberColumn(format="%.1f L"),
                        "Coste Parada (€)": st.column_config.NumberColumn(format="%.2f €"),
                    },
                )

                # Centrar el mapa si el usuario selecciona una parada del plan óptimo
                dk_selected_rows = dk_table_event.selection.get("rows", [])
                if dk_selected_rows:
                    sel_idx = dk_selected_rows[0]
                    # Generar una firma única para la selección de esta tabla
                    dk_sel_id = f"dk_{sel_idx}"
                    if st.session_state.get("last_selected_idx") != dk_sel_id:
                        sel_nombre = df_dk.iloc[sel_idx].get("Gasolinera", "la gasolinera")
                        
                        # Obtener las coordenadas originales desde gdf_dijkstra
                        # (df_dk no tiene geometría, necesitamos gdf_dijkstra en EPSG:4326)
                        geom = gdf_dijkstra.to_crs("EPSG:4326").iloc[sel_idx].geometry
                        
                        st.session_state["map_selected_station"] = {
                            "center": [geom.y, geom.x],
                            "zoom":   15,
                            "nombre": sel_nombre,
                        }
                        st.session_state["last_selected_idx"] = dk_sel_id
                        st.toast(f"📍 Recentrando mapa en **{sel_nombre}** (Parada Óptima)…")
                        st.rerun()

                # Nota metodológica
                st.caption(
                    "ℹ️ Los litros indicados cubren el tramo hasta la siguiente parada (con 10% de reserva de seguridad). "
                    "El coste total es la suma del combustible comprado en ruta, sin incluir el que ya llevas al salir."
                )

                # --- 📱 EXPORTACIÓN DE LA RUTA ---
                st.write("")  # Espaciador
                if not _using_gpx:
                    # MODO TEXTO -> Google Maps URL
                    gmaps_url, omitidas = generate_google_maps_url(track_utm, gdf_dijkstra)
                    st.link_button(
                        "📱 Llevarme allí (Abrir en Google Maps)",
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
                    # MODO GPX -> Mismo archivo con Waypoints inyectados
                    if _gpx_bytes:
                        gpx_xml_con_paradas = enrich_gpx_with_stops(
                            _gpx_bytes,
                            gdf_dijkstra,
                            fuel_column=fuel_column
                        )
                        st.download_button(
                            label="💾 Descargar GPX Original + Paradas",
                            data=gpx_xml_con_paradas,
                            file_name="Ruta_Optimizada_Gasolineras.gpx",
                            mime="application/gpx+xml",
                            type="primary",
                            help="Descarga tu mismo track inalterado, inyectando las gasolineras seleccionadas como Waypoints."
                        )

        st.divider()

    # -----------------------------------------------------------------------
    # 3. Mapa — aparece primero para impacto visual inmediato
    # -----------------------------------------------------------------------
    header_map = "🗺️ Mapa Interactivo de la Ruta"
    if autonomia_km > 0:
        header_map += f"  ·  ⚠️ Zonas de riesgo con {autonomia_km} km de autonomía"
    st.subheader(header_map)
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

    st_folium(
        mapa_obj,
        width="100%",
        height=map_height,
        center=map_center,
        zoom=map_zoom,
        returned_objects=[],
    )
    if not map_active:
        st.caption("ℹ️ Activa la interacción arriba para hacer zoom y desplazarte por el mapa.")

    st.divider()

    # -----------------------------------------------------------------------
    # 4. Tabla de resultados
    # -----------------------------------------------------------------------
    st.subheader("🏆 Ranking de Gasolineras")
    st.caption(
        "Haz clic en una fila para centrar el mapa en esa gasolinera (se actualiza en el próximo render). "
        "Haz clic en los marcadores del mapa para ver más detalles."
    )

    COLS = {
        "km_ruta":            "Km en Ruta",
        "Rótulo":             "Rótulo / Marca",
        "Municipio":          "Municipio",
        "Dirección":          "Dirección",
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

    # Nota: el formateo de números (km, min, €/L) se gestiona en column_config
    # más abajo — no aplicamos .apply() que convertiría los números a strings
    # y rompería el ProgressColumn y NumberColumn de Streamlit.

    # Coordenadas WGS84 de cada gasolinera (para el zoom del mapa)
    gdf_top_wgs84 = gdf_top.to_crs("EPSG:4326")
    station_coords = [
        (row.geometry.y, row.geometry.x)
        for _, row in gdf_top_wgs84.iterrows()
    ]

    # --- column_config ---
    precio_col_label = f"Precio {combustible_elegido} (€/L)"
    _precio_min = float(df_show[precio_col_label].min()) if precio_col_label in df_show.columns else 0.0
    _precio_max = float(df_show[precio_col_label].max()) if precio_col_label in df_show.columns else 2.0

    col_config = {
        precio_col_label: st.column_config.ProgressColumn(
            precio_col_label,
            help="Precio en €/L. Barra proporcional: verde = más barato, rojo = más caro.",
            format="%.3f €",
            min_value=_precio_min * 0.98,
            max_value=_precio_max * 1.02,
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
        "Rótulo / Marca": st.column_config.TextColumn(
            "Rótulo / Marca",
            help="Nombre comercial de la gasolinera.",
        ),
        # La dirección se muestra como enlace a Google Maps
        "_maps_url": st.column_config.LinkColumn(
            "Dirección 📍",
            help="Clic para abrir en Google Maps (desde allí puedes copiar la dirección).",
            display_text="📍 Ver / Copiar dirección",
        ),
        # Ocultar la columna de texto plano (ya está en el enlace)
        "Dirección": None,
    }
    # Eliminar del config las columnas que no existen en df_show
    # (None en column_config oculta la columna sin eliminarla del df)
    col_config = {k: v for k, v in col_config.items() if k in df_show.columns or v is None}

    table_event = st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config=col_config,
    )

    # Determinar el centro del mapa según la selección y persistir en session_state
    selected_rows = table_event.selection.get("rows", [])
    if selected_rows:
        sel_idx = selected_rows[0]
        # Evitar bucle infinito de reruns comprobando si ya lo hemos procesado
        if st.session_state.get("last_selected_idx") != sel_idx:
            sel_nombre = df_show.iloc[sel_idx].get("Rótulo / Marca", "la gasolinera")
            st.session_state["map_selected_station"] = {
                "center": list(station_coords[sel_idx]),
                "zoom":   15,
                "nombre": sel_nombre,
            }
            st.session_state["last_selected_idx"] = sel_idx
            st.toast(f"📍 Recentrando mapa en **{sel_nombre}**…")
            st.rerun()
    else:
        # Cuando el usuario deselecciona (haciendo click fuera)
        if "last_selected_idx" in st.session_state:
            del st.session_state["last_selected_idx"]
            if "map_selected_station" in st.session_state:
                del st.session_state["map_selected_station"]
            st.rerun()

    st.divider()

    # -----------------------------------------------------------------------
    # 5. 🏍️ Radar de Autonomía Crítica
    # -----------------------------------------------------------------------
    st.subheader("🏍️ Radar de Autonomía Crítica")
    st.caption(
        "Análisis de los tramos entre gasolineras comparado con tu autonomía. "
        "Los tramos **rojos** en el mapa marcan zonas donde podrías quedarte sin combustible."
    )

    # --- Cálculo de gaps entre gasolineras ---
    import pyproj as _pyproj
    _geod_radar = _pyproj.Geod(ellps="WGS84")
    _track_coords = list(track.coords)  # (lon, lat)
    _lons = [c[0] for c in _track_coords]
    _lats = [c[1] for c in _track_coords]
    _, _, _dists_m = _geod_radar.inv(_lons[:-1], _lats[:-1], _lons[1:], _lats[1:])
    route_total_km = sum(_dists_m) / 1000.0

    # Km de las gasolineras sugeridas en la ruta (ya calculados por el pipeline)
    station_km_list: list[float] = []
    if "km_ruta" in gdf_top.columns:
        station_km_list = sorted(gdf_top["km_ruta"].dropna().tolist())

    # Checkpoints: km 0, cada gasolinera, km final
    checkpoints = [0.0] + station_km_list + [route_total_km]

    # Calcular gap entre cada par de checkpoints
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
            # Sin autonomía configurada, solo mostramos los gaps
            pct = 0.0
            nivel = "seguro"
            emoji = "🟢"
            label = "—"

        # Nombre del tramo
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

    # --- Resumen general del radar ---
    n_crit = sum(1 for t in tramos if t["nivel"] == "critico")
    n_warn = sum(1 for t in tramos if t["nivel"] == "atencion")
    n_safe = sum(1 for t in tramos if t["nivel"] == "seguro")
    max_gap = max((t["gap_km"] for t in tramos), default=0.0)
    tramo_crit = max(tramos, key=lambda t: t["gap_km"]) if tramos else None

    # Banner de estado global
    if n_crit > 0:
        global_estado_html = (
            '<div style="background:#fee2e2; border:1px solid #fca5a5; border-radius:10px; '
            'padding:14px 18px; margin-bottom:14px;">'
            f'<b style="color:#991b1b; font-size:1rem;">🔴 Ruta con {n_crit} tramo(s) CRÍTICO(S)</b><br>'
            f'<span style="color:#7f1d1d; font-size:0.88rem;">'
            f'El tramo más largo sin gasolinera es de <b>{max_gap:.1f} km</b>. '
            f'Tu autonomía configurada es de <b>{autonomia_km} km</b>. '
            'Revisa los tramos marcados en rojo antes de salir.</span></div>'
        ) if autonomia_km > 0 else (
            '<div style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:10px; '
            'padding:14px 18px; margin-bottom:14px;">'
            f'<b style="color:#334155;">ℹ️ Tramo más largo sin gasolinera: <b>{max_gap:.1f} km</b></b><br>'
            '<span style="color:#64748b; font-size:0.88rem;">Configura tu autonomía en el sidebar para activar las alertas críticas.</span></div>'
        )
    elif n_warn > 0:
        global_estado_html = (
            '<div style="background:#fef9c3; border:1px solid #fde047; border-radius:10px; '
            'padding:14px 18px; margin-bottom:14px;">'
            f'<b style="color:#854d0e; font-size:1rem;">🟡 Ruta con {n_warn} tramo(s) de ATENCIÓN</b><br>'
            f'<span style="color:#713f12; font-size:0.88rem;">'
            f'Ningún tramo supera tu autonomía ({autonomia_km} km), pero hay segmentos de más del 80%. '
            'Procura no llegar a esas zonas con el depósito bajo.</span></div>'
        )
    else:
        global_estado_html = (
            '<div style="background:#dcfce7; border:1px solid #86efac; border-radius:10px; '
            'padding:14px 18px; margin-bottom:14px;">'
            f'<b style="color:#166534; font-size:1rem;">🟢 Ruta completamente SEGURA</b><br>'
            f'<span style="color:#14532d; font-size:0.88rem;">'
            f'Todos los tramos entre gasolineras están por debajo de tu autonomía ({autonomia_km} km). '
            '¡Puedes salir tranquilo!</span></div>'
        ) if autonomia_km > 0 else (
            '<div style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:10px; '
            'padding:14px 18px; margin-bottom:14px;">'
            f'<b style="color:#334155;">ℹ️ Tramo más largo sin gasolinera: {max_gap:.1f} km</b><br>'
            '<span style="color:#64748b; font-size:0.88rem;">Configura tu autonomía en el sidebar para activar las alertas.</span></div>'
        )

    st.markdown(global_estado_html, unsafe_allow_html=True)

    # --- Chips de resumen rápido ---
    _chip_html = '<div class="radar-summary">'
    _chip_html += f'<span class="radar-chip radar-safe">🟢 {n_safe} tramo(s) seguros</span>'
    if n_warn:
        _chip_html += f'<span class="radar-chip radar-warn">🟡 {n_warn} tramo(s) de atención</span>'
    if n_crit:
        _chip_html += f'<span class="radar-chip radar-crit">🔴 {n_crit} tramo(s) críticos</span>'
    _chip_html += f'<span class="radar-chip" style="background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;">🛣️ Ruta total: {route_total_km:.1f} km</span>'
    if autonomia_km > 0:
        _chip_html += f'<span class="radar-chip" style="background:#eff6ff;color:#1e40af;border:1px solid #93c5fd;">⛽ Autonomía: {autonomia_km} km</span>'
    _chip_html += '</div>'
    st.markdown(_chip_html, unsafe_allow_html=True)

    # --- Detalle de cada tramo ---
    with st.expander("Ver detalle de todos los tramos", expanded=(n_crit > 0 or n_warn > 0)):
        for t in tramos:
            css_cls  = "radar-box-crit" if t["nivel"] == "critico" else (
                       "radar-box-warn" if t["nivel"] == "atencion" else "radar-box-safe")
            chip_cls = "radar-crit" if t["nivel"] == "critico" else (
                       "radar-warn" if t["nivel"] == "atencion" else "radar-safe")

            pct_bar  = min(100, int(t["pct"] * 100)) if autonomia_km > 0 else 0
            bar_color = "#ef4444" if t["nivel"] == "critico" else (
                        "#eab308" if t["nivel"] == "atencion" else "#22c55e")

            aviso = ""
            # 1. Avisos por AUTONOMÍA configurada (si el usuario la ha indicado)
            if autonomia_km > 0 and t["nivel"] == "critico":
                aviso += (f'<div style="margin-top:6px; font-size:0.8rem; color:#991b1b; font-weight:600;">'
                          f'⚠️ Supera tu autonomía en {t["gap_km"] - autonomia_km:.1f} km — '
                          'Repostar OBLIGATORIAMENTE antes de este tramo.</div>')
            elif autonomia_km > 0 and t["nivel"] == "atencion":
                aviso += (f'<div style="margin-top:6px; font-size:0.8rem; color:#854d0e; font-weight:600;">'
                          '⚡ Entra en este tramo con el depósito con buena autonomía restante.</div>')

            # 2. Avisos por DISTANCIA ABSOLUTA (independientes de la autonomía)
            if t["gap_km"] >= 100:
                aviso += (
                    '<div style="margin-top:6px; padding:7px 10px; background:#fef2f2; '
                    'border-left:3px solid #dc2626; border-radius:4px; font-size:0.82rem; color:#7f1d1d;">'
                    f'🚨 <b>Tramo muy largo ({t["gap_km"]:.0f} km sin gasolineras)</b> — '
                    'Inicia este tramo con el depósito <b>completamente lleno</b>. '
                    'En zonas de montaña o España vaciada can haber cortes de servicio.</div>'
                )
            elif t["gap_km"] >= 60:
                aviso += (
                    '<div style="margin-top:6px; padding:7px 10px; background:#fff7ed; '
                    'border-left:3px solid #f97316; border-radius:4px; font-size:0.82rem; color:#7c2d12;">'
                    f'⚠️ <b>Tramo largo ({t["gap_km"]:.0f} km sin gasolineras)</b> — '
                    'Procura no entrar con menos de medio depósito. '
                    'Comprueba que las gasolineras del tramo anterior estén abiertas.</div>'
                )

            st.markdown(f"""
            <div class="radar-box {css_cls}">
                <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:8px;">
                    <div>
                        <div class="radar-km-badge">{t['gap_km']:.1f} km</div>
                        <div class="radar-detail">Km {t['km_inicio']:.0f} → Km {t['km_fin']:.0f}</div>
                        <div style="font-size:0.85rem; color:#334155; margin-top:4px;">
                            <b>{t['origen']}</b> → <b>{t['destino']}</b>
                        </div>
                    </div>
                    <span class="radar-chip {chip_cls}">{t['emoji']} {t['label']}</span>
                </div>
                {f'<div style="margin-top:10px; background:#f1f5f9; border-radius:4px; height:6px; overflow:hidden;"><div style="height:6px; width:{pct_bar}%; background:{bar_color}; border-radius:4px;"></div></div>' if autonomia_km > 0 else ''}
                {aviso}
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

else:
    # -----------------------------------------------------------------------
    # PANTALLA INICIAL — Estado vacío con CTA activo (Zero-Friction Onboarding)
    # -----------------------------------------------------------------------
    st.markdown(
        """
        <div class="welcome-container">
            <div class="welcome-icon">🛣️⛽</div>
            <div class="welcome-title">Planificador Inteligente de Repostaje en Ruta</div>
            <div class="welcome-text">
                Indica el Origen y Destino o sube el GPX de tu próximo viaje, indica tu combustible y el depósito de tu vehículo.
                Encontramos las gasolineras más baratas de España <strong>en tiempo real</strong>
                cruzando datos geográficos con la API oficial del MITECO. ¡Ahorra en cada escapada!
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
