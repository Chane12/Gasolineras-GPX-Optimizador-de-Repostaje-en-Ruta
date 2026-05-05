## 2025-02-14 - Fix Cross-Site Scripting (XSS) in Folium Popups
**Vulnerability:** External data (gas station names, addresses, etc.) from MITECO API was directly interpolated into raw HTML strings for `folium.Popup` without sanitization. This allowed Cross-Site Scripting (XSS).
**Learning:** `folium.Popup` and tooltips often use raw HTML interpolation. Data coming from third-party APIs must be assumed unsafe and properly escaped.
**Prevention:** Always sanitize variables embedded in raw HTML using `html.escape()` before string interpolation.
