## 2024-05-15 - Vectorized Spatial Operations
**Learning:** Using Python list comprehensions to call `LineString.project()` for each geometry in a GeoSeries is highly inefficient compared to its vectorized equivalent.
**Action:** Always prefer `shapely.line_locate_point(line, geodataframe.geometry)` or other C-vectorized equivalents when operating over an entire DataFrame/GeoSeries in spatial workloads.
