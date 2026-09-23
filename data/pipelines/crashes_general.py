"""General (all-vehicle) crash pipeline -- NCDOT Statewide Crash Table.

Run: python -m data.pipelines.crashes_general

This is the denominator/context table: every reportable motor-vehicle crash
in NC-08, not just ped/cyclist ones (that's crashes_pedcyclist.py). It also
carries PedInvolved/BikeInvolved flags and Ped/Bike fatality+injury counts, so
it doubles as an independent cross-check on the ped/cyclist pipeline's counts
(the two sources are built by NCDOT from different extraction paths --
StatewideCrashTable is a broader "all crashes" export, NonMotoristCrashes is
purpose-built for non-motorist analysis -- so they won't match exactly, but
should be in the same ballpark for PedInvolved='Y' rows. Any large divergence
is worth investigating before trusting either number on the dashboard).

WHY the FeatureServer's layer index 3 specifically: StatewideCrashTable is
published as an exported CSV wrapped in a FeatureServer with ONE table (no
map layers) -- `.../FeatureServer?f=json` lists it as
`tables: [(3, "export - Statewide Crash Table.csv")]`, confirmed live. There
is no layer 0 on this service; querying /FeatureServer/0 (the usual default)
returns an empty/None response, which is why the URL below is pinned to /3
explicitly rather than guessed.

WHY years 2021-2025: see configs/data.yaml crash_years comment. 2026's NC-08
record count (37,675) is roughly 60% of a full finalized year -- consistent
with 2026 still being a partial year as of the September 2026 pull -- so it's
excluded.
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

NAME = "crashes_general"


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
        return_geometry=False,  # this is a table (no Shape field) -- geometry would just be dropped anyway
    )
    raw_path = save_raw_json(NAME, "statewide_crash_table_nc08_2021_2025.json", features)
    print(f"[{NAME}] saved {len(features)} raw records -> {raw_path}")

    return flatten_features(features)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Esri esriFieldTypeDate -> epoch milliseconds; see crashes_pedcyclist.py
    # for why unit="ms" is required here (bug caught there, fixed everywhere).
    df["Date"] = pd.to_datetime(df.get("Date"), unit="ms", errors="coerce")
    for flag_col in ("PedInvolved", "BikeInvolved"):
        if flag_col in df.columns:
            df[flag_col] = df[flag_col].fillna("N")
    return df


def main() -> None:
    cfg = load_data_config()
    raw_df = _fetch(cfg)
    clean_df = _clean(raw_df)

    out_path = save_processed_csv(NAME, "statewide_crash_table_nc08_2021_2025.csv", clean_df)
    print(f"[{NAME}] saved {len(clean_df)} processed records -> {out_path}")

    county_counts = clean_df["County"].value_counts().to_dict()
    year_counts = clean_df["Year"].value_counts().sort_index().to_dict()
    severity_counts = clean_df["CrshSeverity"].value_counts().to_dict()
    ped_involved = int((clean_df.get("PedInvolved") == "Y").sum()) if "PedInvolved" in clean_df else None
    bike_involved = int((clean_df.get("BikeInvolved") == "Y").sum()) if "BikeInvolved" in clean_df else None
    missing_pct = {
        col: round(100.0 * clean_df[col].isna().mean(), 2)
        for col in ["CrshSeverity", "CrashType", "City", "SpeedRelated"]
        if col in clean_df.columns
    }

    stats = {
        "raw_records": len(raw_df),
        "processed_records": len(clean_df),
        "date_range": f"{clean_df['Date'].min()} -> {clean_df['Date'].max()}",
        "county_breakdown": county_counts,
        "year_breakdown": year_counts,
        "severity_breakdown": severity_counts,
        "ped_involved_crashes": ped_involved,
        "bike_involved_crashes": bike_involved,
        "cross_check_note": (
            "compare ped_involved_crashes/bike_involved_crashes above against "
            "crashes_pedcyclist.py's total record count -- both come from NCDOT "
            "but via different extraction pipelines, so they will NOT match "
            "exactly; large divergence is worth investigating, not averaging away."
        ),
        "missing_field_pct": missing_pct,
    }
    print_stats_report(NAME, stats)


if __name__ == "__main__":
    main()
