"""Geometric helper utilities."""
from __future__ import annotations

from typing import Iterable, Tuple

Point = Tuple[float, float]


def manhattan_distance(a: Point, b: Point) -> float:
    """Return the Manhattan distance between two points."""

    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def centroid(points: Iterable[Point]) -> Point:
    """Compute centroid of a sequence of 2D points."""

    xs = 0.0
    ys = 0.0
    count = 0
    for x, y in points:
        xs += x
        ys += y
        count += 1
    if count == 0:
        raise ValueError("Cannot compute centroid of empty point set")
    return (xs / count, ys / count)
