"""
app.py
======
Interfaz web (Streamlit) para el Optimizador de Gasolineras en Ruta.

Cómo ejecutar:
    streamlit run app.py
"""

import tempfile
from pathlib import Path

import geopandas as gpd
import streamlit as st
from streamlit_folium import st_folium

from gasolineras_ruta import (
    CRS_UTM30N,
    CRS_WGS84,
    ImpossibleRouteError,
    build_route_buffer,
    build_stations_geodataframe,
    calculate_optimal_stops,
    enrich_stations_with_osrm,
    fetch_gasolineras,
    filter_cheapest_stations,
    generate_map,
    load_gpx_track,
    simplify_track,
    spatial_join_within_buffer,
    validate_gpx_track,
)

# ---------------------------------------------------------------------------
# Caché de datos — evitar recalcular en cada interacción
# ---------------------------------------------------------------------------

@st.cache_data(ttl=1800, show_spinner=False)
def cached_fetch_gasolineras() -> object:
    """Descarga todas las gasolineras con caché de 30 minutos."""
    return fetch_gasolineras()


@st.cache_data(ttl=1800, show_spinner=False)
def cached_build_stations_gdf(_df) -> object:
    """
    Construye el GeoDataFrame con índice R-Tree (una vez cada 30 min).
    El prefijo '_' evita que Streamlit intente hashear el DataFrame.
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
_top_default = int(qp.get("top", 5))
_top_default = max(1, min(20, _top_default))
_litros_default = float(qp.get("litros", 0))
_consumo_default = float(qp.get("consumo", 5.0))
_inicio_pct_default = int(qp.get("inicio_pct", 20))
_autonomia_default = int(qp.get("autonomia", 0))

# ---------------------------------------------------------------------------
# BARRA LATERAL — Controles de Configuración
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3035/3035041.png", width=60)
    st.markdown("## ⚙️ Configuración del Viaje")
    st.markdown("---")

    # 1. Archivo GPX – uploader + modo demo
    st.markdown('<p class="sidebar-title">1. Archivo de Ruta (.GPX)</p>', unsafe_allow_html=True)
    gpx_file = st.file_uploader("Elige un archivo .gpx:", type=["gpx"], label_visibility="collapsed")

    # Si no hay archivo pero hay modo demo activo, indicarlo visualmente
    if gpx_file is None and st.session_state.get("demo_mode"):
        st.success("✅ Cargada ruta de demo (Madrid Norte ~55 km)")
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
    with st.expander("Parámetros del depósito y consumo", expanded=False):
        deposito_total_l = st.number_input(
            "Capacidad del depósito (litros)",
            min_value=5.0, max_value=300.0,
            value=max(5.0, _litros_default) if _litros_default > 0 else 50.0,
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

    # Calcular autonomía actual a partir de los datos del vehículo
    autonomia_km = int(combustible_actual_l / consumo_l100km * 100) if consumo_l100km > 0 else 0
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
            "Asegurar repostaje cada X km",
            help="Añade la gasolinera más barata por tramo. Ideal para motos."
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
        st.success("✅ URL actualizada. Copia la barra de direcciones de tu navegador para compartirla.")

    st.caption("Datos en tiempo real del MITECO · Ministerio de Transición Ecológica.")

# ---------------------------------------------------------------------------
# Pipeline de cálculo
# ---------------------------------------------------------------------------
_pipeline_active = run_btn or (st.session_state.get("demo_mode") and not run_btn)

# Bandera para saber si se usó el demo en este ciclo de ejecución
_using_demo = (_pipeline_active and gpx_file is None and st.session_state.get("demo_mode"))

if _pipeline_active:
    if gpx_file is None and not st.session_state.get("demo_mode"):
        st.error("📂 Primero sube tu archivo GPX.")
        st.stop()

    if _using_demo:
        # Cargar el GPX de demo desde disco
        demo_gpx_path = Path(__file__).parent / "demo_route.gpx"
        if not demo_gpx_path.exists():
            st.error("⚠️ No se encontró el archivo de demo. Contacta con el administrador.")
            st.stop()
        tmp_path = demo_gpx_path
    else:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gpx") as tmp:
            tmp.write(gpx_file.read())
            tmp_path = Path(tmp.name)

    progress = st.progress(0, text="Iniciando búsqueda…")

    try:
        progress.progress(8, text="⏬ Descargando precios en tiempo real…")
        df_gas = cached_fetch_gasolineras()

        progress.progress(20, text="🗺️ Leyendo tu ruta GPX…")
        track = load_gpx_track(tmp_path)

        # T3: Validación del GPX (tamaño + bbox España)
        progress.progress(28, text="🔎 Validando ruta…")
        validate_gpx_track(track)

        progress.progress(40, text="✂️ Simplificando la ruta…")
        track_simp = simplify_track(track, tolerance_deg=0.0005)

        progress.progress(55, text="📡 Buscando gasolineras cercanas…")
        gdf_buffer = build_route_buffer(track_simp, buffer_meters=buffer_m)
        # T1: El GeoDataFrame con R-Tree se construye solo una vez (caché)
        gdf_utm = cached_build_stations_gdf(df_gas)
        gdf_within = spatial_join_within_buffer(gdf_utm, gdf_buffer)

        progress.progress(72, text="💰 Calculando las más baratas…")

        if fuel_column not in gdf_within.columns or gdf_within[fuel_column].isna().all():
            st.warning(
                f"No encontramos gasolineras con precio de **{combustible_elegido}** "
                f"en un radio de {radio_km} km. "
                "Prueba a ampliar la distancia en las opciones avanzadas."
            )
            st.stop()

        gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simp], crs=CRS_WGS84).to_crs(CRS_UTM30N)
        track_utm = gdf_track_utm.geometry.iloc[0]

        # Longitud real de la ruta en km (se usa tanto en el planificador como en la UI)
        ruta_km = track_utm.length / 1000.0

        # Pre-computar km_ruta en gdf_within (necesario para el Greedy)
        progress.progress(72, text="📍 Calculando distancias en ruta...")
        mask_precio = gdf_within[fuel_column].notna() & (gdf_within[fuel_column] > 0)
        gdf_within = gdf_within.copy()
        gdf_within.loc[mask_precio, "km_ruta"] = (
            gdf_within.loc[mask_precio, "geometry"]
            .apply(lambda geom: track_utm.project(geom) / 1000.0)
        )

        # ----------------------------------------------------------------
        # Parámetros de autonomía derivados del vehículo
        # ----------------------------------------------------------------
        tiene_datos_vehiculo = deposito_total_l > 0 and consumo_l100km > 0

        if tiene_datos_vehiculo:
            autonomia_actual_km = float(autonomia_km)   # con el combustible de salida
            # Rango útil máximo = autonomía al 100% del depósito, con reserva del 15%
            autonomia_max_km = (deposito_total_l / consumo_l100km) * 100.0
            rango_util_maximo_km = autonomia_max_km * 0.85
        else:
            autonomia_actual_km = 0.0
            rango_util_maximo_km = 0.0

        # ----------------------------------------------------------------
        # MODO PRESCRIPTIVO: Planificador Greedy
        # ----------------------------------------------------------------
        planificador_activo = tiene_datos_vehiculo and autonomia_actual_km > 0
        itinerario: list[dict] = []

        progress.progress(76, text="🧩 Calculando itinerario óptimo...")
        if planificador_activo:
            itinerario, gdf_top = calculate_optimal_stops(
                gdf_within=gdf_within,
                fuel_column=fuel_column,
                autonomia_actual_km=autonomia_actual_km,
                rango_util_maximo_km=rango_util_maximo_km,
                distancia_total_ruta_km=ruta_km,
                deposito_total_l=deposito_total_l,
                consumo_l100km=consumo_l100km,
            )
        else:
            # Fallback: modo descriptivo clásico (sin datos de vehículo)
            gdf_top = filter_cheapest_stations(
                gdf_within,
                fuel_column=fuel_column,
                top_n=top_n,
                track_utm=track_utm,
                segment_km=segment_km,
            )

        if gdf_top.empty:
            st.warning(
                "No hay gasolineras con ese tipo de combustible en la zona de búsqueda. "
                "Prueba con otro combustible o amplía la distancia de búsqueda."
            )
            st.stop()

        # ---- OSRM: Filtro Fino — Distancia real por carretera ----
        progress.progress(82, text="🚗 Calculando desvíos reales (OSRM)...")
        try:
            gdf_top = enrich_stations_with_osrm(
                gdf_top,
                track_original=track,
            )
        except Exception:  # silencio total: si falla OSRM el mapa sigue funcionando
            pass

        progress.progress(90, text="🖼️ Generando mapa…")
        _, mapa_obj = generate_map(
            track_original=track,
            gdf_top_stations=gdf_top,
            fuel_column=fuel_column,
            autonomy_km=float(autonomia_km),  # F3: Zonas de peligro por autonomía
        )

        progress.progress(100, text="✅ ¡Listo!")

    except ImpossibleRouteError as exc:
        progress.empty()
        st.error(
            f"🚫 **Ruta imposible de completar:** {exc}\n\n"
            "Sugerencias: amplía el radio de búsqueda, reduce el consumo estimado "
            "o revisa que la autonomía sea mayor que la distancia hasta la primera gasolinera."
        )
        st.stop()
    except ValueError as exc:
        progress.empty()
        st.error(f"⚠️ {exc}")
        st.stop()
    except FileNotFoundError:
        progress.empty()
        st.error("No se pudo leer el archivo GPX. Asegúrate de que sea un archivo GPX válido.")
        st.stop()
    except Exception as exc:
        progress.empty()
        st.error(
            "Se produjo un error inesperado. Comprueba tu conexión a Internet "
            f"e inténtalo de nuevo.\n\n*Detalle técnico: {exc}*"
        )
        st.stop()
    finally:
        # Solo borrar si es un archivo temporal real (no la ruta de demo)
        if not _using_demo:
            tmp_path.unlink(missing_ok=True)

    # -----------------------------------------------------------------------
    # Resultados — Dashboard
    # -----------------------------------------------------------------------
    if _using_demo:
        st.info("🏙️ **Modo Demo activo** — Ruta Madrid Norte ~55 km. Sube tu propio GPX desde el panel lateral cuando quieras.")
    st.success("✅ Ruta analizada con éxito")

    # -----------------------------------------------------------------------
    # 1. KPIs principales
    # -----------------------------------------------------------------------
    precio_top_min = gdf_top[fuel_column].min()
    precio_zona_max = gdf_within[fuel_column].max()
    total_zona = len(gdf_within[gdf_within[fuel_column].notna() & (gdf_within[fuel_column] > 0)])
    total_mostradas = len(gdf_top)

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("⚽ Ruta Total", f"{ruta_km:.1f} km")
    with kpi2:
        st.metric("Mejor Precio en Ruta", f"{precio_top_min:.3f} €/L")
    with kpi3:
        coste_total_itinerario = sum(p["coste_parada_eur"] for p in itinerario)
        if itinerario:
            st.metric("🧳 Coste Total Estimado", f"{coste_total_itinerario:.2f} €")
        else:
            ahorro_vs_caro = precio_zona_max - precio_top_min
            st.metric("Ahorro vs. Más Cara", f"{ahorro_vs_caro:.3f} €/L")
    with kpi4:
        st.metric(f"Gasolineras en ±{radio_km} km", f"{total_zona}")

    st.divider()

    # =======================================================================
    # 2. ITINERARIO DE REPOSTAJE (modo prescriptivo)
    # =======================================================================
    if itinerario:
        st.subheader("🗳️ Itinerario de Repostaje Óptimo")
        st.caption(
            f"Ruta de **{ruta_km:.1f} km** con autonomía de salida de **{autonomia_actual_km:.0f} km**. "
            f"Rango útil máximo (85% depósito): **{rango_util_maximo_km:.0f} km**."
        )

        # Tarjeta de salida
        import math as _math
        combustible_actual_l = deposito_total_l * fuel_inicio_pct / 100.0
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:12px;padding:14px 18px;
                        background:linear-gradient(135deg,#eff6ff,#dbeafe);
                        border:1px solid #93c5fd;border-radius:10px;margin-bottom:8px;">
                <span style="font-size:1.8rem;">&#127968;</span>
                <div>
                    <div style="font-size:0.78rem;font-weight:700;color:#1e40af;text-transform:uppercase;letter-spacing:.05em;">Punto de Salida</div>
                    <div style="font-size:1rem;font-weight:600;color:#1e3a8a;">Km 0 — {combustible_actual_l:.1f} L disponibles &nbsp;
                        <span style="font-size:0.85rem;color:#3b82f6;">(autonoía {autonomia_actual_km:.0f} km)</span>
                    </div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        for parada in itinerario:
            n = parada["numero"]
            km = parada["km_ruta"]
            nombre = parada["nombre"]
            municipio = parada["municipio"]
            precio = parada["precio_eur_l"]
            litros = parada["litros_repostados"]
            coste = parada["coste_parada_eur"]
            osrm_dist = parada["osrm_distance_km"]
            osrm_dur = parada["osrm_duration_min"]

            desvio_html = ""
            if not _math.isnan(osrm_dist) and not _math.isnan(osrm_dur):
                desvio_html = (
                    f'<span style="font-size:0.82rem;color:#059669;margin-left:8px;">'  
                    f'🚗 {osrm_dist:.1f} km desvío ({osrm_dur:.0f} min)</span>'
                )

            st.markdown(
                f"""
                <div style="display:flex;align-items:flex-start;gap:0;margin-bottom:4px;">
                    <div style="display:flex;flex-direction:column;align-items:center;margin-right:12px;">
                        <div style="
                            background:#2563eb;color:white;font-weight:700;font-size:0.9rem;
                            width:32px;height:32px;border-radius:50%;display:flex;
                            align-items:center;justify-content:center;flex-shrink:0;
                        ">{n}</div>
                        <div style="width:2px;background:#bfdbfe;flex:1;min-height:20px;"></div>
                    </div>
                    <div style="
                        flex:1;padding:12px 16px;margin-bottom:6px;
                        background:white;border:1px solid #e2e8f0;border-radius:10px;
                        box-shadow:0 1px 3px rgba(0,0,0,0.04);
                    ">
                        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;">
                            <div>
                                <span style="font-weight:700;color:#0f172a;">{nombre}</span>
                                <span style="color:#64748b;font-size:0.9rem;"> — {municipio}</span>
                                {desvio_html}
                            </div>
                            <span style="background:#dcfce7;color:#166534;font-weight:700;
                                         border-radius:6px;padding:2px 10px;font-size:0.92rem;">
                                {precio:.3f} €/L
                            </span>
                        </div>
                        <div style="margin-top:6px;display:flex;gap:16px;flex-wrap:wrap;">
                            <span style="font-size:0.82rem;color:#475569;">
                                <b>📍</b> Km {km:.1f}
                            </span>
                            <span style="font-size:0.82rem;color:#475569;">
                                <b>⚽</b> {litros:.1f} L repostados
                            </span>
                            <span style="font-size:0.82rem;color:#2563eb;font-weight:600;">
                                <b>💶</b> {coste:.2f} €
                            </span>
                        </div>
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )

        # Tarjeta de llegada
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:12px;padding:14px 18px;
                        background:linear-gradient(135deg,#f0fdf4,#dcfce7);
                        border:1px solid #86efac;border-radius:10px;margin-top:4px;">
                <span style="font-size:1.8rem;">🏁</span>
                <div>
                    <div style="font-size:0.78rem;font-weight:700;color:#166534;text-transform:uppercase;letter-spacing:.05em;">Destino</div>
                    <div style="font-size:1rem;font-weight:600;color:#14532d;">
                        Km {ruta_km:.1f} — Coste total estimado:
                        <span style="font-size:1.15rem;color:#16a34a;font-weight:800;">{coste_total_itinerario:.2f} €</span>
                    </div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

    else:
        # Modo descriptivo (sin datos de vehículo): tabla clásica
        st.subheader("🏆 Ranking de Gasolineras en Ruta")
        st.caption("Configura los datos de tu vehículo para obtener el itinerario óptimo personalizado.")
        _COLS = {
            "km_ruta": "Km en Ruta",
            "Rótulo": "Rótulo / Marca",
            "Municipio": "Municipio",
            "Provincia": "Provincia",
            fuel_column: f"Precio {combustible_elegido} (€/L)",
            "osrm_distance_km": "Desvío Real (km)",
            "Horario": "Horario",
        }
        _col_map = {c: e for c, e in _COLS.items() if c in gdf_top.columns}
        _df = gdf_top[list(_col_map.keys())].copy().rename(columns=_col_map)
        if "Km en Ruta" in _df.columns:
            _df["Km en Ruta"] = _df["Km en Ruta"].apply(lambda x: f"{x:.1f}")
        if "Desvío Real (km)" in _df.columns:
            _df["Desvío Real (km)"] = _df["Desvío Real (km)"].apply(
                lambda x: f"{x:.1f}" if x == x else "—"
            )
        _df.index = [""] * len(_df)
        st.dataframe(_df, use_container_width=True, hide_index=True)

    st.divider()

    header_map = "🗺️ Mapa Interactivo de la Ruta"
    if autonomia_km > 0:
        header_map += f"  ·  ⚠️ Zonas de riesgo con {autonomia_km} km de autonomía"
    st.subheader(header_map)
    if autonomia_km > 0:
        st.caption(
            "Los segmentos **rojos discontinuos** indican tramos donde no hay gasolinera "
            f"dentro de tus {autonomia_km} km de autonomía. Haz clic en los marcadores para ver detalles."
        )
    else:
        st.caption("Haz clic en los marcadores para ver la información de la gasolinera.")

    # Mapa — anti scroll-trap: el usuario puede desactivar la interactividad
    # para que el scroll de la página no quede "atrapado" dentro del iframe
    # (problema frecuente en móvil con mapas Leaflet/Folium).
    map_active = st.checkbox(
        "🖱️ Activar interacción con el mapa (zoom / arrastrar)",
        value=True,
        help=(
            "En móvil, desactívalo para poder hacer scroll en la página "
            "sin que el mapa capture el gesto."
        ),
    )
    map_height = 580 if map_active else 340

    st_folium(
        mapa_obj, width="100%",
        height=map_height,
        returned_objects=[],
    )
    if not map_active:
        st.caption("ℹ️ Activa la interacción arriba para hacer zoom y desplazarte por el mapa.")

    st.markdown("---")

    # 4. Tabla de resultados
    st.subheader("🏆 Ranking de Gasolineras")

    COLS = {
        "km_ruta":            "Km en Ruta",
        "Rotulo":             "Rótulo / Marca",
        "Municipio":          "Municipio",
        "Provincia":          "Provincia",
        "Direccion":          "Dirección",
        fuel_column:          f"Precio {combustible_elegido} (€/L)",
        "osrm_distance_km":   "Desvío Real (km)",
        "osrm_duration_min":  "Desvío (min)",
        "Horario":            "Horario",
    }

    col_map = {}
    for campo, etiqueta in COLS.items():
        if campo in gdf_top.columns:
            col_map[campo] = etiqueta
        elif campo.replace("o", "ó") in gdf_top.columns:
            col_map[campo.replace("o", "ó")] = etiqueta
        elif campo == "Direccion" and "Dirección" in gdf_top.columns:
            col_map["Dirección"] = etiqueta

    df_show = gdf_top[list(col_map.keys())].copy()
    df_show = df_show.rename(columns=col_map)

    if "Km en Ruta" in df_show.columns:
        df_show["Km en Ruta"] = df_show["Km en Ruta"].apply(lambda x: f"{x:.1f}")
    if "Desvío Real (km)" in df_show.columns:
        df_show["Desvío Real (km)"] = df_show["Desvío Real (km)"].apply(
            lambda x: f"{x:.1f}" if x == x else "—"   # NaN → guion
        )
    if "Desvío (min)" in df_show.columns:
        df_show["Desvío (min)"] = df_show["Desvío (min)"].apply(
            lambda x: f"{x:.0f}" if x == x else "—"
        )

    df_show.index = [""] * len(df_show)
    st.dataframe(df_show, use_container_width=True, hide_index=True)

else:
    # -----------------------------------------------------------------------
    # PANTALLA INICIAL — Estado vacío con CTA activo (Zero-Friction Onboarding)
    # -----------------------------------------------------------------------
    st.markdown(
        """
        <div class="welcome-container">
            <div class="welcome-icon">🏍️⛽</div>
            <div class="welcome-title">Optimizador de Repostaje para Moteros</div>
            <div class="welcome-text">
                Sube el GPX de tu ruta, indica tu combustible y el depósito de tu moto.
                Encontramos las gasolineras más baratas de España <strong>en tiempo real</strong>
                cruzando datos geográficos con la API oficial del MITECO.
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
            "🏍️  Probar con ruta de Demo (Madrid Norte)",
            use_container_width=True,
            help="Carga automáticamente una ruta de ~55 km alrededor de Madrid para que veas la app en funcionamiento sin necesidad de subir un GPX.",
        ):
            # Activar modo demo y relanzar la app para que el pipeline lo detecte
            st.session_state["demo_mode"] = True
            st.rerun()
