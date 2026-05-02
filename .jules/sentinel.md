## 2023-10-27 - Mitigating XSS vulnerabilities in Streamlit components

**Vulnerability:**
XSS vulnerability identified in `ui_components.py` where user-provided inputs (`origen_txt`, `destino_txt`, `combustible`) were directly interpolated into an HTML string that was rendered via `st.markdown(..., unsafe_allow_html=True)` without proper sanitization.

**Learning:**
Streamlit allows HTML injection via `unsafe_allow_html=True` to provide custom styling, but doing so with untrusted or user-provided variables opens the application to Cross-Site Scripting (XSS) attacks. Additionally, static headers do not require `unsafe_allow_html=True` and should use standard markdown processing.

**Prevention:**
Always sanitize user-controllable variables using `html.escape()` before interpolating them into HTML strings when `unsafe_allow_html=True` is used. Furthermore, avoid using `unsafe_allow_html=True` for static text or standard headers where basic markdown formatting suffices.