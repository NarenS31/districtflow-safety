"""The What-If layer — interactive counterfactual interventions.

Per the brief (section 7): let a user toggle a hypothetical intervention on
one segment and see the updated Risk-Exposure score for that segment AND its
immediate graph neighbors, via the GNN's actual message passing — not a
static number edit. This module does exactly that: it perturbs the chosen
segment's OWN feature row, re-runs the frozen RiskGNN forward pass over the
WHOLE graph (all other segments unchanged), and diffs the new risk/exposure
scores against the baseline for the target segment and its 1-hop and 2-hop
neighbors (read straight off the segment adjacency matrix — the same graph
GraphConv diffuses over, so the neighbors shown are exactly the ones that
could feel the change through the model's own spatial mixing).

PROVENANCE: this is the same "clone the input, edit one row, re-run the
frozen model" pattern as the explainer's masking (explain.py) and shares its
discipline — the model is never retrained, only its input.

Intervention presets are a plain editable table (same transparency stance as
countermeasure.py) so adding a new hypothetical action is a one-line edit,
not a code change to the inference path.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import torch

from ..gnn.risk_gnn import RiskGNN

# feature_name substring -> (new absolute value, or a callable old -> new).
# Matched the same way countermeasure.py matches features: substring on the
# feature name produced by the feature-engineering layer (docs/FEATURES.md).
INTERVENTIONS: Dict[str, Dict] = {
    "add_crosswalk": {
        "label": "Add a marked crosswalk",
        "feature_contains": "crosswalk",
        "set_value": 1.0,
    },
    "add_sidewalk": {
        "label": "Close the sidewalk gap",
        "feature_contains": "sidewalk",
        "set_value": 1.0,
    },
    "add_lighting": {
        "label": "Add street lighting",
        "feature_contains": "lighting",
        "set_value": 1.0,
    },
    "reduce_speed_limit_25": {
        "label": "Reduce speed limit to 25 mph",
        "feature_contains": "speed_limit",
        "set_value": 25.0,
    },
    "reduce_speed_limit_30": {
        "label": "Reduce speed limit to 30 mph",
        "feature_contains": "speed_limit",
        "set_value": 30.0,
    },
}


def _neighbors(adjacency: np.ndarray, idx: int, hops: int) -> List[int]:
    """Segment indices reachable within `hops` steps of the segment adjacency
    matrix (the exact graph GraphConv diffuses risk-relevant signal over)."""
    frontier = {idx}
    visited = {idx}
    for _ in range(hops):
        nxt = set()
        for i in frontier:
            nxt.update(int(j) for j in np.where(adjacency[i] > 0)[0])
        frontier = nxt - visited
        visited |= nxt
    visited.discard(idx)
    return sorted(visited)


def run_counterfactual(
    model: RiskGNN,
    modalities: Dict[str, torch.Tensor],
    feature_names: Dict[str, List[str]],
    adjacency: np.ndarray,
    target_idx: int,
    intervention_key: str,
    device: Optional[torch.device] = None,
) -> Dict:
    """Apply one intervention preset to `target_idx`'s feature row, re-run
    the model over the whole graph, and report the score delta for the
    target and its 1-hop / 2-hop neighbors.
    """
    if intervention_key not in INTERVENTIONS:
        raise KeyError(f"Unknown intervention '{intervention_key}'. "
                       f"Known: {list(INTERVENTIONS)}")
    spec = INTERVENTIONS[intervention_key]
    device = device or torch.device("cpu")
    model = model.to(device)
    model.eval()

    # softplus matches the rate transform models/gnn/evaluate.py applies for
    # `risk_score` everywhere else, so this module's numbers line up with
    # the rest of the dashboard (same fix as the explainer's pred_orig_rate).
    with torch.no_grad():
        baseline = torch.nn.functional.softplus(
            model({k: v.to(device) for k, v in modalities.items()})).cpu().numpy()

    perturbed = {k: v.clone() for k, v in modalities.items()}
    applied = False
    for mod_name, names in feature_names.items():
        for c, fname in enumerate(names):
            if spec["feature_contains"] in fname.lower():
                perturbed[mod_name][target_idx, c] = spec["set_value"]
                applied = True

    if not applied:
        return {
            "applied": False,
            "reason": (f"No feature matching '{spec['feature_contains']}' found "
                      f"for this segment — intervention not simulated."),
        }

    with torch.no_grad():
        updated = torch.nn.functional.softplus(
            model({k: v.to(device) for k, v in perturbed.items()})).cpu().numpy()

    hop1 = _neighbors(adjacency, target_idx, 1)
    hop2 = [i for i in _neighbors(adjacency, target_idx, 2) if i not in hop1]

    def _record(idx: int) -> Dict:
        return {
            "segment_idx": idx,
            "baseline_risk_score": round(float(baseline[idx]), 4),
            "updated_risk_score": round(float(updated[idx]), 4),
            "delta": round(float(updated[idx] - baseline[idx]), 4),
        }

    return {
        "applied": True,
        "intervention": spec["label"],
        "target": _record(target_idx),
        "hop1_neighbors": [_record(i) for i in hop1],
        "hop2_neighbors": [_record(i) for i in hop2],
    }
