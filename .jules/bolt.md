## 2024-05-24 - Pandas/GeoPandas sort_values inside loops
**Learning:** Calling `gdf.sort_values` inside an iterative loop (like when calculating autonomy radar gaps over checkpoints) introduces a hidden O(N * M log M) bottleneck.
**Action:** Extract static sorting operations out of loop scopes when the underlying GeoDataFrame is read-only for the duration of the iteration.
