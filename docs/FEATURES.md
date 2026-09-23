# Feature schema — the contract between the data layer and the model

This is the interface `data/pipelines/assemble_features.py` (the real join
of ISRN + AADT + crash + EMS pulls into one table) produces and
`models/gnn/train.py` reads into modality tensors by the grouping below.
`models/explainer/explain.py`, `models/risk/countermeasure.py`, and
`models/risk/counterfactual.py` all match on these exact feature-name
substrings — a renamed column breaks that matching loudly (a "no rule
matched" / "intervention not simulated" fallback fires), not silently.

**Node unit of analysis: NCDOT AADT segments, not raw ISRN records.** ISRN's
`RoadCharacteristicsQtr` re-splits a route on every attribute change (some
real segments are a few feet long — see `data/pipelines/DATA_SOURCES.md`
§1), which is both architecturally infeasible for `RiskGNN`'s O(N²) MOD-1
semantic adjacency at ISRN's real scale (157,807 records) and would spread
the already-sparse 5-year incident signal (3,454 records total) too thin to
learn from. AADT segments (7,975 in the NC-08 bbox) are NCDOT's own
established traffic-volume analysis unit — real road stretches between
significant points, not an ad hoc bucketing rule. This means the model's
scope is implicitly the AADT-counted network; NCDOT doesn't run counts on
minor residential streets, so those are out of scope for this version (see
`docs/LIMITATIONS.md`).

## Modality groups (fed to `HeteroFusion` as separate encoders)

### `infrastructure` — per-segment road attributes (from ISRN)
| feature name | type | source | status |
|---|---|---|---|
| `speed_limit_mph` | float | ISRN `SpeedLimit`, joined by nearest point within 500m | REAL — ~45% missing (ISRN coverage gap, not a join bug — see `assemble_features.py`'s DIAGNOSIS comment) |
| `lane_count` | float | ISRN `ThruLaneCount` | REAL — ~25% missing |
| `road_classification` | float (FHWA functional class 1-7) | ISRN `FuncClass` | REAL |
| `crosswalk_present` | float (0/1) | OSM `crossing` tags | **NOT YET REAL** — `data/pipelines/osm_fallback.py` is written correctly but currently blocked by this build environment's network access to the Overpass API (genuine environment limitation, documented in `data/pipelines/DATA_SOURCES.md` §4, not a fabricated source). `models/risk/countermeasure.py`'s crosswalk rule stays dormant (never fires) until this lands — it will activate with zero code changes. |
| `sidewalk_coverage` | float, fraction [0,1] | OSM `sidewalk` tag | **NOT YET REAL** — same Overpass blocker |
| `lighting_coverage` | float, fraction [0,1] | OSM `lit` tag | **NOT YET REAL** — same Overpass blocker |

### `aadt` — annual average daily traffic (STATIC, one value per segment — never a time series)
| feature name | type | source | status |
|---|---|---|---|
| `aadt_normalized` | float, district-wide min-max | NCDOT `NCDOT_2025_AADTandTrafficSegments_gdb` | REAL — 0% missing (this is the node-defining layer) |
| `aadt_raw` | float | same | REAL — used as the Poisson regression exposure offset, `models/risk/targets.py` |

### `crash_history` — 5-year historical counts (the primary training signal)
| feature name | type | source | status |
|---|---|---|---|
| `pedcyclist_incident_count_5yr` | int, genuinely SEGMENT-level | NCDOT `NCDOT_NonMotoristCrashes`, spatially joined to the nearest segment vertex within 200m | REAL — the regression target's basis. **Not** the HSIP_BIKEPED/HSIP_BP family the original brief flagged as a likely source — those turned out to be HSIP candidate-*project* sites, not crash records; see `DATA_SOURCES.md` §2b. |
| `general_crash_count_5yr_county` | int, **COUNTY-level, not segment-level** | NCDOT `StatewideCrashTable` | REAL, but coarser resolution than its name might suggest — `StatewideCrashTable` is a non-spatial attribute TABLE with no geometry at all, so it genuinely cannot be joined to a specific segment. The same county-wide 5-year total is broadcast to every segment in that county. Named explicitly to flag this (not `..._5yr` alone, which would imply segment-level like its pedcyclist counterpart). |

### `context` — geographic/administrative context
| feature name | type | source | status |
|---|---|---|---|
| `rural_flag` | bool | ISRN `UrbanType` (Census-derived): `NaN` (outside any delineated Census urban area/cluster) = rural; `"Urban Cluster"`/`"Urbanized Area"` = not rural | REAL — a real Census Bureau field, not a heuristic invented for this project |
| `county_code` | float (ordinal-encoded) | ISRN `County`, factorized | REAL |

### `ems_access` — EMS/fire station routing distance
| feature name | type | source | status |
|---|---|---|---|
| `ems_distance_m` | float, district-wide min-max normalized in `risk_exposure.py`; raw meters in the feature table | Multi-source Dijkstra (`utils/graph_utils.nearest_facility_distance`) over the SEGMENT ADJACENCY GRAPH ITSELF (not a separate intersection graph — see `assemble_features.py`), sourced from NC OneMap's `NC_Fire_Stations` + `NC1Map_Emergency_Services` (435 real stations, all 8 counties) | REAL — ~36% of segments unreachable (graph-disconnected from any station-adjacent segment at the 50m adjacency tolerance), left as `NaN`, never guessed. `models/risk/risk_exposure.py` and `models/risk/targets.py`'s `data_density_flag` both treat this honestly. |

A segment with a missing `infrastructure` attribute or unresolved
`ems_distance_m` is NOT dropped — `HeteroFusion` mean-imputes per-row gaps
within a present modality (`models/gnn/train.py`, never zero-fills a real
measurement like speed limit or lane count) and
`models/risk/targets.py.compute_data_density_flag` sets
`data_density_flag=True` so the dashboard shows an explicit low-confidence
flag instead of a falsely precise Risk-Exposure score (brief §8). On the
real NC-08 pull this is **62.7%** of segments — high, and honestly reported
as such rather than tuned down to look better.

## Geometry columns (not model features — used for the map + adjacency)
`start_lat`/`start_lon`/`end_lat`/`end_lon` (segment polyline endpoints, from
the real AADT service's geometry) and `mid_lat`/`mid_lon` (used for
inter-segment distance in the EMS routing graph). `segment_adjacency` is
built from `start_*`/`end_*` via shared-endpoint proximity
(`utils/graph_utils.build_segment_adjacency`, KD-tree accelerated — a plain
O(N²) double loop does not finish in reasonable time at N≈6,000-8,000 real
segments).

## Per-node (intersection) features — not applicable in the current design

The original design considered per-intersection features (type, degree)
separate from segment features. In practice, `assemble_features.py` never
builds an explicit intersection graph — EMS routing runs directly over the
segment adjacency graph (see `ems_access` above) — so this layer doesn't
exist as a separate artifact. If a future revision adds real intersection
nodes (e.g. from ISRN's own LRS topology rather than the endpoint-proximity
heuristic), it would attach here.
