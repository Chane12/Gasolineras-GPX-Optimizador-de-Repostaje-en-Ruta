## 2024-05-04 - Fix XSS Vulnerability in Folium Popups
**Vulnerability:** User-controlled or external data (like gas station names, addresses, and hours) was interpolated directly into raw HTML strings and served via `folium.Popup`.
**Learning:** Folium map generation is prone to Cross-Site Scripting (XSS) when creating custom interactive HTML popups and tooltip elements.
**Prevention:** Always use `html.escape()` or an HTML sanitization library before embedding variables into manual HTML string templates for Folium maps.
