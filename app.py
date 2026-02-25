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
# CSS personalizado: fuente moderna, colores más cálidos, paso-a-paso
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Tarjetas de paso */
    .step-card {
        background: #f8faff;
        border: 1.5px solid #dce8ff;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 18px;
    }
    .step-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1a3c6e;
        margin-bottom: 4px;
    }
    .step-num {
        display: inline-block;
        background: #1a3c6e;
        color: white;
        border-radius: 50%;
        width: 26px;
        height: 26px;
        text-align: center;
        line-height: 26px;
        font-size: 0.85rem;
        font-weight: 700;
        margin-right: 8px;
    }
    .result-box {
        background: #edfff4;
        border: 1.5px solid #6ee7a0;
        border-radius: 12px;
        padding: 16px 20px;
        margin-bottom: 18px;
        font-size: 1rem;
    }
    .stButton > button {
        background: #1a3c6e !important;
        color: white !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
        height: 3rem !important;
        border: none !important;
    }
    .stButton > button:hover {
        background: #2a5ca8 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Cabecera
# ---------------------------------------------------------------------------
st.markdown("## ⛽ Gasolineras baratas en tu ruta")
st.markdown(
    "Descubre las gasolineras **más económicas** a lo largo de tu recorrido "
    "con precios actualizados del Ministerio de Industria."
)
st.divider()

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
# Paso 1 — Archivo GPX
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="step-card">'
    '<p class="step-title"><span class="step-num">1</span>Sube el archivo de tu ruta</p>',
    unsafe_allow_html=True,
)
gpx_file = st.file_uploader(
    "Elige un archivo .gpx",
    type=["gpx"],
    label_visibility="collapsed",
    help=(
        "Exporta tu ruta desde Wikiloc, Komoot, Garmin Connect o Strava "
        "en formato GPX y súbela aquí."
    ),
)
with st.expander("¿Cómo obtengo mi archivo GPX?"):
    st.markdown(
        """
        - **Wikiloc**: abre la ruta → *Descargar* → *.gpx*
        - **Komoot**: abre la ruta → ⋯ → *Exportar como GPX*
        - **Garmin Connect**: Actividades → selecciona la salida → *Exportar GPX*
        - **Strava**: actividad → ⋯ → *Exportar GPX*
        - **Google Maps**: usa [mapstogpx.com](https://mapstogpx.com) para convertir
        """
    )
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Paso 2 — Combustible
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="step-card">'
    '<p class="step-title"><span class="step-num">2</span>Elige tu combustible</p>',
    unsafe_allow_html=True,
)
combustible_elegido = st.selectbox(
    "Tipo de combustible",
    options=list(COMBUSTIBLES.keys()),
    label_visibility="collapsed",
)
fuel_column = COMBUSTIBLES[combustible_elegido]
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Opciones avanzadas (colapsadas por defecto)
# ---------------------------------------------------------------------------
with st.expander("⚙️ Opciones avanzadas"):
    col_a, col_b = st.columns(2)
    with col_a:
        radio_km = st.slider(
            "¿Hasta qué distancia de la ruta buscamos?",
            min_value=1,
            max_value=15,
            value=5,
            step=1,
            format="%d km",
            help="Distancia máxima lateral a la ruta en la que se buscan gasolineras.",
        )
    with col_b:
        top_n = st.slider(
            "¿Cuántas gasolineras quieres ver?",
            min_value=1,
            max_value=15,
            value=5,
            step=1,
        )
    
    st.markdown("---")
    buscar_tramos = st.checkbox("Buscar gasolinera sí o sí cada X km (vehículos de poca autonomía)")
    if buscar_tramos:
        segment_km = st.slider(
            "¿Cada cuántos kilómetros necesitas asegurar una gasolinera?",
            min_value=10,
            max_value=300,
            value=50,
            step=10,
        )
    else:
        segment_km = 0.0

buffer_m = radio_km * 1000  # convertir a metros para el motor GIS

# ---------------------------------------------------------------------------
# Paso 3 — Botón de búsqueda
# ---------------------------------------------------------------------------
st.markdown(
    '<div class="step-card">'
    '<p class="step-title"><span class="step-num">3</span>Busca las gasolineras más baratas</p>',
    unsafe_allow_html=True,
)
run_btn = st.button("🔍  Buscar gasolineras", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

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
    # Resultados
    # -----------------------------------------------------------------------
    st.markdown(
        f'<div class="result-box">'
        f'✅ Encontramos <strong>{len(gdf_within)}</strong> gasolineras en un radio de '
        f'{radio_km} km alrededor de tu ruta. '
        f'Te mostramos las <strong>{len(gdf_top)}</strong> con <strong>{combustible_elegido}</strong> más barato.'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Tabla de resultados limpia
    st.subheader("🏆 Ranking de gasolineras")
    COLS = {
        "km_ruta":     "Km aprox.",
        "Rotulo":      "Nombre",
        "Municipio":   "Municipio",
        "Provincia":   "Provincia",
        "Direccion":   "Dirección",
        fuel_column:   f"Precio {combustible_elegido} (€/L)",
        "Horario":     "Horario",
    }
    # Algunos nombres de columna en el MITECO usan tildes; buscamos ambas variantes
    col_map = {}
    for campo, etiqueta in COLS.items():
        if campo in gdf_top.columns:
            col_map[campo] = etiqueta
        elif campo.replace("o", "ó") in gdf_top.columns:  # Rótulo, Dirección…
            col_map[campo.replace("o", "ó")] = etiqueta

    df_show = gdf_top[list(col_map.keys())].copy()
    df_show = df_show.rename(columns=col_map)
    
    if "Km aprox." in df_show.columns:
        df_show["Km aprox."] = df_show["Km aprox."].apply(lambda x: f"{x:.1f}")
        
    df_show.index = range(1, len(df_show) + 1)
    st.dataframe(df_show, use_container_width=True)

    # Mapa
    st.subheader("🗺️ Mapa interactivo")
    st.caption("Haz clic en cada círculo para ver detalles de la gasolinera.")
    st_folium(mapa_obj, width="100%", height=580, returned_objects=[])

    # Botón de descarga del mapa HTML
    with open(output_html, "rb") as f:
        html_bytes = f.read()
    st.download_button(
        label="⬇️ Descargar mapa (abre en cualquier navegador sin internet)",
        data=html_bytes,
        file_name="mapa_gasolineras.html",
        mime="text/html",
        use_container_width=True,
    )

else:
    # Estado inicial — guía visual
    st.info(
        "👆 Completa los 3 pasos de arriba y pulsa **Buscar gasolineras** para ver el resultado.",
        icon="ℹ️",
    )
    with st.expander("¿Para qué sirve esta herramienta?"):
        st.markdown(
            """
            Esta aplicación te ayuda a **ahorrar en combustible** cuando planificas un viaje en coche.

            1. Sube la ruta de tu viaje en formato **.gpx**
            2. Elige qué tipo de **combustible** usa tu vehículo
            3. La app busca en toda la ruta las gasolineras más baratas y las muestra en un mapa

            Los precios se descargan en **tiempo real** desde el Ministerio de Industria de España 
            (API MITECO), por lo que siempre son actuales.
            """
        )
# Trigger deployment clean
