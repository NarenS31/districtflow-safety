"""Unit tests for the Risk-Exposure Index formula (models/risk/risk_exposure.py).

These pin down the exact behaviors the README documents as the formula's
contract: EMS distance can only ever push a segment's score UP relative to
its own base risk, never down; equal risk scores are ranked purely by EMS
distance; and a missing EMS-distance value degrades gracefully instead of
being silently treated as either "0 distance" or "max distance."
"""
import numpy as np

from models.risk.risk_exposure import compute_risk_exposure


def test_equal_risk_further_from_ems_scores_higher():
    # 4 segments so the two under test (0.5, 0.5) normalize to a nonzero,
    # non-degenerate risk_norm — two IDENTICAL values as the only entries
    # would min-max-collapse to 0 for both (nothing to differentiate against),
    # which would make this test tautological rather than a real check.
    risk = np.array([0.1, 0.5, 0.5, 0.9])
    ems = [10.0, 100.0, 5000.0, 10.0]  # segment 2 much farther from EMS than segment 1
    out = compute_risk_exposure(risk, ems, w_ems=1.0)
    assert out["risk_norm"][1] == out["risk_norm"][2]  # equal base risk, confirmed
    assert out["risk_exposure"][2] > out["risk_exposure"][1]


def test_w_ems_zero_reduces_to_plain_risk_norm():
    risk = np.array([0.2, 0.8, 0.5])
    ems = [10.0, 5000.0, 2500.0]
    out = compute_risk_exposure(risk, ems, w_ems=0.0)
    assert np.allclose(out["risk_exposure"], out["risk_norm"])


def test_missing_ems_distance_falls_back_to_risk_norm_alone():
    risk = np.array([0.3, 0.9])
    ems = [None, 4000.0]
    out = compute_risk_exposure(risk, ems, w_ems=1.0)
    assert out["ems_distance_available"][0] == False  # noqa: E712
    # Falls back to risk_norm, not boosted and not zeroed out.
    assert out["risk_exposure"][0] == out["risk_norm"][0]


def test_high_ems_distance_never_outranks_much_higher_base_risk():
    # A near-zero-risk segment far from EMS should not beat a high-risk
    # segment close to EMS — the multiplicative form keeps risk dominant.
    risk = np.array([0.01, 0.9])
    ems = [5000.0, 10.0]
    out = compute_risk_exposure(risk, ems, w_ems=1.0)
    assert out["risk_exposure"][1] > out["risk_exposure"][0]


def test_all_segments_missing_ems_still_returns_finite_scores():
    risk = np.array([0.1, 0.6, 0.9])
    ems = [None, None, None]
    out = compute_risk_exposure(risk, ems, w_ems=1.0)
    assert np.all(np.isfinite(out["risk_exposure"]))
    assert not out["ems_distance_available"].any()
