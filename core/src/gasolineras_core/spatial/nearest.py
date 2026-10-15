"""
gasolineras_core.spatial.nearest
================================
KD-Tree based nearest-neighbor utilities for spatial queries.
"""

from __future__ import annotations

import numpy as np
from scipy.spatial import KDTree


def build_kdtree_from_points(
    points: list[tuple[float, float]],
) -> KDTree:
    """
    Build a KDTree from a list of (x, y) coordinate tuples.

    Parameters
    ----------
    points : list[tuple[float, float]]
        List of (longitude, latitude) or (x, y) pairs.

    Returns
    -------
    KDTree
        Scipy KD-Tree for O(log N) nearest-neighbor queries.
    """
    return KDTree(np.array(points))


def query_nearest(
    tree: KDTree,
    query_point: tuple[float, float],
) -> tuple[float, int]:
    """
    Find the nearest neighbor of a query point in the KD-Tree.

    Parameters
    ----------
    tree : KDTree
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
