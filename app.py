"""
app.py
======
Interfaz web local (Streamlit) para el Optimizador de Gasolineras en Ruta.

Cómo ejecutar:
    streamlit run app.py
"""

import tempfile
from pathlib import Path

import streamlit as st
from streamlit_folium import st_folium

import geopandas as gpd

from gasolineras_ruta import (
    fetch_gasolineras,
    load_gpx_track,
    simplify_track,
    build_route_buffer,
    build_stations_geodataframe,
    spatial_join_within_buffer,
    filter_cheapest_stations,
    generate_map,
    CRS_WGS84,
    CRS_UTM30N,
)

# Caché de 30 minutos: evita repetir la llamada a la API del MITECO
# en cada interacción del usuario con la interfaz.
@st.cache_data(ttl=1800, show_spinner=False)
def cached_fetch_gasolineras() -> object:
    return fetch_gasolineras()

# ---------------------------------------------------------------------------
# Configuración de la página
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Gasolineras en Ruta",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# CSS personalizado: diseño profesional tipo dashboard
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Barra lateral */
    .css-1d391kg { /* stSidebar */
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Títulos de sección en sidebar */
    .sidebar-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 1.5rem;
        margin-bottom: 0.5rem;
    }

    /* Tarjetas de métricas (KPIs) */
    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0f172a;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 500;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }

    /* Botón principal (sidebar) */
    div.stButton > button {
        background: #2563eb !important;
        color: white !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        height: 2.75rem !important;
        border: none !important;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2), 0 2px 4px -1px rgba(37, 99, 235, 0.1) !important;
        transition: all 0.2s ease-in-out !important;
        margin-top: 1rem;
    }
    div.stButton > button:hover {
        background: #1d4ed8 !important;
        transform: translateY(-1px);
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.3), 0 4px 6px -2px rgba(37, 99, 235, 0.15) !important;
    }

    /* Estado inicial / Guía visual */
    .welcome-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 4rem 2rem;
        text-align: center;
        background: white;
        border: 1px dashed #cbd5e1;
        border-radius: 12px;
        margin-top: 2rem;
    }
    .welcome-icon {
        font-size: 4rem;
        margin-bottom: 1rem;
    }
    .welcome-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 0.5rem;
    }
    .welcome-text {
        font-size: 1rem;
        color: #64748b;
        max-width: 600px;
        line-height: 1.6;
    }
    
    /* DataFrames */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Panel Principal (Cabecera)
# ---------------------------------------------------------------------------
st.title("⛽ Gasolineras en Ruta Dashboard")
st.markdown("Encuentra las estaciones de servicio más económicas a lo largo de tu viaje.")

# ---------------------------------------------------------------------------
# Tipos de combustible — etiquetas en lenguaje natural
# ---------------------------------------------------------------------------
COMBUSTIBLES = {
    "Gasolina 95":                      "Precio Gasolina 95 E5",
    "Gasolina 95 Premium":              "Precio Gasolina 95 E5 Premium",
    "Gasolina 98":                      "Precio Gasolina 98 E5",
    "Diésel (Gasoil A)":               "Precio Gasoleo A",
    "Diésel Premium":                   "Precio Gasoleo Premium",
    "GLP / Autogas":                    "Precio Gases licuados del petroleo",
    "Gas Natural Comprimido (GNC)":     "Precio Gas Natural Comprimido",
    "Gas Natural Licuado (GNL)":        "Precio Gas Natural Licuado",
    "Gasoil B (agrícola/industrial)":   "Precio Gasoleo B",
    "Gasolina 95 E10":                  "Precio Gasolina 95 E10",
    "Gasolina 98 E10":                  "Precio Gasolina 98 E10",
    "Hidrógeno":                        "Precio Hidrogeno",
}

# ---------------------------------------------------------------------------
# BARRA LATERAL (SIDEBAR) - Controles de Configuración
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3035/3035041.png", width=60) # Icono decorativo opcional
    st.markdown("## ⚙️ Configuración del Viaje")
    st.markdown("---")
    
    # Paso 1: Archivo GPX
    st.markdown('<p class="sidebar-title">1. ARCHIVO DE RUTA (.GPX)</p>', unsafe_allow_html=True)
    gpx_file = st.file_uploader(
        "Sube tu archivo .gpx:",
        type=["gpx"],
        label_visibility="collapsed",
    )
    with st.expander("¿Cómo obtengo mi archivo GPX?"):
        st.markdown(
            """
            - **Wikiloc**: ruta → Descargar → *.gpx*
            - **Komoot**: ruta → ⋯ → *Exportar como GPX*
            - **Garmin**: actividad → *Exportar GPX*
            - **Strava**: actividad → ⋯ → *Exportar GPX*
            - **Maps**: usa mapstogpx.com
            """
        )

    # Paso 2: Combustible
    st.markdown('<p class="sidebar-title">2. TIPO DE COMBUSTIBLE</p>', unsafe_allow_html=True)
    combustible_elegido = st.selectbox(
        "Selecciona el combustible:",
        options=list(COMBUSTIBLES.keys()),
        label_visibility="collapsed",
    )
    fuel_column = COMBUSTIBLES[combustible_elegido]

    # Opciones Avanzadas
    st.markdown('<p class="sidebar-title">3. FILTROS AVANZADOS</p>', unsafe_allow_html=True)
    with st.expander("Ajustar parámetros de búsqueda", expanded=False):
        radio_km = st.slider(
            "Distancia máxima a la ruta (km)",
            min_value=1,
            max_value=15,
            value=5,
            step=1,
            help="Distancia máxima lateral a la ruta para buscar gasolineras.",
        )
        top_n = st.slider(
            "Gasolineras a mostrar",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
        )
        st.markdown("---")
        buscar_tramos = st.checkbox("Asegurar repostaje cada X km", help="Ideal para vehículos con poca autonomía (ej. motos)")
        if buscar_tramos:
            segment_km = st.slider(
                "Distancia de seguridad (km)",
                min_value=10,
                max_value=300,
                value=50,
                step=10,
            )
        else:
            segment_km = 0.0

    buffer_m = radio_km * 1000  # convertir a metros

    # Botón Búsqueda
    st.markdown("<br>", unsafe_allow_html=True)
    run_btn = st.button("🔍 Iniciar Búsqueda", use_container_width=True)
    
    st.markdown("---")
    st.caption("Los datos se obtienen en tiempo real de la API del Ministerio de Transición Ecológica (MITECO).")

# ---------------------------------------------------------------------------
# Pipeline de cálculo
# ---------------------------------------------------------------------------
if run_btn:
    if gpx_file is None:
        st.error("📂 Primero sube tu archivo GPX en el Paso 1.")
        st.stop()

    # Guardar GPX en fichero temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gpx") as tmp:
        tmp.write(gpx_file.read())
        tmp_path = Path(tmp.name)

    progress = st.progress(0, text="Iniciando búsqueda…")

    try:
        progress.progress(10, text="⏬ Descargando precios en tiempo real…")
        df_gas = cached_fetch_gasolineras()

        progress.progress(30, text="🗺️ Leyendo tu ruta GPX…")
        track = load_gpx_track(tmp_path)

        progress.progress(50, text="✂️ Procesando la ruta…")
        track_simp = simplify_track(track, tolerance_deg=0.0005)

        progress.progress(65, text="📡 Buscando gasolineras cercanas…")
        gdf_buffer = build_route_buffer(track_simp, buffer_meters=buffer_m)
        gdf_utm    = build_stations_geodataframe(df_gas)
        gdf_within = spatial_join_within_buffer(gdf_utm, gdf_buffer)

        progress.progress(82, text="💰 Calculando las más baratas…")

        if fuel_column not in gdf_within.columns or gdf_within[fuel_column].isna().all():
            st.warning(
                f"No encontramos gasolineras con precio de **{combustible_elegido}** "
                f"en un radio de {radio_km} km. "
                f"Prueba a ampliar la distancia en las opciones avanzadas."
            )
            st.stop()

        # Extraer track en UTM para proyectar gasolineras y encontrar el km de ruta
        gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simp], crs=CRS_WGS84).to_crs(CRS_UTM30N)
        track_utm = gdf_track_utm.geometry.iloc[0]

        gdf_top = filter_cheapest_stations(
            gdf_within, 
            fuel_column=fuel_column, 
            top_n=top_n,
            track_utm=track_utm,
            segment_km=segment_km
        )

        if gdf_top.empty:
            st.warning(
                "No hay gasolineras con ese tipo de combustible en la zona de búsqueda. "
                "Prueba con otro combustible o amplía la distancia de búsqueda."
            )
            st.stop()

        progress.progress(94, text="🖼️ Generando mapa…")
        output_html = Path(tempfile.gettempdir()) / "mapa_gasolineras.html"
        _, mapa_obj = generate_map(
            track_original=track,
            gdf_top_stations=gdf_top,
            fuel_column=fuel_column,
            output_path=output_html,
        )

        progress.progress(100, text="✅ ¡Listo!")

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
        tmp_path.unlink(missing_ok=True)

    # -----------------------------------------------------------------------
    # Resultados - Layout Dashboard
    # -----------------------------------------------------------------------
    st.success("✅ Ruta analizada con éxito")
    
    # 1. KPIs principales en la parte superior
    col1, col2, col3, col4 = st.columns(4)
    
    precio_min = str(gdf_top[fuel_column].min()).replace('.', ',') + " €"
    precio_max_zona = str(gdf_within[fuel_column].max()).replace('.', ',') + " €"
    total_zona = len(gdf_within)
    total_mostradas = len(gdf_top)
    
    with col1:
        st.metric("Mejor Precio Sugerido", precio_min, None)
    with col2:
        st.metric(f"Precio Max. a {radio_km}km", precio_max_zona, None)
    with col3:
        st.metric("Top Optimizadas", f"{total_mostradas} Estaciones", None)
    with col4:
        st.metric("Total en la Zona", f"{total_zona} Est.", None)
        
    st.divider()

    # 2. Área principal: Mapa a la izquierda, Tabla debajo o en pestañas/columnas
    # Para aprovechar mejor el ancho ("wide"), pondremos el mapa primero muy grande.
    
    st.subheader("🗺️ Mapa Interactivo de la Ruta")
    st.caption("Haz clic en los marcadores para ver la información de la gasolinera.")
    
    # Renderizamos el mapa folium con st_folium ajustado al ancho
    st_folium(mapa_obj, width="100%", height=600, returned_objects=[])
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Botón de descarga
    with open(output_html, "rb") as f:
        html_bytes = f.read()
    st.download_button(
        label="⬇️ Descargar Mapa Interactivo (Versión Offline HTML)",
        data=html_bytes,
        file_name="mapa_gasolineras_ruta.html",
        mime="text/html",
        use_container_width=False,
    )

    st.markdown("---")

    # 3. Tabla de Resultados limpia y profesional
    st.subheader("🏆 Ranking de Gasolineras (Detalle)")
    
    COLS = {
        "km_ruta":     "Km Aprox.",
        "Rotulo":      "Rótulo / Marca",
        "Municipio":   "Municipio",
        "Provincia":   "Provincia",
        "Direccion":   "Dirección",
        fuel_column:   f"Precio {combustible_elegido} (€/L)",
        "Horario":     "Horario",
    }
    
    # Búsqueda de columnas con posibles errores de tildes de la API MITECO
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
    
    if "Km Aprox." in df_show.columns:
        df_show["Km Aprox."] = df_show["Km Aprox."].apply(lambda x: f"{x:.1f}")
        
    # Eliminar el índice visual en Streamlit para un aspecto más limpio
    df_show.index = [""] * len(df_show)
    
    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True
    )

else:
    # -----------------------------------------------------------------------
    # ESTADO INICIAL (Cuando no se ha lanzado la búsqueda)
    # -----------------------------------------------------------------------
    st.markdown(
        """
        <div class="welcome-container">
            <div class="welcome-icon">🗺️⛽</div>
            <div class="welcome-title">Bienvenido al Optimizador de Repostaje en Ruta</div>
            <div class="welcome-text">
                Planifica tu viaje de manera inteligente. Configura tu ruta en el panel lateral a la izquierda, 
                selecciona tu combustible, y nosotros buscaremos las estaciones de servicio más económicas de 
                España directamente cruzando datos geográficos y la API oficial del MITECO en tiempo real.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
