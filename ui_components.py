import streamlit as st


def render_welcome_screen(is_mobile: bool = False):
    """Renders the welcome screen. Uses a 2-col layout on PC and 1-col on mobile."""
    if is_mobile:
        # Mobile: compact single-column layout
        st.markdown(
            "<div style='text-align:center; padding: 1rem 0;'>"
            "<span style='font-size:3rem;'>🛣️⛽</span></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<h2 style='text-align:center; margin-top:0;'>Planificador de Repostaje en Ruta</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "Indica tu ruta y combustible. Encontramos las **gasolineras más baratas de España** "
            "cruzando tu trayecto con datos en tiempo real del MITECO."
        )
        # Feature pills
        c1, c2, c3 = st.columns(3)
        c1.markdown("<div style='text-align:center;font-size:0.8rem'>📍 Tiempo real</div>", unsafe_allow_html=True)
        c2.markdown("<div style='text-align:center;font-size:0.8rem'>🗺️ GPX + Texto</div>", unsafe_allow_html=True)
        c3.markdown("<div style='text-align:center;font-size:0.8rem'>⛽ 12.000 Est.</div>", unsafe_allow_html=True)
    else:
        # PC: 2-column heroes layout
        col_left, col_right = st.columns([3, 2], gap="large")
        with col_left:
            st.markdown(
                "<h1 style='font-size:2.8rem; margin-bottom:0.2rem;'>🛣️⛽ Planificador Inteligente de Repostaje</h1>",
                unsafe_allow_html=True,
            )
            st.markdown(
                "<p style='font-size:1.1rem; color: gray; margin-bottom:1.5rem;'>"
                "Encuentra las gasolineras más baratas de España a lo largo de tu ruta, "
                "con datos en <strong>tiempo real del MITECO</strong> y análisis geoespacial de precisión."
                "</p>",
                unsafe_allow_html=True,
            )
            # Feature pills
            pill_cols = st.columns(3)
            pills = [
                ("📍", "Tiempo real", "Precios actualizados cada 30 min del MITECO"),
                ("🗺️", "GPX + Texto", "Sube tu ruta o escribe origen y destino"),
                ("⛽", "12.000 Estaciones", "Toda España indexada con R-Tree"),
            ]
            for col, (icon, title, desc) in zip(pill_cols, pills):
                with col:
                    with st.container(border=True):
                        st.markdown(f"<div style='text-align:center; font-size:1.6rem;'>{icon}</div>", unsafe_allow_html=True)
                        st.markdown(f"<strong style='display:block; text-align:center;'>{title}</strong>", unsafe_allow_html=True)
                        st.caption(desc)
            st.markdown("")
            st.info(
                "🛃 **¿Cómo funciona?**\n"
                "1. **Configura tu ruta** — escribe origen y destino, o sube un `.gpx`.\n"
                "2. **Elige tu combustible** y, opcionalmente, la autonomía de tu vehículo.\n"
                "3. **Haz clic en Iniciar Búsqueda** — el motor geoespacial calcula en segundos.\n"
                "4. **Revisa el mapa y la tabla** — añade paradas a tu plan y expórtalo a Maps o GPX."
            )
        with col_right:
            st.markdown(
                "<div style='"
                "background: var(--secondary-background-color);"
                "border-radius: 16px;"
                "padding: 2rem;"
                "text-align: center;"
                "min-height: 340px;"
                "display: flex; flex-direction: column; justify-content: center; align-items: center;"
                "box-shadow: 0 4px 16px rgba(128,128,128,0.1);"
                "border: 1px solid var(--primary-color);"
                "'>"
                "<span style='font-size:5rem; display:block; margin-bottom:1rem;'>⛽</span>"
                "<span style='color: var(--primary-color); font-size:1.3rem; font-weight:700; letter-spacing:0.05em;'>GASOLINERAS EN RUTA</span><br>"
                "<span style='color: var(--text-color); opacity: 0.8; font-size:0.9rem; margin-top:0.5rem; display:block;'>"
                "Optimizador Geoespacial de Repostaje</span>"
                "<div style='margin-top:1.5rem; display:flex; gap:0.5rem; justify-content:center; flex-wrap:wrap;'>"
                "<span style='border: 1px solid var(--primary-color); color: var(--primary-color); padding:0.3rem 0.8rem; border-radius:999px; font-size:0.8rem;'>🇳🇵 MITECO</span>"
                "<span style='border: 1px solid var(--primary-color); color: var(--primary-color); padding:0.3rem 0.8rem; border-radius:999px; font-size:0.8rem;'>🇧🇂 OSRM</span>"
                "<span style='border: 1px solid var(--primary-color); color: var(--primary-color); padding:0.3rem 0.8rem; border-radius:999px; font-size:0.8rem;'>🗺️ GeoPandas</span>"
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )

def render_config_summary(pipeline_results: dict, combustible: str, radio_km: int, top_n: int, origen_txt: str = "", destino_txt: str = "", using_gpx: bool = False, using_demo: bool = False):
    """Shows an active-config summary badge in the sidebar after the pipeline has run."""
    if using_demo:
        ruta_str = "🧭 Demo: Sierra de Gredos"
    elif using_gpx:
        ruta_str = "📁 Archivo GPX"
    elif origen_txt and destino_txt:
        ruta_str = f"📑 {origen_txt.strip().title()} → {destino_txt.strip().title()}"
    else:
        ruta_str = "📑 Ruta personalizada"

    total = pipeline_results.get("gdf_within_count", 0)
    st.markdown(
        f"""
        <div style='
            background: rgba(255,127,0,0.08);
            border-left: 3px solid #FF8C00;
            padding: 0.6rem 0.8rem;
            border-radius: 0 8px 8px 0;
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
        '>
        <strong style='color:#FF8C00;'>⚙️ Búsqueda Activa</strong><br>
        {ruta_str}<br>
        ⛽ {combustible} · 📍 ±{radio_km} km · 🏆 Top {top_n}<br>
        <span style='color: gray; font-size:0.8rem;'>{total} estaciones en zona</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_metric_cards(precio_top_min: float, ahorro_vs_caro: float, total_mostradas: int, total_zona: int, radio_km: int, fuel_column: str):
    """Renders the main KPI metrics."""
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Mejor Precio Encontrado", f"{precio_top_min:.3f} €/L")
    with col2:
        st.metric(
            "Ahorro vs. Más Cara de la Zona",
            f"{ahorro_vs_caro:.3f} €/L",
            delta=None,
        )
    with col3:
        st.metric("Estaciones Sugeridas", f"{total_mostradas}")
    with col4:
        st.metric(f"Total en ±{radio_km} km", f"{total_zona} Est.")

def render_station_cards(df_show, precio_col_label: str, station_coords: list, mis_paradas: list):
    """
    Mejora 2: Vista de tarjetas táctiles para móvil.
    Renderiza los resultados como tarjetas verticales en lugar de st.dataframe.
    Devuelve tupla (idx, coords_x, coords_y, row) si el usuario pulsa Añadir, o None.
    """
    import pandas as pd

    MAX_MOBILE_CARDS = 10
    df_cards = df_show.head(MAX_MOBILE_CARDS).copy()
    if len(df_show) > MAX_MOBILE_CARDS:
        st.caption(f"Mostrando las {MAX_MOBILE_CARDS} más económicas. En PC puedes ver el ranking completo.")

    parada_to_add = None

    for i, (_, row) in enumerate(df_cards.iterrows()):
        marca = row.get("Marca", "Estación")
        precio_val = row.get(precio_col_label)
        km_val = row.get("Km en Ruta")
        desvio_val = row.get("Desvío (min)", "—")
        horario = str(row.get("Horario", ""))
        maps_url = str(row.get("_maps_url", ""))

        precio_str = f"{precio_val:.3f} €/L" if pd.notna(precio_val) else "—"
        km_str = f"{float(km_val):.1f} km" if pd.notna(km_val) else "—"
        ahorro_val = row.get("Ahorro (€/L)")
        ahorro_str = f"-{ahorro_val:.3f} €/L" if pd.notna(ahorro_val) and ahorro_val > 0 else ""

        coords_y, coords_x = station_coords[i] if i < len(station_coords) else (None, None)
        ya_en_plan = any(
            p.get("_geom_x") == coords_x and p.get("_geom_y") == coords_y
            for p in mis_paradas
        )

        with st.container(border=True):
            col_info, col_precio = st.columns([3, 2])
            with col_info:
                st.markdown(f"**⛽ {marca}**")
                st.caption(f"📍 {km_str} en ruta")
                if desvio_val and desvio_val != "—":
                    st.caption(f"🔀 Desvío: {desvio_val}")
                if horario and horario != "nan":
                    st.caption(f"🕐 {horario[:40]}{'…' if len(horario) > 40 else ''}")
            with col_precio:
                st.markdown(
                    f"<div style='text-align:right; font-size:1.25rem; font-weight:700; color:#FF8C00;'>{precio_str}</div>"
                    + (f"<div style='text-align:right; font-size:0.8rem; color:#4CAF50;'>{ahorro_str}</div>" if ahorro_str else ""),
                    unsafe_allow_html=True,
                )
            btn_cols = st.columns([1, 1])
            with btn_cols[0]:
                if maps_url and maps_url != "nan":
                    st.link_button("🗺️ Maps", url=maps_url, use_container_width=True)
            with btn_cols[1]:
                if ya_en_plan:
                    st.button("✅ En plan", key=f"card_plan_{i}", disabled=True, use_container_width=True)
                else:
                    if st.button("➕ Añadir", key=f"card_add_{i}", use_container_width=True, type="primary"):
                        parada_to_add = (i, coords_x, coords_y, row)

    return parada_to_add

def render_autonomy_radar_ui(tramos: list[dict], route_total_km: float, autonomia_km: float):
    """Renders the autonomy radar UI fully with native Streamlit components."""
    n_crit = sum(1 for t in tramos if t["nivel"] == "critico")
    n_warn = sum(1 for t in tramos if t["nivel"] == "atencion")
    n_safe = sum(1 for t in tramos if t["nivel"] == "seguro")
    max_gap = max((t["gap_km"] for t in tramos), default=0.0)

    if n_crit > 0 and autonomia_km > 0:
        with st.container(border=True):
            st.error(f"🔴 **Ruta con {n_crit} tramo(s) CRÍTICO(S)**\n\nEl tramo más largo sin gasolinera es de **{max_gap:.1f} km**. Tu autonomía configurada es de **{autonomia_km} km**. Revisa los tramos marcados en rojo antes de salir.")
    elif n_warn > 0:
        with st.container(border=True):
            st.warning(f"🟡 **Ruta con {n_warn} tramo(s) de ATENCIÓN**\n\nNingún tramo supera tu autonomía ({autonomia_km} km), pero hay segmentos de más del 80%. Procura no llegar a esas zonas con el depósito bajo.")
    elif autonomia_km > 0:
        with st.container(border=True):
            st.success(f"🟢 **Ruta completamente SEGURA**\n\nTodos los tramos entre gasolineras están por debajo de tu autonomía ({autonomia_km} km). ¡Puedes salir tranquilo!")
    else:
        with st.container(border=True):
            st.info(f"ℹ️ **Tramo más largo sin gasolinera:** {max_gap:.1f} km\n\nConfigura tu autonomía en el sidebar para activar las alertas.")

    # Chips de resumen rápido
    cols = st.columns(5)
    cols[0].markdown(f"🟢 **{n_safe} seguros**")
    if n_warn: cols[1].markdown(f"🟡 **{n_warn} atención**")
    if n_crit: cols[2].markdown(f"🔴 **{n_crit} críticos**")
    cols[3].markdown(f"🛣️ **Total: {route_total_km:.1f} km**")
    if autonomia_km > 0: cols[4].markdown(f"⛽ **Autonomía: {autonomia_km} km**")

    # Detalle de cada tramo
    tramos_peligro = [t for t in tramos if t["nivel"] in ["critico", "atencion"] or t["gap_km"] >= 60]

    if tramos_peligro:
        with st.expander(f"⚠️ Atención: Tienes {len(tramos_peligro)} tramos que requieren revisión", expanded=True):
            for t in tramos_peligro:
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**{t['gap_km']:.1f} km** (Km {t['km_inicio']:.0f} → Km {t['km_fin']:.0f})")
                        st.caption(f"{t['origen']} → {t['destino']}")
                    with c2:
                        st.markdown(f"{t['emoji']} **{t['label']}**")

                    if autonomia_km > 0:
                        pct_bar = min(1.0, t["gap_km"] / autonomia_km)
                        pct_real = (t["gap_km"] / autonomia_km) * 100
                        st.progress(pct_bar, text=f"Consumo de autonomía: {pct_real:.0f}%")

                        if t["nivel"] == "critico":
                            st.error(f"⚠️ Supera tu autonomía en {t['gap_km'] - autonomia_km:.1f} km — Repostar OBLIGATORIAMENTE antes de este tramo.")
                        elif t["nivel"] == "atencion":
                            st.warning(f"⚡ Este tramo de {t['gap_km']:.0f} km consumirá el {pct_real:.0f}% de tu tanque. Entra con suficiente combustible.")
                        else:
                            if t["gap_km"] >= 60:
                                st.info(f"ℹ️ **Tramo de {t['gap_km']:.0f} km sin gasolineras.** Para tu vehículo solo supone un {pct_real:.0f}% de la autonomía total. Tienes margen seguro.")
                    else:
                        if t["gap_km"] >= 100:
                            st.error(f"🚨 **Tramo muy largo ({t['gap_km']:.0f} km sin gasolineras)** — Asegúrate de llevar un nivel alto de combustible antes de entrar.")
                        elif t["gap_km"] >= 60:
                            st.warning(f"⚠️ **Tramo largo ({t['gap_km']:.0f} km sin gasolineras)** — Revisa tu nivel de combustible con antelación.")
    else:
        st.info("Ningún tramo de tu ruta presenta riesgos largos ni exceden tu autonomía. 🟢")
