"""Evaluate a trained RiskGNN checkpoint and emit the full per-segment output
table the rest of the pipeline (explainer, risk-exposure, disparity,
priority list, dashboard) consumes.

Run: python -m models.gnn.evaluate --checkpoint models/gnn/checkpoints/risk_gnn_best.pt
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd
import torch

from ..risk.risk_exposure import compute_risk_exposure
from ..risk.targets import compute_data_density_flag
from .risk_gnn import RiskGNN
from .train import FEATURE_GROUPS, _build_modalities


def load_checkpoint(path: str, device: torch.device):
    ck = torch.load(path, map_location=device, weights_only=False)
    return ck


def run_inference(checkpoint_path: str, features_path: str, adjacency_path: str,
                  w_ems: float = 1.0) -> pd.DataFrame:
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

    with torch.no_grad():
        pred_rate = torch.nn.functional.softplus(model(modalities)).numpy()  # [N]

    segments = segments.copy()
    segments["risk_score"] = pred_rate
    segments["data_density_flag"] = compute_data_density_flag(
        segments, cfg.get("min_county_incidents", 15))

    ems_dist = segments["ems_distance_m"].where(
        segments["ems_distance_m"].notna(), None).tolist() if "ems_distance_m" in segments else [None] * len(segments)
    exposure = compute_risk_exposure(pred_rate, ems_dist, w_ems=w_ems)
    for k, v in exposure.items():
        segments[k] = v

    return segments


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default="models/gnn/checkpoints/risk_gnn_best.pt")
    ap.add_argument("--features", default="data/processed/nc08_segments.parquet")
    ap.add_argument("--adjacency", default="data/processed/nc08_adjacency.npy")
    ap.add_argument("--w-ems", type=float, default=1.0)
    ap.add_argument("--out", default="evaluation/results/segment_scores.parquet")
    args = ap.parse_args()

    out_df = run_inference(args.checkpoint, args.features, args.adjacency, args.w_ems)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    out_df.to_parquet(args.out)

    summary = {
        "n_segments": int(len(out_df)),
        "mean_risk_score": float(out_df["risk_score"].mean()),
        "mean_risk_exposure": float(out_df["risk_exposure"].mean()),
        "pct_low_confidence": float(out_df["data_density_flag"].mean() * 100.0),
        "pct_ems_distance_available": float(out_df["ems_distance_available"].mean() * 100.0),
    }
    print("[evaluate]", json.dumps(summary, indent=2))
    with open("evaluation/results/segment_scores_summary.json", "w") as f:
        json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
