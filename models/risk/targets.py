"""How the RiskGNN's supervision target and data-density flag are built.

TARGET CHOICE: ped/cyclist crash risk is COUNT data (incidents per segment
over 5 years), not a continuous measurement, so the honest choice of loss is
a Poisson (or negative-binomial, if overdispersed) regression against the
raw `pedcyclist_incident_count_5yr` count, using log(AADT) as an offset —
this is the standard treatment for crash-frequency modeling in the road
safety literature (segments with more traffic exposure are expected to
accumulate more incidents at the same underlying per-trip risk, so AADT
enters as exposure, not as an ordinary feature competing for the same
signal). `risk_score` (what the GNN's readout produces) is the model's
predicted incident RATE; the dashboard's Risk-Exposure Index (see
risk_exposure.py) is a separate, downstream transform of that rate, not the
raw count itself.

DATA-DENSITY FLAG: per the brief's Limitations requirement (rural counties
have sparser records than the Charlotte-adjacent suburbs), a segment's score
must never be presented with false precision when its county's underlying
sample is thin. We flag a segment low-confidence if EITHER:
  (a) its own 5-year crash_history + pedcyclist_incident_count are both 0
      AND it also lacks AADT (i.e., there is close to no signal at all,
      not just "this segment happens to be safe"), OR
  (b) its COUNTY's total ped/cyclist incident record count falls below
      `min_county_incidents` (configs/model.yaml) — a small-sample flag at
      the county level, not just the segment level, since one segment's
      absence of incidents in a sparse county is much less informative than
      the same absence in a dense one.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def build_target(segments: pd.DataFrame) -> np.ndarray:
    """segments must have `pedcyclist_incident_count_5yr` (int) and
    `aadt_raw` (float, RAW un-normalized AADT, for the log-offset — the
    normalized `aadt_normalized` feature column is for the model input, this
    is the actual traffic-volume exposure term).

    Returns the Poisson regression TARGET array (raw counts) — train.py
    supplies the AADT log-offset to the loss, this function only assembles
    the count target so the offset logic lives in one place (train.py, next
    to the loss function it modifies).
    """
    counts = segments["pedcyclist_incident_count_5yr"].fillna(0).to_numpy(dtype=np.float64)
    return counts


def compute_data_density_flag(segments: pd.DataFrame, min_county_incidents: int = 15
                              ) -> pd.Series:
    """Returns a bool Series aligned to `segments.index`.

    REVISED (the original draft checked "does this segment have ANY AADT/
    crash/general-crash signal at all" — on the real assembled NC-08 table,
    AADT is present on ~100% of segments (see assemble_features.py's stats
    report), so that check was true for nearly every row and the flag was
    almost never set — a real bug caught by actually running this on live
    data, not a synthetic smoke test with deliberately-injected gaps). What
    ACTUALLY varies on the real table is (a) whether the ISRN fine-attribute
    join reached this segment (speed_limit_mph / lane_count present — real
    rate ~45%/~25% missing, see DIAGNOSIS comment in assemble_features.py)
    and (b) whether an EMS routing distance was resolved. Both are checked
    directly instead of the AADT proxy. The county-incident-count floor is
    kept as a second, independent criterion (harmless if it never fires on
    the current 8 counties, which all clear 15 — it exists for whichever
    future county/time-window has a genuinely thin sample, e.g. mid-year on
    a partial data pull).
    """
    missing_fine_attrs = (
        segments["speed_limit_mph"].isna() | segments["lane_count"].isna()
    )
    missing_ems = segments["ems_distance_m"].isna() if "ems_distance_m" in segments else False
    county_totals = segments.groupby("county")["pedcyclist_incident_count_5yr"].transform(
        lambda s: s.fillna(0).sum())
    county_sparse = county_totals < min_county_incidents
    return missing_fine_attrs | missing_ems | county_sparse


def target_summary(segments: pd.DataFrame) -> Dict[str, float]:
    """A quick honesty check to print/log before training — if this looks
    degenerate (e.g. >95% zero counts everywhere), that's a real finding
    about data sparsity to report, not a bug to silently work around."""
    counts = segments["pedcyclist_incident_count_5yr"].fillna(0)
    return {
        "n_segments": int(len(segments)),
        "pct_zero_incidents": float((counts == 0).mean() * 100.0),
        "mean_incidents": float(counts.mean()),
        "max_incidents": float(counts.max()) if len(counts) else 0.0,
        "n_counties": int(segments["county"].nunique()),
    }
