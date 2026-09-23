"""Export everything the static dashboard needs as plain JSON/GeoJSON files.

WHY STATIC, NOT A LIVE BACKEND: a Congressional App Challenge submission needs
a URL that reliably loads for judges with zero server/runtime risk. Every
number the dashboard shows is computed here, once, from the real trained
model + real data, and written to dashboard/public/data/ as build artifacts.
The counterfactual "what-if" layer (brief section 7) is the one feature that
looks like it needs live inference — it doesn't: we PRECOMPUTE every
(segment, intervention) combination for the segments a user can actually
click on (the Top-N priority list) and let the frontend look up the result.
This is still real GNN inference with real message passing (models/risk/
counterfactual.py), just computed at build time instead of request time.

Run: python -m evaluation.export_dashboard_data --n-priority 25
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd
import torch

from evaluation.priority_list import build_priority_list
from models.gnn.evaluate import load_checkpoint
from models.gnn.risk_gnn import RiskGNN
from models.gnn.train import _build_modalities
from models.risk.counterfactual import INTERVENTIONS, run_counterfactual
from models.risk.disparity import disparity_gap, disparity_summary

OUT_DIR = "dashboard/public/data"


def _df_records(df: pd.DataFrame) -> list:
    # NaN isn't valid JSON — convert to None so the frontend gets a clean
    # "missing" value instead of a parse error or a silently-wrong 'NaN' string.
    return json.loads(df.where(pd.notnull(df), None).to_json(orient="records"))


def export_segments(scores: pd.DataFrame) -> None:
    """A GeoJSON FeatureCollection IF lat/lon geometry columns are present,
    else a plain records JSON — the map component checks for `type` on load
    and falls back to a list-based render if geometry isn't there yet (real
    ISRN/OSM geometry lands via data/pipelines; this export never fabricates
    coordinates it doesn't have)."""
    has_geom = {"start_lat", "start_lon", "end_lat", "end_lon"}.issubset(scores.columns)
    if has_geom:
        features = []
        for _, row in scores.iterrows():
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[row["start_lon"], row["start_lat"]],
                                    [row["end_lon"], row["end_lat"]]],
                },
                "properties": {
                    "segment_id": row.get("segment_id"),
                    "segment_name": row.get("segment_name"),
                    "county": row.get("county"),
                    "rural_flag": bool(row.get("rural_flag", False)),
                    "risk_score": float(row["risk_score"]),
                    "risk_exposure": float(row["risk_exposure"]),
                    "data_density_flag": bool(row.get("data_density_flag", False)),
                    "ems_distance_available": bool(row.get("ems_distance_available", False)),
                },
            })
        payload = {"type": "FeatureCollection", "features": features}
    else:
        payload = {"type": "RecordList", "note": "No segment geometry available yet — "
                  "data/pipelines/isrn_roads.py has not been integrated. See "
                  "docs/LIMITATIONS.md.", "records": _df_records(scores)}
    with open(os.path.join(OUT_DIR, "segments.json"), "w") as f:
        json.dump(payload, f)


def export_priority_and_counterfactuals(checkpoint_path: str, features_path: str,
                                        adjacency_path: str, scores_path: str,
                                        n: int) -> None:
    priority = build_priority_list(scores_path, checkpoint_path, features_path, n)
    with open(os.path.join(OUT_DIR, "priority_list.json"), "w") as f:
        json.dump(priority, f, indent=2)

    device = torch.device("cpu")
    ck = load_checkpoint(checkpoint_path, device)
    cfg = ck["config"]
    segments = pd.read_parquet(features_path)
    adjacency = np.load(adjacency_path)
    modalities, feature_names = _build_modalities(segments, device)

    model = RiskGNN(
        num_segments=ck["n_segments"],
        physical_adj=torch.tensor(adjacency, dtype=torch.float32),
        modality_dims=ck["modality_dims"],
        hidden_channels=cfg["model"]["hidden_channels"],
        n_blocks=cfg["model"]["n_blocks"],
        embed_dim=cfg["model"]["embed_dim"],
        gcn_order=cfg["model"]["gcn_order"],
        dropout=cfg["model"]["dropout"],
        use_semantic=cfg["model"].get("use_semantic", True),
    )
    model.load_state_dict(ck["model_state"])
    model.eval()

    seg_ids = segments["segment_id"].tolist() if "segment_id" in segments.columns else list(range(len(segments)))
    cf_out = {}
    for entry in priority:
        idx = seg_ids.index(entry["segment_id"])
        cf_out[entry["segment_id"]] = {}
        for key in INTERVENTIONS:
            cf_out[entry["segment_id"]][key] = run_counterfactual(
                model, modalities, feature_names, adjacency, idx, key)
    with open(os.path.join(OUT_DIR, "counterfactuals.json"), "w") as f:
        json.dump(cf_out, f, indent=2)


def export_disparity(scores: pd.DataFrame) -> None:
    summary = disparity_summary(scores)
    gap = disparity_gap(summary)
    out = {
        "by_county": _df_records(summary["by_county"]),
        "by_rural_suburban": _df_records(summary["by_rural_suburban"]),
        "by_county_rural": _df_records(summary["by_county_rural"]),
        "gap": gap,
    }
    with open(os.path.join(OUT_DIR, "disparity.json"), "w") as f:
        json.dump(out, f, indent=2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", default="evaluation/results/segment_scores.parquet")
    ap.add_argument("--checkpoint", default="models/gnn/checkpoints/risk_gnn_best.pt")
    ap.add_argument("--features", default="data/processed/nc08_segments.parquet")
    ap.add_argument("--adjacency", default="data/processed/nc08_adjacency.npy")
    ap.add_argument("--n-priority", type=int, default=25)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    scores = pd.read_parquet(args.scores)

    export_segments(scores)
    export_disparity(scores)
    export_priority_and_counterfactuals(args.checkpoint, args.features,
                                        args.adjacency, args.scores, args.n_priority)

    with open(os.path.join(OUT_DIR, "meta.json"), "w") as f:
        json.dump({
            "n_segments": int(len(scores)),
            "generated_from": "evaluation/export_dashboard_data.py",
        }, f, indent=2)
    print(f"[export] wrote dashboard data to {OUT_DIR}/")


if __name__ == "__main__":
    main()
