"""Pedestrian/cyclist crash pipeline -- NCDOT Non-Motorist Crashes.

Run: python -m data.pipelines.crashes_pedcyclist

This is the dashboard's PRIMARY ped/cyclist incident source. NCDOT publishes
individual non-motorist-involved crash records (one row per crash, not an
aggregate) with lat/lon, non-motorist type (Pedestrian/Bicyclist/Other),
severity, and roadway context -- exactly the point-level data a crash-risk-
exposure map needs, as opposed to the county-level rollups in crashes_general.

WHY this service and not the "HSIP_BIKEPED"/"HSIP_BP" family the task
description flagged as a lead: those turned out (confirmed live, see
DATA_SOURCES.md) to be NCDOT Highway Safety Improvement Program *candidate
project site* layers -- engineering-prioritized locations for infrastructure
funding, not a record of individual crashes. NCDOT_NonMotoristCrashes is the
actual per-crash table; it is what HSIP's own bike/ped prioritization is
presumably built from. We use NonMotoristCrashes as ground truth and treat the
HSIP layers as a separate, not-yet-built "known high-priority sites" overlay
(documented as a gap in DATA_SOURCES.md, not silently substituted here).

WHY "5 most recent finalized years": configs/data.yaml pins [2021..2025].
2026 has zero records in this table at all (its live max CrashYear is 2025,
unlike crashes_general's StatewideCrashTable which does have a visibly-partial
2026) -- so excluding 2026 here isn't even a judgment call, it doesn't exist
yet in this table. See configs/data.yaml crash_years comment for the full
cross-check against crashes_general.
"""
from __future__ import annotations

import os
from typing import Dict

import pandas as pd

from utils.io_utils import (
    fetch_arcgis_features,
    flatten_features,
    load_data_config,
    print_stats_report,
    processed_dir,
    raw_dir,
    save_processed_csv,
    save_raw_json,
)

NAME = "crashes_pedcyclist"


def _fetch(cfg: Dict) -> pd.DataFrame:
    ds = cfg["datasets"][NAME]
    counties = cfg["counties"]["nc08"]
    years = cfg["crash_years"]["finalized_years"]

    county_list = ", ".join(f"'{c}'" for c in counties)
    year_list = ", ".join(str(y) for y in years)
    where = f"{ds['county_field']} IN ({county_list}) AND {ds['year_field']} IN ({year_list})"

    print(f"[{NAME}] querying {ds['service_url']}")
    print(f"[{NAME}] where={where}")
    features = fetch_arcgis_features(
        ds["service_url"],
        where=where,
        out_fields=",".join(ds["fields_used"]),
        page_size=ds["page_size"],
    )
    rdir = raw_dir(NAME)
    raw_path = save_raw_json(NAME, "nonmotorist_crashes_nc08_2021_2025.json", features)
    print(f"[{NAME}] saved {len(features)} raw records -> {raw_path}")

    return flatten_features(features)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Esri esriFieldTypeDate fields come back over REST as epoch MILLISECONDS
    # (UTC), not an ISO string -- pd.to_datetime needs unit="ms" or every date
    # silently collapses to ~1970-01-01 (a real bug caught by eyeballing the
    # first stats report; worth flagging since it's an easy mistake to repeat
    # in the other pipelines that also carry esriFieldTypeDate columns).
    df["CrashDate"] = pd.to_datetime(df.get("CrashDate"), unit="ms", errors="coerce")
    # Latitude/Longitude are already real fields on this service (no geometry
    # reprojection needed), but a couple of legacy records occasionally ship
    # null coordinates -- drop those for the *processed* (map-ready) copy; they
    # stay in the raw JSON untouched, per the provenance rule (raw = unfiltered).
    before = len(df)
    df = df.dropna(subset=["Latitude", "Longitude"])
    dropped = before - len(df)
    if dropped:
        print(f"[{NAME}] dropped {dropped} records with missing coordinates (kept in raw, not processed)")
    df = df.rename(columns={"Latitude": "lat", "Longitude": "lon"})
    # flatten_features() also derives _lon/_lat from the point geometry, which
    # duplicates the named Latitude/Longitude fields (same value, float-noise
    # apart) -- drop the redundant geometry-derived columns and keep the
    # named ones as the single source of truth for this table.
    df = df.drop(columns=["_lon", "_lat"], errors="ignore")
    return df


def main() -> None:
    cfg = load_data_config()
    raw_df = _fetch(cfg)
    clean_df = _clean(raw_df)

    out_path = save_processed_csv(NAME, "nonmotorist_crashes_nc08_2021_2025.csv", clean_df)
    print(f"[{NAME}] saved {len(clean_df)} processed records -> {out_path}")

    county_counts = clean_df["County"].value_counts().to_dict()
    type_counts = clean_df["NM_Type"].value_counts().to_dict()
    year_counts = clean_df["CrashYear"].value_counts().sort_index().to_dict()
    missing_pct = {
        col: round(100.0 * clean_df[col].isna().mean(), 2)
        for col in ["SpeedLimit", "RdClass", "LightCond", "Weather", "NM_Age", "NM_Sex"]
        if col in clean_df.columns
    }

    stats = {
        "raw_records": len(raw_df),
        "processed_records": len(clean_df),
        "date_range": f"{clean_df['CrashDate'].min()} -> {clean_df['CrashDate'].max()}",
        "county_breakdown": county_counts,
        "nonmotorist_type_breakdown": type_counts,
        "year_breakdown": year_counts,
        "missing_field_pct": missing_pct,
    }
    print_stats_report(NAME, stats)


if __name__ == "__main__":
    main()
