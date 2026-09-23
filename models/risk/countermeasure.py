"""Rule-based countermeasure lookup — deliberately NOT a black box.

Per the brief: tag each high-priority segment with a suggested countermeasure
category based on which features drove its score, using a simple, editable,
transparent rule table keyed to the explainer's top attributed features and
referencing standard FHWA pedestrian safety countermeasure categories. This
is a LOOKUP, not a model: every rule below is one line a non-engineer can
read, question, and edit. If a feature name here drifts from what
data/pipelines actually produces, RULES will simply stop matching (loud, via
the "no rule matched" fallback) rather than silently mis-tagging.

CITATIONS (verified real, not assumed — checked against FHWA's own site):
- FHWA Proven Safety Countermeasures (PSCi), 28 countermeasures including
  Road Diets, Crosswalk Visibility Enhancements, Pedestrian Refuge Islands,
  Lighting, Signal Timing: https://highways.dot.gov/safety/proven-safety-countermeasures
- FHWA STEP (Safe Transportation for Every Pedestrian) guide:
  https://highways.dot.gov/safety/pedestrian-bicyclist/step
- FHWA Systemic Safety Project Selection Tool:
  https://highways.dot.gov/safety/data-analysis-tools/systemic/systemic-safety-project-selection-tool
"""
from __future__ import annotations

from typing import Dict, List, TypedDict


class Countermeasure(TypedDict):
    category: str
    fhwa_reference: str
    rationale: str


# Ordered rule list: (feature_name substring match, condition, countermeasure).
# First matching rule per feature wins; a segment collects up to N distinct
# countermeasures from its top attributed features (deduplicated by category).
# Editing this table is the entire "retrain" step for the countermeasure
# layer — no model weights involved, on purpose.
_RULES: List[Dict] = [
    {
        "feature_contains": "speed_limit",
        "condition": lambda v: v >= 45,
        "countermeasure": {
            "category": "Reduced speed limit / traffic calming",
            "fhwa_reference": "FHWA Proven Safety Countermeasures: Road Diets, Speed Management",
            "rationale": "High posted speed limit is among this segment's top risk drivers.",
        },
    },
    {
        "feature_contains": "crosswalk",
        "condition": lambda v: v < 0.5,  # crosswalk-presence flag, 0 = absent
        "countermeasure": {
            "category": "Marked crosswalk / pedestrian crossing improvement",
            "fhwa_reference": "FHWA Proven Safety Countermeasures: Pedestrian Crossing Improvements",
            "rationale": "No marked crosswalk detected near this segment.",
        },
    },
    {
        "feature_contains": "sidewalk",
        "condition": lambda v: v < 0.5,  # sidewalk-coverage flag/fraction
        "countermeasure": {
            "category": "Sidewalk gap closure",
            "fhwa_reference": "FHWA STEP Guide: Pedestrian Facility Design",
            "rationale": "Sidewalk coverage is incomplete or absent along this segment.",
        },
    },
    {
        "feature_contains": "lighting",
        "condition": lambda v: v < 0.5,
        "countermeasure": {
            "category": "Street lighting improvement",
            "fhwa_reference": "FHWA Proven Safety Countermeasures: Lighting",
            "rationale": "Low/absent street lighting coverage on this segment.",
        },
    },
    {
        "feature_contains": "intersection_density",
        "condition": lambda v: v >= 0.7,  # normalized density
        "countermeasure": {
            "category": "Signal timing / intersection control review",
            "fhwa_reference": "FHWA Proven Safety Countermeasures: Signal Timing",
            "rationale": "High nearby intersection density increases conflict points.",
        },
    },
    {
        "feature_contains": "aadt",
        "condition": lambda v: v >= 0.7,  # normalized AADT
        "countermeasure": {
            "category": "Road diet / lane reconfiguration",
            "fhwa_reference": "FHWA Proven Safety Countermeasures: Road Diets",
            "rationale": "High traffic volume (AADT) relative to the district.",
        },
    },
    {
        "feature_contains": "lane_count",
        "condition": lambda v: v >= 4,
        "countermeasure": {
            "category": "Pedestrian refuge island / crossing distance reduction",
            "fhwa_reference": "FHWA Proven Safety Countermeasures: Pedestrian Refuge Islands",
            "rationale": "Wide multi-lane crossing distance on this segment.",
        },
    },
    {
        "feature_contains": "crash_history",
        "condition": lambda v: v > 0,
        "countermeasure": {
            "category": "Targeted enforcement / engineering study",
            "fhwa_reference": "FHWA Systemic Safety Project Selection Tool",
            "rationale": "Documented prior ped/cyclist crash history on this segment.",
        },
    },
]


def suggest_countermeasures(top_features: List[Dict], max_suggestions: int = 3
                            ) -> List[Countermeasure]:
    """top_features: the explainer's top_features list (schema.py), each
    {feature_name, importance, value, modality}. Returns up to
    max_suggestions countermeasures, ordered by the rank of the attributed
    feature that triggered them (i.e. the most important driver's
    countermeasure comes first), deduplicated by category.
    """
    seen = set()
    out: List[Countermeasure] = []
    for feat in top_features:
        name = feat["feature_name"].lower()
        value = feat["value"]
        for rule in _RULES:
            if rule["feature_contains"] not in name:
                continue
            try:
                if not rule["condition"](value):
                    continue
            except TypeError:
                continue
            cm = rule["countermeasure"]
            if cm["category"] in seen:
                continue
            seen.add(cm["category"])
            out.append(cm)
            break
        if len(out) >= max_suggestions:
            break

    if not out:
        out.append({
            "category": "Engineering study recommended (no rule matched)",
            "fhwa_reference": "FHWA Systemic Safety Project Selection Tool",
            "rationale": ("This segment's top risk drivers did not match an "
                          "existing rule — flagged for manual review rather "
                          "than a guessed countermeasure."),
        })
    return out
