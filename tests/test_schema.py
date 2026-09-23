"""Unit tests for models/explainer/schema.py — the explanation JSON contract
the dashboard depends on. A drift here breaks the frontend silently, so the
validator itself needs to actually catch drift.
"""
from models.explainer.schema import assert_valid, validate_explanation

VALID = {
    "meta": {"district": "NC-08", "timestamp": "t", "model_checkpoint": "risk_gnn_best.pt"},
    "segment": {
        "segment_id": "seg_1", "segment_name": "Test Segment", "county": "Union",
        "rural_flag": False, "risk_score": 0.1, "risk_exposure_score": 0.2,
    },
    "top_features": [
        {"feature_name": "speed_limit_mph", "importance": 0.5, "value": 45.0, "modality": "infrastructure"},
    ],
    "data_density_flag": False,
    "explanation_confidence": 0.8,
}


def test_valid_explanation_passes():
    assert validate_explanation(VALID) == []
    assert_valid(VALID)  # should not raise


def test_missing_top_level_key_is_caught():
    bad = {k: v for k, v in VALID.items() if k != "top_features"}
    problems = validate_explanation(bad)
    assert any("top_features" in p for p in problems)


def test_wrong_type_is_caught():
    bad = dict(VALID)
    bad["segment"] = dict(VALID["segment"])
    bad["segment"]["risk_score"] = "not a number"
    problems = validate_explanation(bad)
    assert any("risk_score" in p for p in problems)


def test_bool_rejected_where_float_expected():
    # bool is a subclass of int/float in Python — must not silently pass as
    # a real risk_score (a stray True/False masquerading as a value).
    bad = dict(VALID)
    bad["segment"] = dict(VALID["segment"])
    bad["segment"]["risk_score"] = True
    problems = validate_explanation(bad)
    assert any("risk_score" in p for p in problems)
