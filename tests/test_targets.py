"""Unit tests for models/risk/targets.py's compute_data_density_flag.

Regression test for a real bug: the first version checked "does this
segment have ANY aadt/crash signal at all," which was true for ~100% of
real NC-08 segments (AADT is present almost everywhere) and so almost never
flagged anything — caught only by running the real pipeline, not a
synthetic smoke test. These tests pin the fixed behavior: missing
fine-grained attributes or EMS distance is what should actually flag a
segment, not the presence/absence of AADT.
"""
import pandas as pd

from models.risk.targets import compute_data_density_flag


def _segments(**overrides) -> pd.DataFrame:
    base = {
        "county": ["Union"] * 5,
        "pedcyclist_incident_count_5yr": [5, 0, 3, 0, 1],
        "speed_limit_mph": [45.0, 45.0, 45.0, 45.0, 45.0],
        "lane_count": [2.0, 2.0, 2.0, 2.0, 2.0],
        "ems_distance_m": [100.0, 100.0, 100.0, 100.0, 100.0],
        "aadt_raw": [5000.0] * 5,  # present everywhere — must NOT be what drives the flag
    }
    base.update(overrides)
    return pd.DataFrame(base)


def test_complete_segment_not_flagged():
    segs = _segments()
    flags = compute_data_density_flag(segs, min_county_incidents=1)
    assert not flags.any()


def test_missing_speed_limit_flags_that_segment_only():
    segs = _segments(speed_limit_mph=[45.0, None, 45.0, 45.0, 45.0])
    flags = compute_data_density_flag(segs, min_county_incidents=1)
    assert flags.tolist() == [False, True, False, False, False]


def test_missing_ems_distance_flags_that_segment():
    segs = _segments(ems_distance_m=[100.0, 100.0, None, 100.0, 100.0])
    flags = compute_data_density_flag(segs, min_county_incidents=1)
    assert flags.tolist() == [False, False, True, False, False]


def test_sparse_county_flags_every_segment_in_it():
    segs = _segments(pedcyclist_incident_count_5yr=[0, 0, 0, 0, 0])
    flags = compute_data_density_flag(segs, min_county_incidents=100)
    assert flags.all()  # county total (0) is far below the floor


def test_present_aadt_alone_does_not_prevent_flagging():
    # The bug this test guards against: AADT being present everywhere must
    # not mask a genuinely missing infrastructure attribute.
    segs = _segments(speed_limit_mph=[None] * 5)
    flags = compute_data_density_flag(segs, min_county_incidents=1)
    assert flags.all()
