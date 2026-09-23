"""Rural/suburban disparity analysis — the civic-impact narrative layer.

Aggregates Risk-Exposure by COUNTY and by RURAL vs. SUBURBAN classification
within NC-08, per the brief's section 5. This module is pure aggregation: it
assumes `rural_flag` (bool, per segment) and `county` were already assigned
during data/feature engineering (see data/pipelines/isrn_roads.py and
DATA_SOURCES.md for how rural vs. suburban is derived from county + NCDOT
road functional classification), and just summarizes Risk-Exposure over
those groups so the dashboard can render the disparity chart/callout
directly from this output.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def disparity_summary(segments: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """segments must have columns: county, rural_flag, risk_exposure,
    risk_score, ems_distance_available, data_density_flag.

    Returns
    -------
    dict with two DataFrames:
      by_county : mean/median/p90 Risk-Exposure per county, n_segments,
                  pct_low_confidence (data_density_flag share)
      by_rural_suburban : same stats split ONLY by rural_flag (district-wide)
      by_county_rural : same stats split by (county, rural_flag) — the finest
                        cut, what the dashboard's disparity chart plots
    """
    required = {"county", "rural_flag", "risk_exposure", "risk_score",
                "ems_distance_available", "data_density_flag"}
    missing = required - set(segments.columns)
    if missing:
        raise ValueError(f"disparity_summary missing columns: {sorted(missing)}")

    def _agg(g: pd.DataFrame) -> pd.Series:
        return pd.Series({
            "n_segments": len(g),
            "mean_risk_exposure": g["risk_exposure"].mean(),
            "median_risk_exposure": g["risk_exposure"].median(),
            "p90_risk_exposure": g["risk_exposure"].quantile(0.9),
            "mean_risk_score": g["risk_score"].mean(),
            "pct_ems_distance_available": g["ems_distance_available"].mean() * 100.0,
            "pct_low_confidence": g["data_density_flag"].mean() * 100.0,
        })

    by_county = segments.groupby("county", dropna=False).apply(_agg).reset_index()
    by_rural = segments.groupby("rural_flag", dropna=False).apply(_agg).reset_index()
    by_county_rural = (segments.groupby(["county", "rural_flag"], dropna=False)
                       .apply(_agg).reset_index())

    by_county = by_county.sort_values("mean_risk_exposure", ascending=False)
    by_county_rural = by_county_rural.sort_values(
        ["county", "rural_flag"])

    return {
        "by_county": by_county,
        "by_rural_suburban": by_rural,
        "by_county_rural": by_county_rural,
    }


def disparity_gap(summary: Dict[str, pd.DataFrame]) -> Dict[str, float]:
    """The single headline disparity number for the callout: the RATIO of
    mean Risk-Exposure in rural NC-08 vs. suburban/urban NC-08 (a value < 1
    means rural scores LOWER — on the real NC-08 data it does, at ~0.44,
    plausibly reflecting sparser rural incident reporting rather than lower
    real risk, see docs/LIMITATIONS.md; a value > 1 would mean the opposite —
    this function does not assume either direction), and how much SPARSER is
    rural data (pct_low_confidence gap) — the brief's Limitations point that
    rural counties have sparser incident records than the Charlotte-adjacent
    suburbs needs a number attached to it, not just a sentence, so the two
    numbers ship together here.
    """
    by_rural = summary["by_rural_suburban"].set_index("rural_flag")
    if True not in by_rural.index or False not in by_rural.index:
        return {"rural_vs_suburban_exposure_ratio": float("nan"),
                "rural_vs_suburban_confidence_gap_pct": float("nan")}
    rural = by_rural.loc[True]
    suburban = by_rural.loc[False]
    ratio = (rural["mean_risk_exposure"] / suburban["mean_risk_exposure"]
             if suburban["mean_risk_exposure"] else float("nan"))
    conf_gap = rural["pct_low_confidence"] - suburban["pct_low_confidence"]
    return {
        "rural_vs_suburban_exposure_ratio": float(ratio),
        "rural_vs_suburban_confidence_gap_pct": float(conf_gap),
    }
