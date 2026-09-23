"""Join the real NCDOT/NC OneMap pulls (data/pipelines/{isrn_roads,aadt,
crashes_general,crashes_pedcyclist,ems_fire_stations}.py) into the single
segment feature table + adjacency matrix RiskGNN trains on
(docs/FEATURES.md is the column contract this script fills).

KEY DESIGN DECISION — the graph's NODES are AADT segments, not raw ISRN
records. ISRN's `NCDOT_RoadCharacteristicsQtr` re-splits a route on EVERY
attribute change (see DATA_SOURCES.md §1): the real pull has 157,807 rows,
many of them a few FEET long (one sample segment spans 0.00001 miles). Using
those as graph nodes would (a) make the model architecturally infeasible —
`RiskGNN`'s MOD-1 semantic adjacency is an O(N^2) dense N x N matrix by
construction (models/gnn/risk_gnn.py), completely impractical at N=157,807
— and (b) spread the already-sparse 5-year ped/cyclist incident signal
(3,454 records total) so thin that almost every node would show zero
incidents regardless of real risk. NCDOT's own AADT segment product
(`NCDOT_2025_AADTandTrafficSegments_gdb`, 7,861 segments in NC-08, each a
real stretch between significant points — the sample segment is 3.56 miles)
is NCDOT's own established unit of traffic-volume analysis, not an ad hoc
bucketing rule invented for this project. Using it as the node set is
therefore both the pragmatic AND the more standard choice. This also means
the model's scope is implicitly "the AADT-counted road network" — NCDOT
doesn't run AADT counts on minor residential streets, so this project does
not score those (documented in docs/LIMITATIONS.md; it also concentrates
scope on the collector/arterial roads where most ped/cyclist crashes and
FHWA safety-program attention already occur, so this is not just an
accidental gap).

GENERAL CRASH COUNT IS COUNTY-LEVEL, NOT SEGMENT-LEVEL (a real, discovered
data limitation, not an oversight): `StatewideCrashTable` is a plain
attribute TABLE with no geometry at all (confirmed on the live service —
`tables: [...]`, no `layers`), so general vehicle crashes CANNOT be spatially
joined to a segment. `general_crash_count_5yr_county` is the honest name for
what this actually is: the same county-wide 5-year total attached to every
segment in that county, a coarse contextual feature, not a per-segment
measurement. `pedcyclist_incident_count_5yr` (the primary training label) DOES
have real per-crash coordinates and is genuinely segment-level.

EMS DISTANCE is real shortest-path routing over the SAME segment adjacency
graph the GNN trains on (brief's own wording: "computed via shortest-path
routing over the graph itself") — no separate intersection graph is built;
the segment graph already connects road stretches at shared endpoints, so it
doubles as the routing substrate, with edge weight = haversine distance
between adjacent segments' midpoints (utils/graph_utils.nearest_facility_distance).

Run: python -m data.pipelines.assemble_features
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from utils.graph_utils import (build_segment_adjacency, haversine_meters,
                                nearest_facility_distance)

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"
OUT_FEATURES = "data/processed/nc08_segments.parquet"
OUT_ADJACENCY = "data/processed/nc08_adjacency.npy"

# Standard 5 rural NC-08 counties vs. 3 that carry the Charlotte suburbs
# (fallback ONLY when a segment's ISRN join is too far to trust UrbanType —
# see rural_flag derivation below, which prefers the real Census-derived
# UrbanType field over this county-level guess whenever it's available).
RURAL_COUNTIES = {"Stanly", "Montgomery", "Anson", "Richmond", "Robeson"}

ISRN_JOIN_MAX_M = 500.0     # beyond this, a FINE attribute match (speed/lanes/class) isn't trusted
COUNTY_JOIN_MAX_M = 5000.0  # county boundaries are coarse; a much looser radius is fine for county-only
CRASH_JOIN_MAX_M = 200.0    # beyond this, a crash point isn't assigned to any segment
EMS_JOIN_MAX_M = 2000.0     # beyond this, a station isn't linked to a routing node

# DIAGNOSIS (kept as a comment, not just in the commit message, because the
# next person editing this file needs the same context): AADT segments are
# filtered by a padded RECTANGULAR bbox (DATA_SOURCES.md §3 — this layer has
# no county attribute at all), but NC-08's 8 counties are not
# rectangle-shaped, so the padded bbox legitimately includes real road
# network belonging to NEIGHBORING counties/states (Rowan, Iredell, Gaston,
# Scotland, Hoke, or South Carolina). Measured on the live pull: nearest-ISRN
# distance is clearly BIMODAL — a dense cluster under ~2km (genuine NC-08
# segments, ISRN's own network is just locally sparse in some rural
# stretches) and a second cluster at 5-70km (structurally outside NC-08,
# caught only by the rectangular bbox). COUNTY_JOIN_MAX_M=5000 sits in the
# gap between those two clusters. ISRN_JOIN_MAX_M=500 stays tight because
# speed limit / lane count are truly LOCAL properties a 3km-away ISRN point
# should not be trusted to describe, even for a segment whose COUNTY is
# correctly identified from that same match.


def _load_aadt_segments() -> pd.DataFrame:
    with open(os.path.join(RAW_DIR, "aadt", "aadt_segments_nc08_bbox.json")) as f:
        raw = json.load(f)
    rows = []
    for rec in raw:
        attrs = rec["attributes"]
        paths = rec.get("geometry", {}).get("paths") or [[]]
        verts = paths[0]  # [[lon, lat], ...]
        if len(verts) < 2:
            continue
        lons = [v[0] for v in verts]
        lats = [v[1] for v in verts]
        rows.append({
            "segment_id": str(attrs["TSegID2025"]),
            "route_id": attrs.get("RouteID"),
            "aadt_raw": attrs.get("AADT"),
            "aadtt_raw": attrs.get("AADTT"),
            "start_lon": verts[0][0], "start_lat": verts[0][1],
            "end_lon": verts[-1][0], "end_lat": verts[-1][1],
            "mid_lon": float(np.mean(lons)), "mid_lat": float(np.mean(lats)),
            "_vertices": verts,  # kept only for the vertex-index build below
        })
    df = pd.DataFrame(rows)
    # AADT can legitimately be null for a segment NCDOT hasn't counted this
    # cycle; never silently zero-fill a traffic-volume feature (that would
    # claim "no traffic," not "no data") — drop it from THIS layer's join,
    # it still exists as a node, aadt_raw stays NaN and the Poisson-offset
    # code (models/gnn/train.py) already floors NaN AADT defensively there.
    return df.reset_index(drop=True)


def _build_vertex_index(segments: pd.DataFrame) -> Tuple[cKDTree, np.ndarray]:
    """One KD-tree over EVERY vertex of every segment's polyline, each tagged
    with its segment's row index — used to assign a point (a crash, a
    station) to the NEAREST SEGMENT, not just the nearest segment midpoint.
    Segments here can be miles long, so midpoint-only assignment would badly
    mis-locate crashes far from a segment's center; nearest-vertex is a much
    closer approximation of true point-to-polyline distance and costs nothing
    extra since the vertices are already in hand.
    """
    pts, owner = [], []
    for i, verts in enumerate(segments["_vertices"]):
        for lon, lat in verts:
            pts.append((lat, lon))
            owner.append(i)
    tree = cKDTree(np.array(pts))
    return tree, np.array(owner)


def _nearest_segment(tree: cKDTree, owner: np.ndarray, lat: float, lon: float,
                     max_m: float, mean_lat: float) -> Tuple[Optional[int], float]:
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * max(np.cos(np.radians(mean_lat)), 1e-6)
    # Query in a generous degree radius, verify with real haversine — same
    # coarse-filter/exact-verify pattern as build_segment_adjacency.
    deg_radius = max_m / min(m_per_deg_lat, m_per_deg_lon)
    idxs = tree.query_ball_point((lat, lon), r=deg_radius)
    if not idxs:
        return None, float("nan")
    best_i, best_d = None, float("inf")
    pts = tree.data
    for i in idxs:
        d = haversine_meters(lat, lon, pts[i][0], pts[i][1])
        if d < best_d:
            best_d, best_i = d, int(owner[i])
    if best_d > max_m:
        return None, float("nan")
    return best_i, best_d


def _join_isrn(segments: pd.DataFrame) -> pd.DataFrame:
    isrn = pd.read_csv(os.path.join(PROCESSED_DIR, "isrn_roads", "road_characteristics_nc08.csv"),
                       low_memory=False)
    isrn_pts = isrn[["_lat", "_lon"]].to_numpy()
    tree = cKDTree(isrn_pts)
    mean_lat = float(segments["mid_lat"].mean())
    # Single ball query at the LOOSER county radius; fine-attribute matching
    # then re-checks the same best match against the tighter threshold. One
    # query per segment either way — this just reuses its result for both
    # decisions instead of querying twice.
    deg_radius = COUNTY_JOIN_MAX_M / (111_320.0 * max(np.cos(np.radians(mean_lat)), 1e-6))

    cols = {"speed_limit_mph": [], "lane_count": [], "road_classification": [],
           "surface_type": [], "county": [], "rural_flag": [],
           "segment_name": [], "isrn_join_distance_m": []}
    for _, seg in segments.iterrows():
        idxs = tree.query_ball_point((seg["mid_lat"], seg["mid_lon"]), r=deg_radius)
        best_i, best_d = None, float("inf")
        for i in idxs:
            d = haversine_meters(seg["mid_lat"], seg["mid_lon"], isrn_pts[i][0], isrn_pts[i][1])
            if d < best_d:
                best_d, best_i = d, i

        if best_i is None or best_d > COUNTY_JOIN_MAX_M:
            # No ISRN point within even the loose county radius -> this
            # segment is almost certainly a bbox false-positive outside
            # NC-08 entirely (see the DIAGNOSIS comment above). Dropped
            # later (county is required downstream).
            for k in cols:
                cols[k].append(np.nan if k != "rural_flag" else None)
            cols["isrn_join_distance_m"][-1] = best_d if best_i is not None else np.nan
            continue

        row = isrn.iloc[best_i]
        cols["county"].append(row["County"])
        # Real Census-derived urban/rural signal (see module docstring):
        # UrbanType is "Urbanized Area" / "Urban Cluster" / NaN (= outside
        # any delineated urban area => rural, standard Census definition).
        # County boundaries are coarse, so this is trusted at the same
        # COUNTY_JOIN_MAX_M radius as county itself.
        cols["rural_flag"].append(bool(pd.isna(row["UrbanType"])))
        name = row.get("StreetName") or row.get("RouteName") or f"Route {seg['route_id']}"
        cols["segment_name"].append(f"{name} ({row['County']})")
        cols["isrn_join_distance_m"].append(best_d)

        # FINE attributes (speed limit, lane count, functional class,
        # surface) are LOCAL properties — only trust them at the tighter
        # ISRN_JOIN_MAX_M radius, even though county/rural_flag from this
        # same match are kept.
        if best_d <= ISRN_JOIN_MAX_M:
            cols["speed_limit_mph"].append(row["SpeedLimit"] if row["SpeedLimit"] not in (0, None) else np.nan)
            cols["lane_count"].append(row["ThruLaneCount"] if row["ThruLaneCount"] not in (0, None) else np.nan)
            cols["road_classification"].append(row["FuncClass"])
            cols["surface_type"].append(row["SrfcType"])
        else:
            cols["speed_limit_mph"].append(np.nan)
            cols["lane_count"].append(np.nan)
            cols["road_classification"].append(np.nan)
            cols["surface_type"].append(np.nan)

    for k, v in cols.items():
        segments[k] = v
    return segments


def _join_pedcyclist_crashes(segments: pd.DataFrame, tree: cKDTree, owner: np.ndarray,
                             mean_lat: float) -> np.ndarray:
    crashes = pd.read_csv(os.path.join(PROCESSED_DIR, "crashes_pedcyclist",
                                       "nonmotorist_crashes_nc08_2021_2025.csv"))
    counts = np.zeros(len(segments), dtype=np.int64)
    unmatched = 0
    for _, row in crashes.iterrows():
        if pd.isna(row["lat"]) or pd.isna(row["lon"]):
            unmatched += 1
            continue
        seg_idx, _ = _nearest_segment(tree, owner, row["lat"], row["lon"],
                                      CRASH_JOIN_MAX_M, mean_lat)
        if seg_idx is None:
            unmatched += 1
            continue
        counts[seg_idx] += 1
    print(f"[assemble_features] ped/cyclist crashes: {len(crashes) - unmatched}/{len(crashes)} "
         f"matched to a segment within {CRASH_JOIN_MAX_M:.0f}m ({unmatched} unmatched)")
    return counts


def _join_general_crashes_county(segments: pd.DataFrame) -> pd.Series:
    """COUNTY-LEVEL ONLY — see module docstring for why (StatewideCrashTable
    has no geometry at all)."""
    crashes = pd.read_csv(os.path.join(PROCESSED_DIR, "crashes_general",
                                       "statewide_crash_table_nc08_2021_2025.csv"))
    county_totals = crashes.groupby("County").size()
    return segments["county"].map(county_totals).fillna(0).astype(int)


def _join_ems_distance(segments: pd.DataFrame, adjacency: np.ndarray,
                       tree: cKDTree, owner: np.ndarray, mean_lat: float) -> pd.Series:
    stations = pd.read_csv(os.path.join(PROCESSED_DIR, "ems_fire_stations",
                                        "fire_ems_stations_nc08.csv"))
    facility_nodes = set()
    for _, st in stations.iterrows():
        if pd.isna(st["lat"]) or pd.isna(st["lon"]):
            continue
        seg_idx, _ = _nearest_segment(tree, owner, st["lat"], st["lon"], EMS_JOIN_MAX_M, mean_lat)
        if seg_idx is not None:
            facility_nodes.add(seg_idx)
    print(f"[assemble_features] {len(facility_nodes)} distinct segments hold >=1 fire/EMS "
         f"station within {EMS_JOIN_MAX_M:.0f}m (of {len(stations)} stations)")

    # The routing graph IS the segment adjacency graph (brief's own wording:
    # "shortest-path routing over the graph itself") — edge weight =
    # haversine between adjacent segments' midpoints.
    node_adj: Dict[int, List[Tuple[int, float]]] = {i: [] for i in range(len(segments))}
    ii, jj = np.where(adjacency > 0)
    mids = segments[["mid_lat", "mid_lon"]].to_numpy()
    for i, j in zip(ii.tolist(), jj.tolist()):
        if i == j:
            continue
        w = haversine_meters(mids[i][0], mids[i][1], mids[j][0], mids[j][1])
        node_adj[i].append((j, w))

    dist = nearest_facility_distance(node_adj, list(facility_nodes))
    out = pd.Series([dist.get(i, np.nan) for i in range(len(segments))])
    print(f"[assemble_features] EMS routing distance resolved for "
         f"{out.notna().sum()}/{len(out)} segments "
         f"({out.notna().mean()*100:.1f}%) — rest are graph-disconnected from "
         f"any station-adjacent segment, left as a real data gap, not guessed.")
    return out


def main() -> None:
    segments = _load_aadt_segments()
    print(f"[assemble_features] {len(segments)} AADT segments loaded (graph nodes)")

    segments = _join_isrn(segments)
    isrn_matched = segments["speed_limit_mph"].notna().sum()
    print(f"[assemble_features] ISRN attribute join: {isrn_matched}/{len(segments)} "
         f"segments matched within {ISRN_JOIN_MAX_M:.0f}m")

    vertex_tree, vertex_owner = _build_vertex_index(segments)
    mean_lat = float(segments["mid_lat"].mean())

    segments["pedcyclist_incident_count_5yr"] = _join_pedcyclist_crashes(
        segments, vertex_tree, vertex_owner, mean_lat)
    segments["general_crash_count_5yr_county"] = _join_general_crashes_county(segments)

    endpoints = list(zip(
        zip(segments["start_lat"], segments["start_lon"]),
        zip(segments["end_lat"], segments["end_lon"]),
    ))
    adjacency = build_segment_adjacency(endpoints, intersection_ids=None, tol_m=50.0)
    n_edges = int((adjacency > 0).sum() - len(segments))
    print(f"[assemble_features] segment adjacency: {n_edges} shared-endpoint edges "
         f"(50m tolerance) over {len(segments)} nodes")

    segments["ems_distance_m"] = _join_ems_distance(
        segments, adjacency, vertex_tree, vertex_owner, mean_lat)

    # AADT normalization (district-wide min-max, matching docs/FEATURES.md).
    aadt_valid = segments["aadt_raw"].dropna()
    if len(aadt_valid) > 0 and aadt_valid.max() > aadt_valid.min():
        segments["aadt_normalized"] = (
            (segments["aadt_raw"] - aadt_valid.min()) / (aadt_valid.max() - aadt_valid.min()))
    else:
        segments["aadt_normalized"] = 0.0

    # Segments with NO ISRN point within even the loose COUNTY_JOIN_MAX_M
    # radius are dropped — per the DIAGNOSIS comment near the top of this
    # file, these are almost certainly bbox false-positives outside NC-08
    # entirely (AADT has no county attribute of its own to fall back on),
    # not genuine NC-08 segments losing real data.
    county_fallback_needed = segments["county"].isna()
    if county_fallback_needed.any():
        print(f"[assemble_features] {county_fallback_needed.sum()} segments had no ISRN "
             f"match within {COUNTY_JOIN_MAX_M:.0f}m (likely bbox false-positives outside "
             f"NC-08, not real data loss — see DIAGNOSIS comment) — dropped from the "
             f"training table.")
    segments = segments[~county_fallback_needed].reset_index(drop=True)
    # Re-derive adjacency + everything positional AFTER dropping rows, since
    # row order defines the graph's node indices end to end.
    if county_fallback_needed.any():
        keep_idx = np.where(~county_fallback_needed.to_numpy())[0]
        adjacency = adjacency[np.ix_(keep_idx, keep_idx)]

    segments["county_code"] = pd.factorize(segments["county"])[0].astype(float)
    segments["road_classification"] = segments["road_classification"].astype(float)
    segments["lane_count"] = segments["lane_count"].astype(float)

    out_cols = [
        "segment_id", "segment_name", "county", "rural_flag", "county_code",
        "speed_limit_mph", "lane_count", "road_classification",
        "aadt_raw", "aadt_normalized",
        "pedcyclist_incident_count_5yr", "general_crash_count_5yr_county",
        "ems_distance_m",
        "start_lat", "start_lon", "end_lat", "end_lon", "mid_lat", "mid_lon",
        "isrn_join_distance_m",
    ]
    final = segments[out_cols].copy()

    os.makedirs(os.path.dirname(OUT_FEATURES), exist_ok=True)
    final.to_parquet(OUT_FEATURES)
    np.save(OUT_ADJACENCY, adjacency)

    print(f"\n[assemble_features] STATS REPORT")
    print(f"  segments (graph nodes): {len(final)}")
    print(f"  counties: {sorted(final['county'].unique())}")
    print(f"  rural segments: {int(final['rural_flag'].sum())} "
         f"({final['rural_flag'].mean()*100:.1f}%)")
    print(f"  speed_limit_mph missing: {final['speed_limit_mph'].isna().mean()*100:.1f}%")
    print(f"  lane_count missing: {final['lane_count'].isna().mean()*100:.1f}%")
    print(f"  aadt_raw missing: {final['aadt_raw'].isna().mean()*100:.1f}%")
    print(f"  ems_distance_m missing: {final['ems_distance_m'].isna().mean()*100:.1f}%")
    print(f"  total ped/cyclist incidents (5yr, segment-matched): "
         f"{int(final['pedcyclist_incident_count_5yr'].sum())}")
    print(f"  segments with >=1 ped/cyclist incident: "
         f"{int((final['pedcyclist_incident_count_5yr'] > 0).sum())} "
         f"({(final['pedcyclist_incident_count_5yr'] > 0).mean()*100:.1f}%)")
    print(f"  adjacency: {len(final)} nodes, "
         f"{int((adjacency > 0).sum() - len(final))} edges")
    print(f"  wrote {OUT_FEATURES} and {OUT_ADJACENCY}")


if __name__ == "__main__":
    main()
