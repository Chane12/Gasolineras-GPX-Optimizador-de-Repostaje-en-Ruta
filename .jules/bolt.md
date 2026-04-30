## 2025-04-30 - Prevent Redundant Pandas Sorting in Loops
**Learning:** Calling `df.sort_values()` inside a python `for` loop on a GeoDataFrame can severely degrade performance by introducing an $O(N \cdot M \log M)$ complexity bottleneck, where $M$ is the loop iterations and $N$ is dataframe rows.
**Action:** Extract static sorting operations outside of loop scopes to evaluate them once and cache the result.
