# Fire & EMS Station Coverage — NC-08 (per-county status)

**Bottom line: NC OneMap has clean, real, statewide coverage for both fire and
EMS stations across all 8 NC-08 counties. No manual per-county GIS-portal
collection is required.** This file was supposed to be a gap list per the task
instructions ("if not cleanly available for all 8 counties in one dataset, do
NOT fabricate placeholder locations — write a per-county TODO list instead").
It turned out not to be needed as a gap list — kept anyway, repurposed as a
coverage confirmation, because the instruction was to document *whatever is
found*, positive or negative.

Two separate statewide layers were checked on NC OneMap (both confirmed live
2026-09-22, both queried and returned real non-empty records for every one of
the 8 counties — see `data/pipelines/ems_fire_stations.py` and
`DATA_SOURCES.md` §6 for full source detail):

1. **NC Fire Stations** (NC Office of State Fire Marshal via NC OneMap)
2. **NC1Map_Emergency_Services**, layer 0 "Emergency Medical Services" (NC
   OneMap)

## Per-county coverage (live pull, 2026-09-22)

| County      | Fire stations | EMS stations | Status |
|-------------|---------------|---------------|--------|
| Anson       | 8             | 7             | ✅ covered |
| Cabarrus    | 32            | 33            | ✅ covered |
| Mecklenburg | 63            | 65            | ✅ covered |
| Montgomery  | 13            | 10            | ✅ covered |
| Richmond    | 13            | 15            | ✅ covered |
| Robeson     | 37            | 30            | ✅ covered |
| Stanly      | 21            | 23            | ✅ covered |
| Union       | 32            | 33            | ✅ covered |
| **Total**   | **219**       | **216**       | **435 combined** |

All 8 counties: `lat`/`lon`/`address` fields are 0% missing on the combined
processed output.

## Caveats (honest, not gaps in coverage — gaps in *certainty*)

- **No independent cross-check was performed against county-level GIS
  portals or 911 dispatch rosters.** The counts above are internally
  consistent (small counties have small counts, Mecklenburg/Charlotte has the
  most, nothing looks obviously wrong) but have not been verified against a
  second source. If the dashboard needs certified-accurate station counts
  (e.g., for an actual response-time model rather than a density overlay),
  spot-checking a sample against each county's own GIS/911 department is
  still worth doing — this is a reasonable-confidence statewide source, not a
  county-authoritative one.
- **Rural/volunteer department staleness risk (general, not county-specific):**
  statewide inventories like this one are typically compiled from state fire
  marshal / DOI licensing records, which are more likely to lag for small
  volunteer departments (station closures, address changes, mergers) than for
  large paid urban departments. No specific stale record was identified in
  this build; this is a general caveat about the *type* of source, not a
  finding.
- **EMS "stations" here means dispatch/basing locations, not hospitals** —
  the source layer explicitly excludes ambulance services co-located with and
  operated by a hospital (per the service's own description), so if the
  dashboard wants hospital-based EMS response points too, that is a
  genuinely separate, not-yet-covered data need.
- **Update cadence is not real-time** for either layer (fire layer's item
  metadata shows a 2025-11-20 last-modified date; EMS layer doesn't publish
  an explicit refresh cadence). Treat both as "recent, periodically
  refreshed," not live.

## If a manual per-county fallback is ever needed after all

In case a future revision of either NC OneMap layer drops coverage for a
specific county, or a stricter accuracy bar is needed, here is where to go
per county (not yet attempted — listed for completeness only, since it was
not needed this round):

| County      | County GIS portal (starting point for manual collection) |
|-------------|-----------------------------------------------------------|
| Anson       | Anson County GIS / Emergency Services department |
| Cabarrus    | Cabarrus County GIS |
| Mecklenburg | Mecklenburg County GIS / Charlotte Fire Department open data |
| Montgomery  | Montgomery County GIS |
| Richmond    | Richmond County GIS |
| Robeson     | Robeson County GIS |
| Stanly      | Stanly County GIS |
| Union       | Union County GIS |

None of these were used to build the current dataset — the NC OneMap layers
above were sufficient. This table exists only so a future contributor doesn't
have to rediscover "where do I even start" if a gap does appear later.
