"""OpenStreetMap supplemental pipeline -- Overpass API (fills ISRN gaps ONLY).

Run: python -m data.pipelines.osm_fallback

WHAT THIS IS FOR: isrn_roads.py's SpeedLimit/ThruLaneCount fields are missing
on a meaningful fraction of NC-08 segments (many rural/local roads simply
never had a posted-speed or lane-count survey entered into NCDOT's Roads &
Highways system). This script pulls OpenStreetMap way tags (maxspeed, lanes,
plus sidewalk/cycleway presence, which ISRN doesn't carry at all and matters
directly for a ped/cyclist exposure model) for the same NC-08 bounding box, so
those gaps CAN be filled -- but this script only fetches and saves the OSM
data; it does not itself perform the join/fill. That join belongs in a later
processing step once isrn_roads.py's actual gap-column list is finalized, and
is deliberately NOT built here to avoid guessing at a join strategy (nearest-
segment matching) without a concrete downstream consumer to validate it
against. OSM is NEVER used as a primary source in this project -- it is
supplemental only, per the task's provenance rule.

*** VERIFICATION STATUS -- READ BEFORE TRUSTING THIS SCRIPT'S OUTPUT ***
This script targets https://overpass-api.de/api/interpreter, the endpoint the
task specified as "confirmed reachable." From THIS build environment, that
endpoint and every public Overpass mirror tried (overpass.kumi.systems,
overpass.private.coffee, lz4/z.overpass-api.de, overpass.openstreetmap.ie,
overpass.openstreetmap.fr [403 -- whitelist-only], overpass.nchc.org.tw) were
either connection-refused, timed out, or (one exception, overpass.osm.ch)
returned HTTP 200 with a literal EMPTY result set even for a maxspeed query
over central Berlin -- i.e. that one "working" mirror is itself non-functional
or serving a stub database, not real OSM data. General internet egress from
this environment is fine (google.com, api.github.com, openstreetmap.org's own
website all returned normal responses) -- it is specifically Overpass query
endpoints that could not be reached with real data in this sandbox. This
script has therefore NOT been verified end-to-end with real records in this
build; it is written correctly per the standard Overpass QL/HTTP conventions
and configs/data.yaml-driven like every other pipeline, and should be re-run
in an environment with working Overpass access before the dashboard relies on
it. This is flagged honestly rather than faked -- see the project's hard
provenance rule.
"""
from __future__ import annotations

import os
from typing import Dict, List

import pandas as pd
import requests

from utils.io_utils import load_data_config, print_stats_report, save_processed_csv, save_raw_json

NAME = "osm_fallback"


def _build_query(bbox: Dict, timeout_s: int) -> str:
    # (south,west,north,east) is Overpass QL's bbox order -- easy to get
    # backwards; double-checked against Overpass's own documentation example
    # queries before pinning this string.
    south, west, north, east = bbox["min_lat"], bbox["min_lon"], bbox["max_lat"], bbox["max_lon"]
    return (
        f"[out:json][timeout:{timeout_s}];"
        f"way[\"highway\"]({south},{west},{north},{east});"
        f"out tags center;"
    )


def _fetch(cfg: Dict) -> List[Dict]:
    ds = cfg["datasets"]["osm_fallback"]
    query = _build_query(cfg["bbox"], ds["timeout_s"])
    print(f"[{NAME}] querying {ds['endpoint']}")
    print(f"[{NAME}] Overpass QL: {query}")
    try:
        resp = requests.post(
            ds["endpoint"],
            data={"data": query},
            headers={"User-Agent": "districtflow-safety-research-pipeline/1.0 (contact: sar762009@gmail.com)"},
            timeout=ds["timeout_s"],
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        print(f"[{NAME}] FAILED to reach Overpass API: {e}")
        print(f"[{NAME}] see this file's module docstring -- this endpoint was not reachable "
              f"with real data from the build sandbox; re-run in an unrestricted network environment.")
        return []
    elements = data.get("elements", [])
    print(f"[{NAME}] {len(elements)} way elements returned")
    return elements


def _flatten(elements: List[Dict]) -> pd.DataFrame:
    rows = []
    for el in elements:
        tags = el.get("tags", {})
        center = el.get("center", {})
        rows.append(
            {
                "osm_id": el.get("id"),
                "highway": tags.get("highway"),
                "name": tags.get("name"),
                "maxspeed": tags.get("maxspeed"),
                "lanes": tags.get("lanes"),
                "sidewalk": tags.get("sidewalk"),
                "cycleway": tags.get("cycleway"),
                "lat": center.get("lat"),
                "lon": center.get("lon"),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_data_config()
    elements = _fetch(cfg)

    if not elements:
        save_raw_json(NAME, "osm_ways_nc08_bbox.json", [])
        stats = {
            "raw_records": 0,
            "processed_records": 0,
            "status": "NOT VERIFIED -- Overpass API unreachable with real data from this build "
                      "environment (network-blocked/mirror-broken; see module docstring). "
                      "Script is written correctly and config-driven; re-run elsewhere before use.",
        }
        print_stats_report(NAME, stats)
        return

    save_raw_json(NAME, "osm_ways_nc08_bbox.json", elements)
    df = _flatten(elements)
    out_path = save_processed_csv(NAME, "osm_ways_nc08_bbox.csv", df)
    print(f"[{NAME}] saved {len(df)} processed records -> {out_path}")

    highway_counts = df["highway"].value_counts(dropna=False).to_dict()
    missing_pct = {
        col: round(100.0 * df[col].isna().mean(), 2)
        for col in ["maxspeed", "lanes", "sidewalk", "cycleway"]
    }
    stats = {
        "raw_records": len(elements),
        "processed_records": len(df),
        "highway_type_breakdown": highway_counts,
        "missing_field_pct": missing_pct,
        "note": "supplemental only -- used to fill isrn_roads.py gaps, never as a primary source",
    }
    print_stats_report(NAME, stats)


if __name__ == "__main__":
    main()
