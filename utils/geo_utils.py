"""Shared geometry helpers for all DistrictFlow Safety data pipelines.

Kept dependency-light (stdlib `math` only) and Python 3.9 compatible, matching
the house style of the xtraffic reference project's utils/graph_utils.py
(one haversine implementation, reused everywhere, so nobody re-derives it
slightly differently in five different pipeline scripts).
"""
from __future__ import annotations

import math
from typing import Optional, Tuple


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two lat/lon points.

    Used here to (a) sanity-check that fetched records actually fall inside the
    NC-08 bounding box after reprojection, and (b) as a general utility for any
    later "nearest road segment to this crash point" join the dashboard layer
    needs. Same formula/constant as xtraffic/utils/graph_utils.py so distances
    computed anywhere in this project agree with each other.
    """
    r = 6_371_000.0  # Earth radius, meters
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return float(2 * r * math.asin(math.sqrt(a)))


def bbox_contains(lat: Optional[float], lon: Optional[float], bbox: Tuple[float, float, float, float]) -> bool:
    """bbox = (min_lon, min_lat, max_lon, max_lat). False for missing/NaN coords.

    WHY a bbox check at all when most sources also carry a county field: a few
    sources (NCDOT AADT segments) have no county attribute, only geometry, so
    bbox-intersection is the *only* available NC-08 filter for them (see
    aadt.py). For sources that DO have county names we filter by county first
    (exact) and treat bbox as a secondary sanity check, not the primary filter.
    """
    if lat is None or lon is None:
        return False
    try:
        if lat != lat or lon != lon:  # NaN check without importing math again
            return False
    except TypeError:
        return False
    min_lon, min_lat, max_lon, max_lat = bbox
    return (min_lon <= lon <= max_lon) and (min_lat <= lat <= max_lat)


def polyline_midpoint(paths) -> Tuple[Optional[float], Optional[float]]:
    """Rough representative (lon, lat) for an Esri polyline geometry's `paths`.

    WHY a plain vertex average instead of true arc-length midpoint: these road
    segments are short (typically well under a mile between attribute breaks),
    so the vertex-average point is visually indistinguishable from the true
    midpoint on any dashboard map at NC-08 scale, and it avoids pulling in a
    geometry library for a display-only approximation. Do not use this for
    anything requiring survey-grade accuracy.
    """
    pts = [pt for path in (paths or []) for pt in path]
    if not pts:
        return None, None
    lon = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lon, lat
