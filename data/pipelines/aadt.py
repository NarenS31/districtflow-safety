"""Annual Average Daily Traffic (AADT) pipeline -- NCDOT 2025 AADT segments.

Run: python -m data.pipelines.aadt

One static annual-average traffic-volume figure per road segment -- the
exposure denominator for crash-RATE (not just raw crash-count) scoring: a
road carrying 30,000 vehicles/day with 5 crashes/year is objectively safer per
vehicle-mile than one carrying 3,000 vehicles/day with the same 5 crashes.

WHY bounding-box filtering, not county: confirmed live, this layer's field
schema (TSegID2025, RouteID, BeginMP, EndMP, AADT, AADT_Year, ...) has NO
county attribute at all -- it is pure linear-referenced segment geometry. Per
the task's own fallback rule ("filter by county field if present, else by
bounding box"), we use the NC-08 bbox from configs/data.yaml (itself derived
from the live extent of the county-attributed isrn_roads service, so it's not
an arbitrary box). This means a handful of segments just outside the 8
counties but inside the padded bbox may slip in near the district's edge --
flagged here and in DATA_SOURCES.md as a known, small, edge-only imprecision,
not silently hidden.

WHY the "_gdb" 2025 service specifically, over NCDOT_AADT_Stations (also
live): Stations stores one AADT value per fixed count-station location with
a separate column per year (AADT_2002 .. AADT_2022, as plain strings) -- point
data, sparse, and already 3 years stale relative to this project's 2026 build
date. NCDOT_2025_AADTandTrafficSegments_gdb is SEGMENT-level (matches the
isrn_roads unit of analysis), single current AADT_Year=2025 value per segment,
and is NCDOT's newest published AADT product. We use it as the AADT source of
record and do not also pull Stations (documented, not silently dropped).
"""
from __future__ import annotations

from typing import Dict

import pandas as pd

from utils.io_utils import (
    fetch_arcgis_features,
    flatten_features,
    load_data_config,
    print_stats_report,
    save_processed_csv,
    save_raw_json,
)

NAME = "aadt"


def _fetch(cfg: Dict) -> pd.DataFrame:
    ds = cfg["datasets"][NAME]
    bbox = cfg["bbox"]
    geometry = f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}"

    print(f"[{NAME}] querying {ds['service_url']}")
    print(f"[{NAME}] bbox={geometry}")
    features = fetch_arcgis_features(
        ds["service_url"],
        where="1=1",
        out_fields=",".join(ds["fields_used"]),
        geometry=geometry,
        geometry_type="esriGeometryEnvelope",
        page_size=ds["page_size"],
        return_geometry=True,  # polyline -- we need a midpoint to plot each segment
    )
    raw_path = save_raw_json(NAME, "aadt_segments_nc08_bbox.json", features)
    print(f"[{NAME}] saved {len(features)} raw records -> {raw_path}")

    return flatten_features(features)


def _clean(df: pd.DataFrame, bbox: Dict) -> pd.DataFrame:
    from utils.geo_utils import bbox_contains

    df = df.copy()
    bbox_tuple = (bbox["min_lon"], bbox["min_lat"], bbox["max_lon"], bbox["max_lat"])
    df["_in_bbox"] = df.apply(lambda r: bbox_contains(r.get("_lat"), r.get("_lon"), bbox_tuple), axis=1)
    before = len(df)
    df = df[df["_in_bbox"]].drop(columns=["_in_bbox"])
    dropped = before - len(df)
    if dropped:
        print(f"[{NAME}] dropped {dropped} records whose midpoint fell outside the bbox after reprojection")
    # AADT=0 or missing means "not measured on this segment" (e.g. a ramp NCDOT
    # doesn't independently count), not "zero traffic" -- keep as NaN, don't
    # coerce to 0, so an exposure model doesn't treat it as a true zero.
    df.loc[df["AADT"] <= 0, "AADT"] = pd.NA
    return df


def main() -> None:
    cfg = load_data_config()
    raw_df = _fetch(cfg)
    clean_df = _clean(raw_df, cfg["bbox"])

    out_path = save_processed_csv(NAME, "aadt_segments_nc08_bbox.csv", clean_df)
    print(f"[{NAME}] saved {len(clean_df)} processed records -> {out_path}")

    aadt_year_counts = clean_df["AADT_Year"].value_counts(dropna=False).to_dict()
    missing_pct = {
        col: round(100.0 * clean_df[col].isna().mean(), 2)
        for col in ["AADT", "AADTT", "SU_AADT", "MU_AADT"]
        if col in clean_df.columns
    }

    stats = {
        "raw_records": len(raw_df),
        "processed_records": len(clean_df),
        "aadt_year_breakdown": aadt_year_counts,
        "aadt_stats_vehicles_per_day": {
            "min": float(clean_df["AADT"].min(skipna=True)),
            "median": float(clean_df["AADT"].median(skipna=True)),
            "max": float(clean_df["AADT"].max(skipna=True)),
        },
        "missing_field_pct": missing_pct,
        "note": (
            "filtered by NC-08 BOUNDING BOX, not county attribute (this "
            "service has none) -- a small number of near-border segments "
            "just outside the 8 counties may be included; see DATA_SOURCES.md"
        ),
    }
    print_stats_report(NAME, stats)


if __name__ == "__main__":
    main()
