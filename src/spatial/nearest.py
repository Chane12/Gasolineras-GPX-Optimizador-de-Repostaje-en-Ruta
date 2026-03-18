"""
src/spatial/nearest.py
======================
KD-Tree based nearest-neighbor utilities for spatial queries.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def build_kdtree_from_points(
    points: list[tuple[float, float]],
) -> cKDTree:
    """
    Build a cKDTree from a list of (x, y) coordinate tuples.

    Parameters
    ----------
    points : list[tuple[float, float]]
        List of (longitude, latitude) or (x, y) pairs.

    Returns
    -------
    cKDTree
        Scipy KD-Tree for O(log N) nearest-neighbor queries.
    """
    return cKDTree(np.array(points))


def query_nearest(
    tree: cKDTree,
    query_point: tuple[float, float],
) -> tuple[float, int]:
    """
    Find the nearest neighbor of a query point in the KD-Tree.

    Parameters
    ----------
    tree : cKDTree
        Pre-built KD-Tree.
    query_point : tuple[float, float]
        (x, y) coordinates of the query point.

    Returns
    -------
    tuple[float, int]
        (distance, index) of the nearest neighbor.
    """
    dist, idx = tree.query(query_point)
    return float(dist), int(idx)
