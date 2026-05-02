
## 2025-02-28 - Shapely Vectorization for Distance and Interpolation
**Learning:** Found a specific performance bottleneck where `.apply()` was being used to invoke `track_original.project()` and `track_original.interpolate()` over GeoPandas row geometries inside `enrich_stations_with_osrm`. This is inefficient in Python since `apply` operates element-wise and creates significant interpreter overhead.
**Action:** Replaced `.apply` iterations with Shapely 2.0 array-aware/C-vectorized functions like `shapely.line_locate_point()` and `shapely.line_interpolate_point()`. Then extracted coordinates with `shapely.get_x()` and `shapely.get_y()`. Always favor array-aware functions when processing GeoPandas/Shapely logic over DataFrames/Series to ensure C-level performance speeds.
