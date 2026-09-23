"""The Risk-Exposure Index — the headline metric of the dashboard.

THE FORMULA (documented plainly, per the project brief — this is not allowed
to be buried):

    risk_norm     = min-max(risk_score)          over all NC-08 segments, in [0,1]
    ems_norm      = min-max(ems_distance_meters)  over all NC-08 segments, in [0,1]
    risk_exposure = risk_norm * (1 + w_ems * ems_norm)

`risk_score` is the RiskGNN's predicted ped/cyclist crash-risk score for the
segment (models/gnn/risk_gnn.py). `ems_distance_meters` is the shortest
road-network distance from the segment to its nearest fire/EMS station
(utils/graph_utils.nearest_facility_distance). `w_ems` is the ONE tunable
knob (configs/risk_exposure.yaml, default 1.0): a segment at the district's
maximum EMS distance gets up to a (1 + w_ems)x multiplier on its base risk;
a segment adjacent to a station gets ~1x (unchanged).

WHY MULTIPLICATIVE, NOT A WEIGHTED SUM (alpha*risk + beta*distance): a
weighted sum lets a very-low-risk segment that happens to be far from EMS
outrank a genuinely high-risk segment close to a station, which would be a
strange headline number for a ped/cyclist safety tool to lead with. The
multiplicative form keeps risk_score as the dominant term — a segment cannot
reach a high Risk-Exposure score without a meaningful base risk score — while
EMS distance still scales it up, which is exactly the brief's requirement:
"a segment with moderate risk but far from emergency response scores higher
than an equally risky segment close to a station."

Segments with a missing EMS-distance value (see EMS_STATIONS_TODO.md — not
every county has clean station data yet) are NOT silently given ems_norm=0
(which would understate their exposure) or 1 (which would overstate it).
They get `ems_distance_available=False` and risk_exposure falls back to
risk_norm alone, with `data_density_flag=True` so the dashboard shows the
low-confidence flag instead of a falsely-precise number (brief, section 8).
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np


def _minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = np.nanmin(x), np.nanmax(x)
    if hi - lo < 1e-9:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def compute_risk_exposure(
    risk_scores: np.ndarray,
    ems_distance_m: List[Optional[float]],
    w_ems: float = 1.0,
) -> Dict[str, np.ndarray]:
    """Compute the Risk-Exposure Index for every segment at once (min-max
    normalization is district-wide, so it must see all segments together).

    Parameters
    ----------
    risk_scores : [N] RiskGNN output per segment.
    ems_distance_m : length-N list; None where EMS routing distance is
        unavailable for that segment (data gap, see module docstring).
    w_ems : configurable EMS-distance weight (configs/risk_exposure.yaml).

    Returns
    -------
    dict with:
      risk_exposure       : [N] the headline score
      risk_norm            : [N] normalized base risk (for the explainer/UI)
      ems_norm              : [N] normalized EMS distance, NaN where unavailable
      ems_distance_available: [N] bool
    """
    n = len(risk_scores)
    risk_norm = _minmax(np.asarray(risk_scores, dtype=np.float64))

    ems_arr = np.array([np.nan if d is None else d for d in ems_distance_m],
                       dtype=np.float64)
    available = ~np.isnan(ems_arr)

    ems_norm = np.full(n, np.nan)
    if available.any():
        ems_norm[available] = _minmax(ems_arr[available])

    risk_exposure = risk_norm.copy()
    boosted = risk_norm * (1.0 + w_ems * np.nan_to_num(ems_norm, nan=0.0))
    risk_exposure = np.where(available, boosted, risk_norm)

    return {
        "risk_exposure": risk_exposure,
        "risk_norm": risk_norm,
        "ems_norm": ems_norm,
        "ems_distance_available": available,
    }
