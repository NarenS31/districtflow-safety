"""Fire + EMS station locations for NC-08 -- two NC OneMap statewide layers.

Run: python -m data.pipelines.ems_fire_stations

Per the task spec: check NC OneMap first for a statewide fire/EMS layer before
resorting to a manual per-county TODO. Two SEPARATE NC OneMap-hosted layers
were found and confirmed live with real, non-empty NC-08 coverage in ALL 8
counties (record counts printed by this script's stats report; the full
per-county breakdown is also written out to EMS_STATIONS_TODO.md so it's
readable without running code):

  - NC Fire Stations (NC Office of State Fire Marshal, via NC OneMap):
    statewide inventory of active fire stations, required under 11 NCAC
    05A.0901's "9S fire rating program".
  - NC1Map_Emergency_Services, layer 0 "Emergency Medical Services" (NC
    OneMap): statewide inventory of EMS/ambulance bases (private + government).

These are two DIFFERENT source datasets (different maintaining agency, different
schema) merged here into one processed output with a `station_type` column --
NOT one dataset silently relabeled as two. Raw JSON is kept separate per
source (data/raw/ems_fire_stations/fire_raw.json and ems_raw.json) so the
provenance of every row is traceable to its original service.

WHY no per-county manual-TODO fallback was needed: both layers came back with
real records in every one of the 8 counties on the live county-grouped count
check performed during development (Anson/Montgomery/Richmond/Stanly all have
real, if small, station counts -- not zero, not missing). See
EMS_STATIONS_TODO.md for the exact numbers and a caveat about small-county
undercounting risk (volunteer/rural departments are more likely to be
mis-recorded or stale in ANY statewide inventory than urban ones).
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

NAME = "ems_fire_stations"


def _fetch_fire(cfg: Dict) -> pd.DataFrame:
    ds = cfg["datasets"]["ems_fire_stations"]["fire"]
    counties = cfg["counties"]["nc08"]
    county_list = ", ".join(f"'{c}'" for c in counties)
    where = f"{ds['county_field']} IN ({county_list})"

    print(f"[{NAME}] (fire) querying {ds['service_url']}")
    features = fetch_arcgis_features(ds["service_url"], where=where, out_fields="*", page_size=2000)
    save_raw_json(NAME, "fire_raw.json", features)
    df = flatten_features(features)
    df["station_type"] = "fire"
    df["name"] = df.get("DEPT_NAME")
    df["county"] = df.get("COUNTY")
    df["lat"] = df.get("LATITUDE", df.get("_lat"))
    df["lon"] = df.get("LONGITUDE", df.get("_lon"))
    df["address"] = df.get("STATION_ADDRESS")
    print(f"[{NAME}] (fire) {len(df)} records")
    return df


def _fetch_ems(cfg: Dict) -> pd.DataFrame:
    ds = cfg["datasets"]["ems_fire_stations"]["ems"]
    counties_upper = cfg["counties"]["nc08_upper"]
    county_list = ", ".join(f"'{c}'" for c in counties_upper)
    where = f"{ds['county_field']} IN ({county_list})"

    print(f"[{NAME}] (ems) querying {ds['service_url']}")
    # This layer's native SR is NC State Plane (meters, wkid 32119) -- its raw
    # x/y attribute columns are in that projection, NOT lat/lon. We request
    # outSR=4326 so fetch_arcgis_features's returned geometry.x/y come back
    # reprojected to WGS84 degrees; flatten_features reads geometry, not the
    # native x/y attribute columns, so this is handled automatically -- but
    # it's exactly the kind of silent-wrong-units bug worth flagging loudly.
    features = fetch_arcgis_features(ds["service_url"], where=where, out_fields="*", page_size=2000, out_sr=4326)
    save_raw_json(NAME, "ems_raw.json", features)
    df = flatten_features(features)
    df["station_type"] = "ems"
    df["name"] = df.get("name")
    df["county"] = df.get("county").str.title() if "county" in df.columns else None
    df["lat"] = df.get("_lat")
    df["lon"] = df.get("_lon")
    df["address"] = df.get("address")
    print(f"[{NAME}] (ems) {len(df)} records")
    return df


def main() -> None:
    cfg = load_data_config()
    fire_df = _fetch_fire(cfg)
    ems_df = _fetch_ems(cfg)

    keep_cols = ["station_type", "name", "county", "address", "city", "lat", "lon"]
    fire_out = fire_df.reindex(columns=[c for c in keep_cols if c in fire_df.columns] + ["FD_ID", "STATION_NUMBER"])
    ems_out = ems_df.reindex(columns=[c for c in keep_cols if c in ems_df.columns] + ["fips", "type", "numabul", "totalpers"])

    combined = pd.concat([fire_out, ems_out], ignore_index=True, sort=False)
    out_path = save_processed_csv(NAME, "fire_ems_stations_nc08.csv", combined)
    print(f"[{NAME}] saved {len(combined)} combined processed records -> {out_path}")

    county_by_type = combined.groupby(["county", "station_type"]).size().unstack(fill_value=0).to_dict("index")
    missing_pct = {
        col: round(100.0 * combined[col].isna().mean(), 2)
        for col in ["lat", "lon", "address"]
        if col in combined.columns
    }

    stats = {
        "fire_stations_total": len(fire_df),
        "ems_stations_total": len(ems_df),
        "combined_total": len(combined),
        "county_by_type": county_by_type,
        "missing_field_pct": missing_pct,
        "sources": {
            "fire": cfg["datasets"]["ems_fire_stations"]["fire"]["name"],
            "ems": cfg["datasets"]["ems_fire_stations"]["ems"]["name"],
        },
        "note": "see EMS_STATIONS_TODO.md for the per-county coverage table and honest caveats",
    }
    print_stats_report(NAME, stats)


if __name__ == "__main__":
    main()
