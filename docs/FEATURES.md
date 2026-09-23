# Feature schema — the contract between the data layer and the model

This is the interface every other layer of the project depends on:
`data/pipelines/*` must produce a segment feature table with exactly these
columns (or a documented subset — missing modalities are handled gracefully,
see `models/gnn/risk_gnn.py`'s `HeteroFusion`); `models/gnn/train.py` reads
them into modality tensors by this grouping; `models/explainer/explain.py`,
`models/risk/countermeasure.py`, and `models/risk/counterfactual.py` all
match on these exact feature-name substrings. If a pipeline script renames a
column, the countermeasure/counterfactual rule tables will silently stop
matching it (they fail loud — "no rule matched" / "intervention not
simulated" — but a renamed column is still a real integration bug to catch
here first).

## Modality groups (fed to `HeteroFusion` as separate encoders)

### `infrastructure` — per-segment road attributes (from ISRN, fallback OSM)
| feature name | type | source | notes |
|---|---|---|---|
| `speed_limit_mph` | float | ISRN / OSM `maxspeed` | |
| `lane_count` | float | ISRN / OSM `lanes` | |
| `road_classification` | float (ordinal-encoded) | ISRN functional class | 0=local … higher=arterial |
| `intersection_density` | float, normalized [0,1] | derived: nearby intersection count within 250m | curvature/intersection-density proxy, brief §2 |
| `crosswalk_present` | float (0/1) | ISRN/OSM `crossing` tags, HSIP BIKEPED inventory | 1 = a marked crossing exists on/near the segment |
| `sidewalk_coverage` | float, fraction [0,1] | OSM `sidewalk` tag coverage | fraction of segment length with adjacent sidewalk |
| `lighting_coverage` | float, fraction [0,1] | OSM `lit` tag coverage, county GIS where available | often sparse outside urban counties — flag accordingly |

### `aadt` — annual average daily traffic (STATIC, one value per segment — never a time series)
| feature name | type | source |
|---|---|---|
| `aadt_normalized` | float, normalized [0,1] district-wide | NCDOT AADT segment data |

### `crash_history` — 5-year historical counts (the primary training signal)
| feature name | type | source |
|---|---|---|
| `pedcyclist_incident_count_5yr` | int | NCDOT NCBikePed / HSIP BikePed | THE regression target's basis (see `models/risk/targets.py`) |
| `general_crash_count_5yr` | int | NCDOT StatewideCrashTable | secondary feature, all-vehicle crashes |

### `context` — geographic/administrative context
| feature name | type | source |
|---|---|---|
| `rural_flag` | float (0/1) | derived: county + ISRN road classification (brief §2) | also carried un-encoded as `rural_flag: bool` in `segment_meta` for the disparity module |
| `county_code` | float (ordinal-encoded) | ISRN / county boundary join | |

### `ems_access` — EMS/fire station routing (per intersection, aggregated to segments)
| feature name | type | source |
|---|---|---|
| `ems_distance_m` | float, normalized [0,1] district-wide, NaN if unavailable | `utils/graph_utils.nearest_facility_distance` over the routing graph | segment value = mean of its two endpoint intersections' distances |

A segment/county with an incomplete `ems_access` modality (see
`data/pipelines/EMS_STATIONS_TODO.md`) is NOT dropped — `HeteroFusion` zeros
that modality's gate contribution for rows where it's absent (see
`models/gnn/risk_gnn.py`), and `models/risk/targets.py` sets
`data_density_flag=True` on those segments so the dashboard shows an
explicit low-confidence flag instead of a falsely precise Risk-Exposure
score (brief §8).

## Per-node (intersection) features — used only for EMS routing, not fed
directly to the segment-level GNN (the GNN's "nodes" are road segments, per
`utils/graph_utils.build_segment_adjacency`'s docstring):
- `intersection_type` (2-way / 3-way / 4-way / roundabout) — ISRN/OSM
- `degree` — computed from the routing graph
- `distance_to_nearest_ems_m` — `utils/graph_utils.nearest_facility_distance`
  output, aggregated up to the `ems_distance_m` segment feature above
