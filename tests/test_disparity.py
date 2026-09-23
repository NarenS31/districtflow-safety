"""Unit tests for models/risk/disparity.py — the rural/suburban civic-impact
narrative layer. Pins down that the disparity numbers actually reflect a
real gap when one is injected, and that the module fails loud (not silently)
on a malformed input rather than producing a misleading empty chart.
"""
import pandas as pd
import pytest

from models.risk.disparity import disparity_gap, disparity_summary


def _fake_segments() -> pd.DataFrame:
    rows = []
    # Suburban county: dense data, moderate exposure.
    for i in range(20):
        rows.append({
            "county": "Mecklenburg", "rural_flag": False,
            "risk_exposure": 0.3, "risk_score": 0.1,
            "ems_distance_available": True, "data_density_flag": False,
        })
    # Rural county: sparse data, higher exposure, mostly flagged.
    for i in range(20):
        rows.append({
            "county": "Anson", "rural_flag": True,
            "risk_exposure": 0.6, "risk_score": 0.2,
            "ems_distance_available": i % 2 == 0, "data_density_flag": True,
        })
    return pd.DataFrame(rows)


def test_disparity_summary_shapes():
    segs = _fake_segments()
    summary = disparity_summary(segs)
    assert set(summary) == {"by_county", "by_rural_suburban", "by_county_rural"}
    assert len(summary["by_county"]) == 2
    assert len(summary["by_rural_suburban"]) == 2


def test_rural_segments_show_higher_exposure_and_lower_confidence():
    segs = _fake_segments()
    summary = disparity_summary(segs)
    gap = disparity_gap(summary)
    assert gap["rural_vs_suburban_exposure_ratio"] > 1.0  # rural exposure is higher
    assert gap["rural_vs_suburban_confidence_gap_pct"] > 0  # rural is less confident


def test_missing_required_column_raises_loud():
    segs = _fake_segments().drop(columns=["data_density_flag"])
    with pytest.raises(ValueError):
        disparity_summary(segs)
