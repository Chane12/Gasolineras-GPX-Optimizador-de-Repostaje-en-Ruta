import streamlit as st

def render_welcome_screen():
    """Renders the welcome screen with pure native components."""
    with st.container(border=True):
        st.markdown("<h1 style='text-align: center; font-size: 3.5rem; margin-bottom: 0;'>🛣️⛽</h1>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center; margin-top: 0;'>Planificador Inteligente de Repostaje en Ruta</h2>", unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align: center; color: gray;'>"
            "Indica el Origen y Destino o sube el GPX de tu próximo viaje, indica tu combustible y el depósito de tu vehículo.<br>"
            "Encontramos las gasolineras más baratas de España <strong>en tiempo real</strong> "
            "cruzando datos geográficos con la API oficial del MITECO. ¡Ahorra en cada escapada!"
            "</p>", 
            unsafe_allow_html=True
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
