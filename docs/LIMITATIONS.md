# Limitations

This is the detailed version of the README's Limitations section — code
comments across the repo point here (`models/risk/*.py`,
`dashboard/src/components/MapView.tsx`) when a specific number or view is
affected by one of these gaps.

## Data sparsity is uneven across NC-08, by design of the region itself

Mecklenburg County (Charlotte and its immediate suburbs) has denser road
sensor/GIS coverage, denser NCDOT crash reporting infrastructure, and denser
ped/cyclist incident records than the rural counties in the district —
Anson, Richmond, Montgomery, Stanly, and much of Robeson. This is not a
modeling artifact; it reflects real, uneven public-safety data investment
across the district. **Measured on the real trained model:**

- Mean Risk-Exposure in the 5 rural counties comes out at **~44% of** the 3
  suburban/urban counties' (`models/risk/disparity.disparity_gap()`, run
  against `evaluation/results/segment_scores.parquet`). Read this as evidence
  of the REPORTING gap, not a safety finding: Mecklenburg alone holds 2,606
  of the district's 3,454 real recorded ped/cyclist incidents (2021-2025) —
  the model was trained on those counts, and a county with far fewer
  recorded incidents will predict a lower rate whether or not its roads are
  actually safer.
- A rural segment with zero recorded ped/cyclist incidents may be genuinely
  safer, OR may simply be under-reported. `models/risk/targets.py`'s
  `data_density_flag` flags a segment low-confidence when it's missing a
  fine-grained ISRN attribute match, an EMS routing distance, or sits in a
  county whose total 5-year incident count falls below a floor
  (`min_county_incidents` in `configs/model.yaml`). On the real NC-08 data
  this is **62.7% of all segments** — the ISRN fine-attribute gap (~45%
  missing speed limit, ~25% missing lane count) turned out to be the
  dominant driver, not cleanly split by rural/urban the way the incident-count
  gap is (see `data/pipelines/DATA_SOURCES.md` §1's DIAGNOSIS note).
- `models/risk/disparity.py`'s `disparity_gap()` reports the rural-vs-suburban
  gap in `pct_low_confidence` alongside the Risk-Exposure ratio specifically
  so this sparsity is a visible number, not an implicit caveat.
- The dashboard shows the low-confidence flag directly on every affected
  segment (brief §8) rather than presenting a falsely precise score.

## AADT is a static annual average, never a time series

NCDOT's Annual Average Daily Traffic figures are exactly that — one number
per road segment per year. The model uses AADT as a single static feature
(`aadt_normalized` in `docs/FEATURES.md`) and, separately, as a Poisson
regression exposure offset (`models/risk/targets.py`). It is NEVER
interpolated, resampled, or treated as if it varied by time of day, day of
week, or season — a segment's real-time traffic condition is a different
question this project does not answer (that's what DriveNC.gov/TIMS's live
overlay is for, and even that is explicitly a "current conditions" layer,
never archived, never used as training signal).

## EMS/fire station coverage is incomplete

See `data/pipelines/EMS_STATIONS_TODO.md` for the current per-county status.
Where a segment's `ems_distance_m` is unavailable, `models/risk/risk_exposure.py`
does NOT substitute a guessed value — the Risk-Exposure Index falls back to
the base risk score alone for that segment, and `ems_distance_available` is
surfaced so the dashboard can show that gap explicitly rather than implying
false precision.

## The explainer measures alignment with the model, not ground truth

Per-segment feature attributions (`models/explainer/explain.py`) show which
INPUT FEATURES the trained RiskGNN relied on for a given score. This is a
faithful description of the model's own reasoning — it is not independent
proof that those features are the true causal drivers of pedestrian/cyclist
risk on that segment. A model trained on sparse, uneven data can learn a
confident-looking but data-artifact-driven attribution. Countermeasure
suggestions (`models/risk/countermeasure.py`) are therefore a starting point
for engineering review, not a substitute for it.

## The counterfactual "what-if" layer is a model simulation, not a guarantee

`models/risk/counterfactual.py` shows how the TRAINED MODEL'S score would
change under a hypothetical feature edit, propagated through real GNN message
passing. It answers "what does the model think would happen," which is only
as good as the model's fit to the (sparse, uneven) underlying data — it is
not a substitute for a traffic engineering study before any real intervention.

## Manual gaps this project does not fabricate around

Per the project brief, these are explicit manual TODOs, not silently faked:
- Exact EMS/fire station locations for counties without clean centralized data
  (see `data/pipelines/EMS_STATIONS_TODO.md`).
- Outreach to county planning offices, Safe Routes to School coordinators, or
  Vision Zero contacts for real-world validation of the model's priority list.
- Ground-truthing the Top-N list against local knowledge before any of it is
  presented as a definitive engineering recommendation.
