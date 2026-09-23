"""The segment-explanation JSON schema — a CONTRACT the dashboard depends on.

PROVENANCE: ported from XTraffic's models/explainer/schema.py (same
validate-before-it-leaves-the-explainer discipline), reshaped for a different
question. XTraffic's explanation answers "which OTHER SENSORS caused this
forecast" (top_nodes/top_edges/propagation_path — a spatial-propagation
story). Ours answers "which of THIS SEGMENT'S OWN INPUT FEATURES drove its
risk score" (top_features — a feature-attribution story), because the brief
asks for per-segment feature attributions, not per-node influence. There is
no time axis (no propagation_lag_minutes — AADT/crash-history features carry
no sub-annual time series, see models/gnn/risk_gnn.py's module docstring) and
no forecast horizon (a risk score is not a forecast).

The schema (all fields required unless marked optional):
{
  "meta": {"district": str, "timestamp": str, "model_checkpoint": str,
           "model_checkpoint_sha256": str [optional]},
  "segment": {"segment_id": str, "segment_name": str, "county": str,
              "rural_flag": bool, "risk_score": float,
              "risk_exposure_score": float},
  "top_features": [{"feature_name": str, "importance": float,
                     "value": float, "modality": str}],
  "data_density_flag": bool,
  "explanation_confidence": float
}

`data_density_flag` (True = sparse/low-confidence data for this segment/
county) exists because the brief requires the dashboard show "an explicit
low-confidence/data-density flag rather than a falsely-precise number" —
this is that flag, computed once here rather than re-derived ad hoc in the
UI. See models/risk/targets.py for how it's set.

Python 3.9 compatible (typing.Dict/List, no `X | Y`).
"""
from __future__ import annotations

from typing import Any, Dict, List

_TOP_LEVEL = {
    "meta": dict,
    "segment": dict,
    "top_features": list,
    "data_density_flag": bool,
    "explanation_confidence": (int, float),
}

_META_KEYS = {"district": str, "timestamp": str, "model_checkpoint": str}
_META_OPTIONAL_KEYS = {"model_checkpoint_sha256": str}

_SEGMENT_KEYS = {
    "segment_id": str, "segment_name": str, "county": str,
    "rural_flag": bool, "risk_score": (int, float),
    "risk_exposure_score": (int, float),
}

_TOP_FEATURE_KEYS = {
    "feature_name": str, "importance": (int, float),
    "value": (int, float), "modality": str,
}


def _check_dict(name: str, d: Dict[str, Any], spec: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    if not isinstance(d, dict):
        return [f"{name}: expected dict, got {type(d).__name__}"]
    for key, typ in spec.items():
        if key not in d:
            errs.append(f"{name}.{key}: missing")
        elif not isinstance(d[key], typ) or (typ is not bool and isinstance(d[key], bool)):
            errs.append(f"{name}.{key}: expected {typ}, got {type(d[key]).__name__}")
    return errs


def validate_explanation(exp: Dict[str, Any]) -> List[str]:
    """Return a list of problems; empty list == valid. Never raises — callers
    decide whether to warn-and-continue or assert (see assert_valid)."""
    errs: List[str] = []
    for key, typ in _TOP_LEVEL.items():
        if key not in exp:
            errs.append(f"top-level.{key}: missing")
        elif not isinstance(exp[key], typ):
            errs.append(f"top-level.{key}: expected {typ}, got {type(exp[key]).__name__}")
    if errs:
        return errs

    errs += _check_dict("meta", exp["meta"], _META_KEYS)
    present_optional = {k: t for k, t in _META_OPTIONAL_KEYS.items() if k in exp["meta"]}
    if present_optional:
        errs += _check_dict("meta", exp["meta"], present_optional)
    errs += _check_dict("segment", exp["segment"], _SEGMENT_KEYS)
    for i, feat in enumerate(exp["top_features"]):
        errs += _check_dict(f"top_features[{i}]", feat, _TOP_FEATURE_KEYS)
    return errs


def assert_valid(exp: Dict[str, Any]) -> None:
    problems = validate_explanation(exp)
    if problems:
        raise ValueError("Explanation failed schema validation:\n  - "
                         + "\n  - ".join(problems))
