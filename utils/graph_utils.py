"""Shared graph helpers for the road-segment risk graph.

Ported from the XTraffic project's utils/graph_utils.py (same author, MIT-style
internal reuse) and adapted from a SENSOR graph to a ROAD-SEGMENT graph:

  XTraffic:        nodes = point sensors,  edges = physical proximity
  DistrictFlow:    nodes = road SEGMENTS,  edges = shared intersections

This is the same trick XTraffic's Chicago pipeline already used (segments as
graph nodes, adjacency from shared endpoint coordinates) — we reuse it as the
primary pattern here instead of point-sensor adjacency, since NCDOT's road
network is segment-based, not sensor-based.

Kept dependency-light (numpy only) and Python 3.9 compatible.
"""
from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Distance
# ---------------------------------------------------------------------------
def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two lat/lon points."""
    r = 6_371_000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return float(2 * r * np.arcsin(np.sqrt(a)))


# ---------------------------------------------------------------------------
# Segment (road) adjacency
# ---------------------------------------------------------------------------
def build_segment_adjacency(
    endpoints: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    intersection_ids: Optional[List[Tuple[object, object]]] = None,
    tol_m: float = 15.0,
) -> np.ndarray:
    """Undirected adjacency between road segments that share an intersection.

    Two construction paths, in priority order:
    1. EXACT: if `intersection_ids` is given (each segment's (from_id, to_id)
       intersection identifiers from ISRN/OSM topology), two segments are
       adjacent iff they share an intersection id. This is the real topology
       and should always be preferred when available.
    2. HEURISTIC: otherwise, fall back to geometric proximity — two segments
       are adjacent iff an endpoint of one lies within `tol_m` meters of an
       endpoint of the other (same method XTraffic's Chicago pipeline used
       for segment-level data with no explicit topology).

    Parameters
    ----------
    endpoints : per-segment ((lat1, lon1), (lat2, lon2)) endpoint coordinates.
    intersection_ids : optional per-segment (from_id, to_id) topology ids.
    tol_m : geometric tolerance for the fallback path.

    Returns
    -------
    adj : [N, N] float32, 1.0 on the diagonal and on each shared-intersection
          pair, 0.0 elsewhere (unweighted — edge WEIGHT features like AADT or
          speed differential are attached separately as model inputs, not
          baked into this structural adjacency).
    """
    n = len(endpoints)
    adj = np.zeros((n, n), dtype=np.float32)
    np.fill_diagonal(adj, 1.0)

    if intersection_ids is not None:
        node_to_segs: Dict[object, List[int]] = {}
        for i, (a, b) in enumerate(intersection_ids):
            node_to_segs.setdefault(a, []).append(i)
            node_to_segs.setdefault(b, []).append(i)
        for segs in node_to_segs.values():
            for i in segs:
                for j in segs:
                    if i != j:
                        adj[i, j] = 1.0
        return adj

    # Heuristic fallback: O(N^2) haversine comparison of all endpoint pairs.
    # Fine at NC-08 scale (thousands, not millions, of segments); flagged in
    # DATA_SOURCES.md as a fallback for whichever segments lack topology ids.
    pts = []
    for a, b in endpoints:
        pts.append(a)
        pts.append(b)
    for i in range(n):
        ai, bi = endpoints[i]
        for j in range(i + 1, n):
            aj, bj = endpoints[j]
            if (haversine_meters(ai[0], ai[1], aj[0], aj[1]) <= tol_m
                    or haversine_meters(ai[0], ai[1], bj[0], bj[1]) <= tol_m
                    or haversine_meters(bi[0], bi[1], aj[0], aj[1]) <= tol_m
                    or haversine_meters(bi[0], bi[1], bj[0], bj[1]) <= tol_m):
                adj[i, j] = adj[j, i] = 1.0
    return adj


# ---------------------------------------------------------------------------
# Shortest-path distance to nearest facility (EMS/fire stations)
# ---------------------------------------------------------------------------
def nearest_facility_distance(
    node_adj_weighted: Dict[object, List[Tuple[object, float]]],
    facility_nodes: List[object],
) -> Dict[object, float]:
    """Multi-source Dijkstra: shortest road-network distance (meters) from
    every intersection node to its NEAREST facility (EMS/fire station).

    WHY multi-source Dijkstra instead of N single-source runs: pushing every
    facility onto the heap at distance 0 simultaneously and relaxing outward
    finds each node's distance to its CLOSEST facility in one graph traversal
    (Dijkstra's correctness only depends on non-negative edge weights and a
    consistent "already settled" check — the source being a set instead of a
    point doesn't change that), which is O((V+E) log V) instead of
    O(F * (V+E) log V) for F facilities.

    Parameters
    ----------
    node_adj_weighted : intersection_id -> [(neighbor_intersection_id, meters), ...]
                        (an undirected weighted graph over INTERSECTIONS, built
                        from segment lengths — this is the routing graph EMS
                        distance is computed over, distinct from the segment
                        adjacency above which is the graph the GNN operates on).
    facility_nodes : intersection ids nearest each EMS/fire station.

    Returns
    -------
    dist : intersection_id -> meters to nearest facility. Unreachable nodes are
           omitted (caller should treat missing = data gap, not infinity, per
           the provenance rule — never silently present a fabricated number).
    """
    dist: Dict[object, float] = {}
    heap: List[Tuple[float, object]] = []
    for f in facility_nodes:
        if f in node_adj_weighted:
            heap.append((0.0, f))
    heapq.heapify(heap)
    while heap:
        d, u = heapq.heappop(heap)
        if u in dist and dist[u] <= d:
            continue
        dist[u] = d
        for v, w in node_adj_weighted.get(u, []):
            nd = d + w
            if v not in dist or nd < dist[v]:
                heapq.heappush(heap, (nd, v))
    return dist


# ---------------------------------------------------------------------------
# Normalization (train-statistics only) — same rationale as XTraffic
# ---------------------------------------------------------------------------
class StandardScaler:
    """Per-feature z-score scaler fit on TRAIN segments only.

    WHY train-only: mean/std become parameters of the pipeline. Fitting on
    val/test segments would leak their distribution into training, the same
    leakage XTraffic avoids by fitting only on the train split of METR-LA.
    """

    def __init__(self, mean: Optional[np.ndarray] = None, std: Optional[np.ndarray] = None):
        self.mean = mean
        self.std = std

    @classmethod
    def fit(cls, train_values: np.ndarray) -> "StandardScaler":
        # train_values : [n_train_segments, n_features]
        mean = np.nanmean(train_values, axis=0)
        std = np.nanstd(train_values, axis=0)
        std = np.where(std < 1e-6, 1.0, std)  # guard constant/missing columns
        return cls(mean=mean, std=std)

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std

    def inverse_transform(self, x: np.ndarray) -> np.ndarray:
        return x * self.std + self.mean

    def to_dict(self) -> Dict[str, list]:
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}

    @classmethod
    def from_dict(cls, d: Dict[str, list]) -> "StandardScaler":
        return cls(mean=np.array(d["mean"]), std=np.array(d["std"]))


def chronological_or_spatial_split(
    n_samples: int, train_ratio: float, val_ratio: float, seed: int = 42
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Train/val/test index arrays for a STATIC graph (no time axis).

    XTraffic splits chronologically because its samples are sliding time
    windows over one graph (shuffling would leak future into past). We have
    no time series here — each sample is a road segment with static
    features — so a chronological split doesn't apply. We use a seeded random
    split instead (segments are independent units, not time-ordered), which
    is the closest honest analogue: the leakage this guards against here is
    the same family of error, just along a different axis (spatial train/test
    contamination would be a bigger risk if segments were densely overlapping
    micro-segments, but ISRN/OSM segments are already discrete distinct road
    stretches, so a random split is standard practice for spatial GNN node
    regression/classification tasks).
    """
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n_samples)
    n_train = int(round(n_samples * train_ratio))
    n_val = int(round(n_samples * val_ratio))
    return idx[:n_train], idx[n_train:n_train + n_val], idx[n_train + n_val:]
