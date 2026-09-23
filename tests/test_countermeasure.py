"""Unit tests for models/risk/countermeasure.py's rule table — the
"transparent, editable, not a black box" lookup. Checks the rules actually
fire on realistic feature-attribution input and that an unmatched segment
gets the honest "no rule matched" fallback instead of a fabricated
suggestion.
"""
from models.risk.countermeasure import suggest_countermeasures


def test_high_speed_limit_triggers_traffic_calming():
    feats = [{"feature_name": "speed_limit_mph", "importance": 0.8, "value": 55.0, "modality": "infrastructure"}]
    out = suggest_countermeasures(feats)
    assert any("speed" in c["category"].lower() or "calming" in c["category"].lower() for c in out)


def test_missing_crosswalk_triggers_crossing_improvement():
    feats = [{"feature_name": "crosswalk_present", "importance": 0.7, "value": 0.0, "modality": "infrastructure"}]
    out = suggest_countermeasures(feats)
    assert any("crosswalk" in c["category"].lower() for c in out)


def test_no_matching_rule_gives_honest_fallback_not_a_guess():
    feats = [{"feature_name": "county_code", "importance": 0.9, "value": 3.0, "modality": "context"}]
    out = suggest_countermeasures(feats)
    assert len(out) == 1
    assert "no rule matched" in out[0]["category"].lower()


def test_deduplicates_by_category():
    feats = [
        {"feature_name": "speed_limit_mph", "importance": 0.9, "value": 55.0, "modality": "infrastructure"},
        {"feature_name": "speed_limit_mph", "importance": 0.5, "value": 50.0, "modality": "infrastructure"},
    ]
    out = suggest_countermeasures(feats)
    categories = [c["category"] for c in out]
    assert len(categories) == len(set(categories))


def test_respects_max_suggestions():
    feats = [
        {"feature_name": "speed_limit_mph", "importance": 0.9, "value": 55.0, "modality": "infrastructure"},
        {"feature_name": "crosswalk_present", "importance": 0.8, "value": 0.0, "modality": "infrastructure"},
        {"feature_name": "sidewalk_coverage", "importance": 0.7, "value": 0.1, "modality": "infrastructure"},
        {"feature_name": "lighting_coverage", "importance": 0.6, "value": 0.1, "modality": "infrastructure"},
    ]
    out = suggest_countermeasures(feats, max_suggestions=2)
    assert len(out) <= 2
