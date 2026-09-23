"""Unit tests for utils/graph_utils.py — segment adjacency construction and
the multi-source Dijkstra EMS-distance routine, on small hand-checkable graphs.
"""
import numpy as np

from utils.graph_utils import build_segment_adjacency, nearest_facility_distance


def test_segment_adjacency_exact_topology_shares_intersection():
    # Three segments: A-B, B-C, and D-E (disconnected from the first two).
    endpoints = [((0, 0), (0, 1)), ((0, 1), (0, 2)), ((5, 5), (5, 6))]
    ids = [("A", "B"), ("B", "C"), ("D", "E")]
    adj = build_segment_adjacency(endpoints, intersection_ids=ids)
    assert adj[0, 1] == 1.0  # share intersection B
    assert adj[1, 0] == 1.0  # undirected
    assert adj[0, 2] == 0.0  # no shared intersection
    assert adj[1, 2] == 0.0


def test_segment_adjacency_heuristic_fallback_uses_proximity():
    # Two segments whose endpoints are ~5m apart (within tol) should connect;
    # a third far away should not.
    endpoints = [
        ((35.000000, -80.000000), (35.001000, -80.000000)),
        ((35.001000, -80.000045), (35.002000, -80.000000)),  # ~4m from seg 0's end
        ((36.500000, -81.500000), (36.501000, -81.500000)),  # far away
    ]
    adj = build_segment_adjacency(endpoints, intersection_ids=None, tol_m=15.0)
    assert adj[0, 1] == 1.0
    assert adj[0, 2] == 0.0


def test_nearest_facility_distance_multi_source_dijkstra():
    # Line graph: A - B - C - D - E, each edge 100m. Facilities at A and E.
    graph = {
        "A": [("B", 100.0)], "B": [("A", 100.0), ("C", 100.0)],
        "C": [("B", 100.0), ("D", 100.0)], "D": [("C", 100.0), ("E", 100.0)],
        "E": [("D", 100.0)],
    }
    dist = nearest_facility_distance(graph, facility_nodes=["A", "E"])
    assert dist["A"] == 0.0
    assert dist["E"] == 0.0
    assert dist["C"] == 200.0  # equidistant from both, 2 hops either way
    assert dist["B"] == 100.0
    assert dist["D"] == 100.0


def test_nearest_facility_distance_unreachable_nodes_omitted():
    graph = {"A": [("B", 50.0)], "B": [("A", 50.0)], "X": [("Y", 10.0)], "Y": [("X", 10.0)]}
    dist = nearest_facility_distance(graph, facility_nodes=["A"])
    assert "A" in dist and "B" in dist
    assert "X" not in dist and "Y" not in dist  # disconnected component, never guessed
