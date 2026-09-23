"""Base road-graph pipeline -- NCDOT Integrated Statewide Road Network (ISRN).

Run: python -m data.pipelines.isrn_roads

NCDOT's road-characteristics extract, generated from their Esri Roads &
Highways system (which IS the ISRN under the hood -- Roads & Highways is
Esri's linear-referencing product, and this quarterly export is NCDOT's
published-attributes view of it). Each record is a road segment, split
wherever any attribute (speed limit, lane count, surface type, ...) changes
along a route -- this is the base graph the dashboard's exposure model sits
on top of (crashes and AADT both get related back to a segment on this
network).

WHY this endpoint and not a generically-named "ISRN" service: no service
literally named "ISRN" exists in NCDOT's public ArcGIS Online org (the 993-
service list at services.arcgis.com/NuWFvHYDMVmmxMeM was grepped exhaustively
-- see DATA_SOURCES.md). NCDOT_RoadCharacteristicsQtr, hosted on NCDOT's own
gis11.services.ncdot.gov server (a different host from the AGOL org), is the
public-facing product of the ISRN and is what NC OneMap itself points to for
"NCDOT Road Characteristics" -- confirmed live with 107 fields including
SpeedLimit, ThruLaneCount, FuncClass, MaintCntyCode.

WHY filter by MaintCntyCode (not a bbox): this layer has an exact county
attribute with a documented domain (verified via the live field metadata,
values pinned in configs/data.yaml), so an attribute filter is both exact and
cheap -- no reason to fall back to an approximate bounding box the way
aadt.py has to (that service has no county field at all).

Note on record volume: NC-08's 8 counties carry ~158k road-characteristic
records (any point where an attribute changes creates a new segment row) --
this is a legitimately large, granular network, not a fetch bug.
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

NAME = "isrn_roads"

# Human-readable labels for NCDOT's FuncClass codes (FHWA functional
# classification scheme -- documented in NCDOT's Road Characteristics layer
# metadata / the standard HPMS functional-class codes). Used only to make the
# processed CSV and stats report legible; the raw numeric code is preserved.
FUNC_CLASS_LABELS = {
    1: "Interstate",
    2: "Other Freeway/Expressway",
    3: "Other Principal Arterial",
    4: "Minor Arterial",
    5: "Major Collector",
    6: "Minor Collector",
    7: "Local",
}


def _fetch(cfg: Dict) -> pd.DataFrame:
    ds = cfg["datasets"][NAME]
    county_codes = cfg["counties"]["nc08_maintcntycode"]

    code_list = ", ".join(f"'{c}'" for c in county_codes.values())
    where = f"{ds['county_field']} IN ({code_list})"

    print(f"[{NAME}] querying {ds['service_url']}")
    print(f"[{NAME}] where={where}")
    features = fetch_arcgis_features(
        ds["service_url"],
        where=where,
        out_fields=",".join(ds["fields_used"]),
        page_size=ds["page_size"],
        verify_ssl=ds.get("verify_ssl", True),
        return_geometry=True,  # polyline -- flatten_features derives a representative midpoint
    )
    raw_path = save_raw_json(NAME, "road_characteristics_nc08.json", features)
    print(f"[{NAME}] saved {len(features)} raw records -> {raw_path}")

    return flatten_features(features)


def _clean(df: pd.DataFrame, county_codes: Dict[str, str]) -> pd.DataFrame:
    df = df.copy()
    code_to_county = {v: k for k, v in county_codes.items()}
    df["County"] = df["MaintCntyCode"].map(code_to_county)
    df["FuncClassLabel"] = df["FuncClass"].map(FUNC_CLASS_LABELS)
    # DesignSpd/SpeedLimit of 0 in this dataset means "not recorded", not
    # "0 mph" (0 mph is not a real posted speed limit) -- treat as missing so
    # downstream exposure scoring doesn't silently divide/weight by zero.
    for col in ("SpeedLimit", "DesignSpd"):
        if col in df.columns:
            df.loc[df[col] == 0, col] = pd.NA
    return df


def main() -> None:
    cfg = load_data_config()
    county_codes = cfg["counties"]["nc08_maintcntycode"]
    raw_df = _fetch(cfg)
    clean_df = _clean(raw_df, county_codes)

    out_path = save_processed_csv(NAME, "road_characteristics_nc08.csv", clean_df)
    print(f"[{NAME}] saved {len(clean_df)} processed records -> {out_path}")

    county_counts = clean_df["County"].value_counts().to_dict()
    funcclass_counts = clean_df["FuncClassLabel"].value_counts(dropna=False).to_dict()
    missing_pct = {
        col: round(100.0 * clean_df[col].isna().mean(), 2)
        for col in ["SpeedLimit", "ThruLaneCount", "FuncClass", "SrfcType", "AADT"]
        if col in clean_df.columns
    }

    stats = {
        "raw_records": len(raw_df),
        "processed_records": len(clean_df),
        "county_breakdown": county_counts,
        "functional_class_breakdown": funcclass_counts,
        "missing_field_pct": missing_pct,
        "note": (
            "one row per road-characteristic segment (split wherever an "
            "attribute changes along a route), not one row per physical road"
        ),
    }
    print_stats_report(NAME, stats)


if __name__ == "__main__":
    main()
