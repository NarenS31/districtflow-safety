"""Shared config/IO/ArcGIS-REST helpers for all DistrictFlow Safety data pipelines.

Every pipeline under data/pipelines/ imports from here so (a) the NCDOT/NC
OneMap ArcGIS pagination logic exists in exactly one place, (b) raw/processed
output always lands in the same layout, and (c) every script prints a stats
report in the same shape. This mirrors the xtraffic reference project's
utils/io_utils.py pattern (load_data_config / raw_dir / processed_dir /
print_stats_report), adapted for Esri FeatureServer sources instead of Socrata.

Python 3.9 compatible: typing.Optional/Dict/List, no `X | Y` unions.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import yaml

# Resolve paths relative to the repo root (parent of this utils/ directory),
# NOT the process cwd -- so `python -m data.pipelines.foo` works the same
# whether it's invoked from the repo root or anywhere else.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)

DEFAULT_CONFIG_PATH = os.path.join(_REPO_ROOT, "configs", "data.yaml")


def load_data_config(path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def raw_dir(name: str) -> str:
    path = os.path.join(_REPO_ROOT, "data", "raw", name)
    os.makedirs(path, exist_ok=True)
    return path


def processed_dir(name: str) -> str:
    path = os.path.join(_REPO_ROOT, "data", "processed", name)
    os.makedirs(path, exist_ok=True)
    return path


def save_raw_json(name: str, filename: str, records: List[Dict[str, Any]]) -> str:
    """Dump the untouched ArcGIS feature attribute dicts. This IS the raw layer
    (provenance: exactly what the API returned, no cleaning), so a reviewer can
    always trace a dashboard number back to an unmodified server response.
    """
    path = os.path.join(raw_dir(name), filename)
    with open(path, "w") as f:
        json.dump(records, f)
    return path


def save_processed_csv(name: str, filename: str, df: pd.DataFrame) -> str:
    path = os.path.join(processed_dir(name), filename)
    df.to_csv(path, index=False)
    return path


def print_stats_report(title: str, stats: Dict[str, Any]) -> None:
    print("=" * 72)
    print(f"STATS REPORT: {title}")
    print("=" * 72)
    for k, v in stats.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"{k}: {v}")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Esri ArcGIS REST FeatureServer/MapServer pagination
# ---------------------------------------------------------------------------
def fetch_arcgis_features(
    layer_url: str,
    where: str = "1=1",
    out_fields: str = "*",
    geometry: Optional[str] = None,
    geometry_type: str = "esriGeometryEnvelope",
    in_sr: int = 4326,
    spatial_rel: str = "esriSpatialRelIntersects",
    out_sr: int = 4326,
    return_geometry: bool = True,
    page_size: int = 2000,
    max_records: Optional[int] = None,
    timeout: int = 60,
    verify_ssl: bool = True,
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """Page through an Esri ArcGIS REST layer's /query endpoint via resultOffset.

    WHY resultOffset pagination: every NCDOT/NC-OneMap layer used in this
    project caps a single request at page_size records (their maxRecordCount,
    confirmed live at 2000 for each service in DATA_SOURCES.md). We loop,
    advancing resultOffset, until a page comes back shorter than page_size
    (the standard "last page" signal) or max_records is reached.

    WHY a retry loop: these are shared state-government ArcGIS Online/on-prem
    servers -- transient 5xx/timeouts are common under load, not a sign the
    endpoint is gone. We retry with linear backoff before giving up loudly.

    Returns the raw list of Esri feature dicts ({"attributes": {...},
    "geometry": {...}}), unflattened -- see flatten_features() below.
    """
    all_features: List[Dict[str, Any]] = []
    offset = 0
    while True:
        params: Dict[str, Any] = {
            "where": where,
            "outFields": out_fields,
            "outSR": out_sr,
            "returnGeometry": str(return_geometry).lower(),
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "f": "json",
        }
        if geometry is not None:
            params.update(
                {
                    "geometry": geometry,
                    "geometryType": geometry_type,
                    "inSR": in_sr,
                    "spatialRel": spatial_rel,
                }
            )

        last_err = None
        data = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(f"{layer_url}/query", params=params, timeout=timeout, verify=verify_ssl)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:  # noqa: BLE001 -- deliberately broad, we retry any transient failure
                last_err = e
                print(f"  [arcgis] attempt {attempt}/{max_retries} failed ({e}); retrying...")
                time.sleep(2 * attempt)
        if data is None:
            raise RuntimeError(f"[arcgis] giving up on {layer_url} at offset {offset}: {last_err}")

        if "error" in data:
            raise RuntimeError(f"[arcgis] server error from {layer_url}: {data['error']}")

        feats = data.get("features", [])
        all_features.extend(feats)
        print(f"  [arcgis] {layer_url.split('/services/')[-1]}: +{len(feats)} (total {len(all_features)}, offset {offset})")

        if len(feats) < page_size:
            break
        offset += page_size
        if max_records is not None and len(all_features) >= max_records:
            all_features = all_features[:max_records]
            break
    return all_features


def flatten_features(features: List[Dict[str, Any]]) -> pd.DataFrame:
    """Attributes dict -> DataFrame row, plus a representative _lon/_lat column
    derived from the geometry (point x/y directly; polyline = vertex-average
    midpoint, see geo_utils.polyline_midpoint). Geometry-less table services
    (e.g. StatewideCrashTable, which is an exported CSV table with no Shape
    field) simply get no _lon/_lat columns.
    """
    from utils.geo_utils import polyline_midpoint  # local import: keep io_utils geometry-agnostic by default

    rows = []
    for feat in features:
        row = dict(feat.get("attributes", {}))
        geom = feat.get("geometry")
        if geom:
            if "x" in geom and "y" in geom:
                row["_lon"], row["_lat"] = geom["x"], geom["y"]
            elif "paths" in geom:
                row["_lon"], row["_lat"] = polyline_midpoint(geom["paths"])
        rows.append(row)
    return pd.DataFrame(rows)
