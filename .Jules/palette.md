## 2024-04-25 - Improve Context on Disabled Buttons
**Learning:** Disabled UI elements (like "Added to plan" buttons) often confuse users if they lack context on *why* they are disabled. Streamlit's native `help` parameter is an excellent, low-effort way to provide this context via tooltips, especially on cards where screen estate is limited.
**Action:** Always provide a descriptive `help` tooltip for `st.button` or `st.link_button` components, particularly when the button can be in a disabled state.
