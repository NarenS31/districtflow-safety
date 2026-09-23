"""Train RiskGNN on the assembled NC-08 segment feature table.

PROVENANCE: config-driven, seeded, masked-loss discipline ported from
XTraffic's models/gnn/train.py (Adam + gradient clipping + early stopping +
per-epoch CSV logging), adapted to a transductive single-graph regression
task with a Poisson loss instead of masked MAE (see models/risk/targets.py
for why Poisson: crash counts are count data with AADT as exposure, not a
continuous measurement).

Run: python -m models.gnn.train --config configs/model.yaml
"""
from __future__ import annotations

import argparse
import csv
import os
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import yaml

from ..risk.targets import build_target, compute_data_density_flag, target_summary
from utils.graph_utils import chronological_or_spatial_split
from .risk_gnn import RiskGNN

FEATURE_GROUPS = {
    "infrastructure": ["speed_limit_mph", "lane_count", "road_classification",
                       "intersection_density", "crosswalk_present",
                       "sidewalk_coverage", "lighting_coverage"],
    "aadt": ["aadt_normalized"],
    "crash_history": ["pedcyclist_incident_count_5yr", "general_crash_count_5yr"],
    "context": ["rural_flag", "county_code"],
    "ems_access": ["ems_distance_m"],
}


def _build_modalities(segments: pd.DataFrame, device: torch.device
                      ) -> Tuple[Dict[str, torch.Tensor], Dict[str, list]]:
    """Split the flat feature table into the modality tensors HeteroFusion
    expects, per docs/FEATURES.md. A modality is OMITTED ENTIRELY (not
    zero-filled) if none of its columns exist in `segments` — that's the
    "whole modality missing" case models/gnn/risk_gnn.py's HeteroFusion
    tolerates by design (e.g. no AADT service reachable at all)."""
    modalities: Dict[str, torch.Tensor] = {}
    feature_names: Dict[str, list] = {}
    for name, cols in FEATURE_GROUPS.items():
        present = [c for c in cols if c in segments.columns]
        if not present:
            continue
        arr = segments[present].fillna(0.0).to_numpy(dtype=np.float32)
        modalities[name] = torch.tensor(arr, device=device)
        feature_names[name] = present
    return modalities, feature_names


def masked_poisson_nll(pred_rate: torch.Tensor, counts: torch.Tensor,
                       log_offset: torch.Tensor) -> torch.Tensor:
    """Poisson NLL with an AADT log-offset (targets.py's rationale): the
    model predicts log(lambda) implicitly via softplus(pred_rate) as lambda,
    and log_offset shifts expected counts by traffic exposure so the model
    isn't rewarded for just learning "high AADT -> more crashes" (already
    known) instead of the genuinely risk-relevant signal.
    """
    log_lambda = torch.log(torch.nn.functional.softplus(pred_rate) + 1e-6) + log_offset
    lam = torch.exp(log_lambda)
    # Poisson NLL: lambda - k*log(lambda) + log(k!); the log(k!) term is
    # constant w.r.t. the model and dropped (doesn't affect gradients).
    nll = lam - counts * log_lambda
    return nll.mean()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/model.yaml")
    ap.add_argument("--features", default="data/processed/nc08_segments.parquet")
    ap.add_argument("--adjacency", default="data/processed/nc08_adjacency.npy")
    args = ap.parse_args()

    with open(args.config) as f:
        cfg = yaml.safe_load(f)

    torch.manual_seed(cfg["seed"])
    np.random.seed(cfg["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if not os.path.exists(args.features):
        raise FileNotFoundError(
            f"{args.features} not found. Run data/pipelines/assemble_features.py "
            f"first (needs the raw pulls from data/pipelines/*.py) — this "
            f"training script never fabricates its own input.")

    segments = pd.read_parquet(args.features)
    adjacency = np.load(args.adjacency)
    print("[train] target summary:", target_summary(segments))

    segments["data_density_flag"] = compute_data_density_flag(
        segments, cfg.get("min_county_incidents", 15))
    counts = build_target(segments)
    aadt_raw = segments["aadt_raw"].fillna(1.0).clip(lower=1.0).to_numpy(dtype=np.float64)
    log_offset_all = np.log(aadt_raw)

    modalities, feature_names = _build_modalities(segments, device)
    n = len(segments)
    train_idx, val_idx, test_idx = chronological_or_spatial_split(
        n, cfg["train_ratio"], cfg["val_ratio"], seed=cfg["seed"])

    counts_t = torch.tensor(counts, dtype=torch.float32, device=device)
    log_offset_t = torch.tensor(log_offset_all, dtype=torch.float32, device=device)

    model = RiskGNN(
        num_segments=n,
        physical_adj=torch.tensor(adjacency, dtype=torch.float32),
        modality_dims={k: v.shape[1] for k, v in modalities.items()},
        hidden_channels=cfg["model"]["hidden_channels"],
        n_blocks=cfg["model"]["n_blocks"],
        embed_dim=cfg["model"]["embed_dim"],
        gcn_order=cfg["model"]["gcn_order"],
        dropout=cfg["model"]["dropout"],
        use_semantic=cfg["model"].get("use_semantic", True),
    ).to(device)

    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"])
    best_val = float("inf")
    os.makedirs("evaluation/results", exist_ok=True)
    log_path = "evaluation/results/train_log.csv"
    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["epoch", "train_nll", "val_nll", "alpha"])

        patience, bad_epochs = cfg.get("early_stop_patience", 15), 0
        for epoch in range(cfg["epochs"]):
            model.train()
            opt.zero_grad()
            pred = model(modalities)  # [N]
            loss = masked_poisson_nll(pred[train_idx], counts_t[train_idx],
                                      log_offset_t[train_idx])
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.get("grad_clip", 5.0))
            opt.step()

            model.eval()
            with torch.no_grad():
                pred_eval = model(modalities)
                val_loss = masked_poisson_nll(pred_eval[val_idx], counts_t[val_idx],
                                              log_offset_t[val_idx])
            writer.writerow([epoch, float(loss.item()), float(val_loss.item()),
                            model.current_alpha()])
            f.flush()

            if val_loss.item() < best_val:
                best_val = val_loss.item()
                bad_epochs = 0
                os.makedirs("models/gnn/checkpoints", exist_ok=True)
                torch.save({
                    "model_state": model.state_dict(),
                    "config": cfg,
                    "modality_dims": {k: v.shape[1] for k, v in modalities.items()},
                    "n_segments": n,
                    "epoch": epoch,
                }, "models/gnn/checkpoints/risk_gnn_best.pt")
            else:
                bad_epochs += 1
                if bad_epochs >= patience:
                    print(f"[train] early stop at epoch {epoch} (val_nll={val_loss:.4f})")
                    break

            if epoch % 10 == 0:
                print(f"[train] epoch {epoch} train_nll={loss.item():.4f} "
                     f"val_nll={val_loss.item():.4f} alpha={model.current_alpha():.4f}")

    print(f"[train] best val_nll={best_val:.4f}. Checkpoint: "
         f"models/gnn/checkpoints/risk_gnn_best.pt. Log: {log_path}")


if __name__ == "__main__":
    main()
