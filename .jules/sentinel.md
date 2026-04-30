## 2026-04-30 - Cross-Site Scripting (XSS) in Streamlit Markdown
**Vulnerability:** User input for origin and destination text was directly interpolated into HTML rendered by `st.markdown(..., unsafe_allow_html=True)` in `ui_components.py`.
**Learning:** Even internal UI components that render state summaries can introduce XSS if user-controlled variables are not sanitized before being injected into HTML blocks.
**Prevention:** Always sanitize user-controllable variables using `html.escape()` before injecting them into HTML strings when `unsafe_allow_html=True` is used.
