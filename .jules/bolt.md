## 2024-04-26 - Redundant Pandas/GeoPandas Sort Bottlenecks
**Learning:** Calling `.sort_values()` on a Pandas DataFrame or GeoDataFrame inside a hot loop introduces an O(N * M log M) bottleneck, especially when the sorting parameters do not change between iterations.
**Action:** Always pre-sort or cache the sorted output of a DataFrame outside the loop, and reuse the sorted variable inside to prevent redundant computation.
