"""Section 6 — the ranked Top-N highest-priority segments list.

Reads the per-segment output table (models/gnn/evaluate.py's output),
ranks by risk_exposure, and tags each of the top N with suggested
countermeasures derived from that segment's explainer feature attributions
(models/explainer/explain.py + models/risk/countermeasure.py). This is the
"actionable output" the dashboard's persistent Top-N panel renders directly.

Run: python -m evaluation.priority_list --n 25
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List

import pandas as pd
import torch

from models.explainer.explain import ExplanationBuilder
from models.gnn.evaluate import load_checkpoint
from models.gnn.risk_gnn import RiskGNN
from models.gnn.train import _build_modalities
from models.risk.countermeasure import suggest_countermeasures


def build_priority_list(scores_path: str, checkpoint_path: str,
                        features_path: str, n: int = 25) -> List[dict]:
    scores = pd.read_parquet(scores_path).reset_index(drop=True)
    top = scores.sort_values("risk_exposure", ascending=False).head(n)

    device = torch.device("cpu")
    ck = load_checkpoint(checkpoint_path, device)
    cfg = ck["config"]
    segments = pd.read_parquet(features_path)
    modalities, feature_names = _build_modalities(segments, device)

    model = RiskGNN(
        num_segments=ck["n_segments"],
        physical_adj=torch.zeros(ck["n_segments"], ck["n_segments"]),  # replaced below
        modality_dims=ck["modality_dims"],
        hidden_channels=cfg["model"]["hidden_channels"],
        n_blocks=cfg["model"]["n_blocks"],
        embed_dim=cfg["model"]["embed_dim"],
        gcn_order=cfg["model"]["gcn_order"],
        dropout=cfg["model"]["dropout"],
        use_semantic=cfg["model"].get("use_semantic", True),
    )
    # physical_adj is a registered buffer inside state_dict, so loading the
    # checkpoint restores the REAL adjacency the model was trained with —
    # the placeholder zeros above only satisfy the constructor's shape check.
    model.load_state_dict(ck["model_state"])
    model.eval()

    segment_meta = segments.to_dict("records")
    for i, rec in enumerate(segment_meta):
        rec["segment_id"] = rec.get("segment_id", str(i))
        rec["risk_exposure_score"] = float(scores.loc[i, "risk_exposure"])

    builder = ExplanationBuilder(
        model=model, modalities=modalities, feature_names=feature_names,
        segment_meta=segment_meta, checkpoint_path=checkpoint_path,
        top_k=6, epochs=150, confidence_runs=3,
    )

    priority: List[dict] = []
    for rank, (idx, row) in enumerate(top.iterrows(), start=1):
        exp = builder.explain_segment(int(idx), timestamp="priority_list_run")
        countermeasures = suggest_countermeasures(exp["top_features"])
        priority.append({
            "rank": rank,
            "segment_id": exp["segment"]["segment_id"],
            "segment_name": exp["segment"]["segment_name"],
            "county": exp["segment"]["county"],
            "rural_flag": exp["segment"]["rural_flag"],
            "risk_score": exp["segment"]["risk_score"],
            "risk_exposure_score": exp["segment"]["risk_exposure_score"],
            "data_density_flag": exp["data_density_flag"],
            "explanation_confidence": exp["explanation_confidence"],
            "top_features": exp["top_features"],
            "suggested_countermeasures": countermeasures,
        })
    return priority


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--scores", default="evaluation/results/segment_scores.parquet")
    ap.add_argument("--checkpoint", default="models/gnn/checkpoints/risk_gnn_best.pt")
    ap.add_argument("--features", default="data/processed/nc08_segments.parquet")
    ap.add_argument("--out", default="evaluation/results/priority_list.json")
    args = ap.parse_args()

    priority = build_priority_list(args.scores, args.checkpoint, args.features, args.n)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(priority, f, indent=2)
    print(f"[priority_list] wrote top {len(priority)} segments to {args.out}")


if __name__ == "__main__":
    main()
