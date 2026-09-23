"""NCDOT TIMS active-incident LIVE overlay -- thin puller, not a historical pipeline.

Run: python -m data.pipelines.tims_overlay

WHAT THIS IS: a "what's happening on NC-08 roads right now" overlay --
active/current lane closures, crashes-in-progress, weather-related restrictions,
etc. -- for the dashboard's live-conditions layer. It is explicitly NOT meant
to build up historical training data: TIMS is a snapshot of currently-open
events, not an archive. NCDOT does publish NCDOT_TIMSIncidentsHistory as a
separate service, but per the task scope this pipeline stays a thin,
run-it-when-you-need-it puller of current conditions only -- it overwrites its
single output file on every run rather than appending, so it can never
accidentally accumulate into a pretend historical dataset.

WHY this endpoint over the DriveNC.gov REST API directly: both are confirmed
live and describe the same underlying incident feed. eapps.ncdot.gov (the
legacy DriveNC API host) now redirects with a deprecation notice pointing to
https://www.drivenc.gov/help/endpoint/event (confirmed live 2026-09-22,
returns a JSON message rather than incident data at the un-authenticated
root -- DriveNC.gov's documented API needs following their doc for exact
params/auth). NCDOT_TIMS_Incidents, hosted on NCDOT's own public ArcGIS Online
org, returns the same class of incident data (Road, Reason, Condition, Detour,
EventType, StartDateTime/EndDateTime, CountyName, lat/lon, DriveNCLink back to
the DriveNC.gov page for that event) via a stable, unauthenticated, queryable
FeatureServer -- so it's used as the primary puller here, with the DriveNC.gov
doc URL kept in configs/data.yaml as the documented fallback path if NCDOT
ever retires this ArcGIS mirror.

Run this on a schedule (e.g. a cron hitting `python -m data.pipelines.tims_overlay`
every few minutes) if the dashboard wants a near-real-time overlay; each run
is a fresh, complete snapshot, not a delta.
"""
from __future__ import annotations

from datetime import datetime, timezone
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

NAME = "tims_overlay"


def _fetch(cfg: Dict) -> pd.DataFrame:
    ds = cfg["datasets"]["tims_incidents"]
    counties = cfg["counties"]["nc08"]
    county_list = ", ".join(f"'{c}'" for c in counties)
    where = f"{ds['county_field']} IN ({county_list})"

    print(f"[{NAME}] querying {ds['service_url']} (LIVE snapshot, not historical)")
    print(f"[{NAME}] where={where}")
    features = fetch_arcgis_features(
        ds["service_url"],
        where=where,
        out_fields="*",
        page_size=ds["page_size"],
    )
    # Single overwritten file (no timestamp in the name) -- deliberately NOT
    # accumulating snapshots into a historical archive; see module docstring.
    raw_path = save_raw_json(NAME, "tims_incidents_nc08_current.json", features)
    print(f"[{NAME}] saved {len(features)} raw records (current snapshot) -> {raw_path}")

    return flatten_features(features)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    for col in ("StartDateTime", "EndDateTime", "LastUpdateDateTime"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], unit="ms", errors="coerce")
    return df


def main() -> None:
    cfg = load_data_config()
    pulled_at = datetime.now(timezone.utc).isoformat()
    raw_df = _fetch(cfg)
    clean_df = _clean(raw_df)

    out_path = save_processed_csv(NAME, "tims_incidents_nc08_current.csv", clean_df)
    print(f"[{NAME}] saved {len(clean_df)} processed records -> {out_path}")

    if clean_df.empty:
        stats = {
            "pulled_at_utc": pulled_at,
            "active_incidents_nc08": 0,
            "note": "zero active incidents in NC-08 right now -- this is a normal, valid snapshot, not a fetch failure (see raw JSON for the empty-but-successful response)",
        }
    else:
        county_counts = clean_df["CountyName"].value_counts().to_dict()
        type_counts = clean_df["EventType"].value_counts(dropna=False).to_dict()
        full_closures = int((clean_df.get("IsFullClosure") == "Yes").sum()) if "IsFullClosure" in clean_df else None
        missing_pct = {
            col: round(100.0 * clean_df[col].isna().mean(), 2)
            for col in ["Reason", "Condition", "Detour", "EndDateTime"]
            if col in clean_df.columns
        }
        stats = {
            "pulled_at_utc": pulled_at,
            "active_incidents_nc08": len(clean_df),
            "county_breakdown": county_counts,
            "event_type_breakdown": type_counts,
            "full_closures": full_closures,
            "missing_field_pct": missing_pct,
            "note": "LIVE snapshot only -- rerun this script to refresh, do not treat as a growing historical dataset",
        }
    print_stats_report(NAME, stats)


if __name__ == "__main__":
    main()
