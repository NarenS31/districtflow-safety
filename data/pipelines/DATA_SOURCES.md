# DistrictFlow Safety — Data Sources

Scope: NC's 8th Congressional District (2026 map) — Union, Cabarrus, Stanly,
Montgomery, Anson, Richmond, Mecklenburg, Robeson counties.

**Provenance rule this file exists to satisfy:** every source below was
queried LIVE on **2026-09-22** from this build environment and confirmed to
return real, non-empty, NC-08-scoped records before any pipeline script was
written against it. Nothing in this project reads from a URL that was not
verified this way. Where a source could not be verified live (OSM/Overpass),
that is stated explicitly below and in the corresponding pipeline script —
never silently worked around with fabricated data.

---

## 1. Road network — NCDOT Integrated Statewide Road Network (ISRN)

- **Service:** `NCDOT_RoadCharacteristicsQtr`, layer 0
- **URL:** `https://gis11.services.ncdot.gov/arcgis/rest/services/NCDOT_RoadCharacteristicsQtr/MapServer/0`
- **Pipeline:** `data/pipelines/isrn_roads.py`
- **What it is:** NCDOT's published attribute extract of its Esri Roads &
  Highways system (the actual ISRN linear-referencing database) — road
  characteristics generated quarterly. One row per segment, re-split every
  time an attribute (speed limit, lane count, surface, ...) changes along a
  route.
- **No literal "ISRN" service exists** in NCDOT's public ArcGIS Online org
  (`services.arcgis.com/NuWFvHYDMVmmxMeM`, 993 services, grepped
  exhaustively for ISRN/LRS/Route/Roadway/Centerline keywords — no match).
  This host (`gis11.services.ncdot.gov`, NCDOT's own server, separate from
  the AGOL org) is what NC OneMap itself points to for "NCDOT Road
  Characteristics," and is the ISRN's public-facing product.
- **License/attribution:** NCDOT, public agency data; standard "data
  courtesy of NCDOT" attribution.
- **Update cadence:** quarterly (per service name "Qtr").
- **Fields used:** `RouteName`, `StreetName`, `MaintCntyCode` (county filter —
  see below), `RouteClass`, `FuncClass` (FHWA functional classification 1–7),
  `SpeedLimit`, `DesignSpd`, `ThruLaneCount`, `PeakLanes`, `LaneWidth`,
  `SrfcType`, `UrbanType`, `AADT`, `AadtDate`, `BeginMp1`, `EndMp1`, `RouteID`.
  (107 fields exist on this layer total; only the above are pulled.)
- **County filter:** `MaintCntyCode IN (...)`, a documented 3-digit
  *alphabetical NC county code* field (001=Alamance … 100=Yancey — **not**
  federal FIPS). Codes for the 8 counties were read directly from the live
  field's `codedValues` domain, not hand-typed:
  Anson=004, Cabarrus=013, Mecklenburg=060, Montgomery=062, Richmond=077,
  Robeson=078, Stanly=084, Union=090.
- **Confirmed live:** 157,807 matching segment records for the 8 counties
  (`returnCountOnly` query, 2026-09-22); live extent (WGS84) xmin −81.067,
  ymin 34.296, xmax −78.820, ymax 35.526 — this is also the source of
  `configs/data.yaml`'s NC-08 bounding box (padded ~0.02°).
- **Confirmed live (actual pipeline run, 2026-09-22):** **157,807 records**
  across the 8 counties (Mecklenburg 72,048, Union 19,908, Cabarrus 19,783,
  Robeson 17,719, Stanly 8,926, Richmond 8,359, Montgomery 5,751, Anson
  5,313). Functional class breakdown: Local 110,705, Minor Arterial 12,197,
  Major Collector 11,978, Other Principal Arterial 11,364, Interstate 5,847,
  Minor Collector 4,677, Other Freeway/Expressway 1,025.
- **Known gaps:** `SpeedLimit` is missing on **58.4%** of segments,
  `ThruLaneCount` on **45.6%**, `SrfcType` on **44.8%** (stored as 0, which the
  pipeline converts to missing — 0 mph/0 lanes is not a real recorded value).
  `osm_fallback.py` exists specifically to supplement these gaps (see §4).
  This layer's own `AADT` field is also **73.2% missing** — far sparser than
  the dedicated `aadt.py` source (0% missing on its `AADT` field), which is
  the concrete reason `aadt.py` pulls a separate AADT-specific service rather
  than reusing this table's embedded AADT column.

## 2a. General crashes — NCDOT Statewide Crash Table

- **Service:** `StatewideCrashTable`, **table index 3** (this service has
  `tables: [(3, "export - Statewide Crash Table.csv")]` and no layers at all —
  querying the usual default `/0` returns nothing; the URL below is pinned to
  `/3` deliberately).
- **URL:** `https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/StatewideCrashTable/FeatureServer/3`
- **Pipeline:** `data/pipelines/crashes_general.py`
- **What it is:** every reportable NC motor-vehicle crash, county/year
  granularity, with severity, involvement flags (incl. `PedInvolved`/
  `BikeInvolved`), and fatality/injury counts by category.
- **License/attribution:** NCDOT / NC Division of Motor Vehicles crash
  reporting system; public agency data.
- **Update cadence:** appears to update continuously through the current
  year (2026 already had 37,675 NC-08 records as of the pull date).
- **Fields used:** `Crash_ID`, `Date`, `Year`, `Month`, `County`, `City`,
  `CrshSeverity`, `NumFatalities`, `NumAInjuries`, `NumBInjuries`,
  `NumCInjuries`, `PedFatalities`, `PedSeriousInjuries`, `BikeFatalities`,
  `BikeSeriousInjuries`, `CrashType`, `SpeedRelated`, `PedInvolved`,
  `BikeInvolved`.
- **County filter:** `County IN ('Union','Cabarrus',...)` (plain county name,
  title case, confirmed against live sample values).
- **Year filter — "5 most recent finalized years" = 2021–2025:** live
  per-year NC-08 record counts (2026-09-22 pull): 2021=60,431, 2022=61,225,
  2023=63,383, 2024=62,530, 2025=59,934, **2026=37,675**. 2026's count is
  ~60% of a finalized year's, consistent with 2026 still being a partial,
  accumulating year — excluded. 2021–2025 are all in a tight, mutually
  consistent range and treated as finalized.
- **Confirmed live (actual pipeline run, 2026-09-22):** **307,503 records**
  across the 8 counties, 2021–2025 (Mecklenburg 201,315, Cabarrus 30,368,
  Union 30,191, Robeson 24,426, Stanly 7,487, Richmond 6,635, Anson 4,161,
  Montgomery 2,920). `PedInvolved='Y'` → 2,755 records, `BikeInvolved='Y'` →
  820 records.
- **Known gaps / cross-check note:** the ped/bike involvement counts above
  are in the same ballpark as, but do **not** exactly match,
  `crashes_pedcyclist.py`'s totals (2,322 pedestrian + 866 bicyclist = 3,188
  vs. 2,755 + 820 = 3,575 here) — the two tables are built by NCDOT via
  different extraction pipelines (StatewideCrashTable is a general export;
  NonMotoristCrashes is purpose-built for non-motorist analysis), so this
  size of divergence (~12%) is expected and was checked, not ignored. A much
  larger divergence would be worth investigating before trusting either
  number on the dashboard.

## 2b. Pedestrian/cyclist crashes — NCDOT Non-Motorist Crashes

- **Service:** `NCDOT_NonMotoristCrashes`, layer 0
- **URL:** `https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/NCDOT_NonMotoristCrashes/FeatureServer/0`
- **Pipeline:** `data/pipelines/crashes_pedcyclist.py`
- **What it is:** individual pedestrian/cyclist-involved crash records
  (one row per crash) with coordinates — the dashboard's PRIMARY ped/cyclist
  incident source.
- **Why not the "HSIP_BIKEPED"/"HSIP_BP" family the task brief flagged as a
  likely lead** (`2020_HSIP_BIKEPED`, `2024_HSIP_BikePed`, `2022_HSIP_BP_ADDS`,
  `2025_HSIP_BP`, `NC_2026_HSIP_BP`, etc. — all confirmed live and real): these
  are NCDOT Highway Safety Improvement Program **candidate infrastructure
  project sites** — engineering-prioritized locations recommended for safety
  funding — **not** a record of individual crash events. `NCDOT_NonMotoristCrashes`
  is the actual per-crash table (presumably one of the inputs HSIP's own
  prioritization is built from). The HSIP layers are a real, separate,
  "known high-priority sites" data source that could be layered onto the
  dashboard later; they are **not** pulled by any current pipeline (documented
  gap, not silently substituted for crash data).
- **License/attribution:** NCDOT; public agency data.
- **Update cadence:** appears to update through the current year at the
  county level, though `CrashYear` here tops out at 2025 with zero 2026
  records (unlike StatewideCrashTable's visibly-partial 2026) — 2025 should
  be read as "as complete as this table currently is," not guaranteed final;
  NC crash data commonly carries a reporting/QA lag of several months to
  a year, so late-2025 records especially may still see minor revisions.
- **Fields used:** `CrashID`, `CrashDate`, `CrashYear`, `CrashSevr`, `NM_Type`
  (Pedestrian / Bicyclist / Other Cyclist / Scooter / Wheelchair / Skateboard
  / Other), `NM_Age`, `NM_Sex`, `NM_Inj`, `BikeDir`, `SpeedLimit`, `RdClass`,
  `RdCharacte`, `RdConditio`, `LightCond`, `Weather`, `Latitude`, `Longitude`,
  `County`, `City`.
- **County filter:** `County IN (...)`, plain title-case county name.
- **Year filter:** same 2021–2025 window as §2a (this table's live max
  `CrashYear` is 2025 with no 2026 records at all, so 2026 is trivially
  excluded — not even a judgment call).
- **Confirmed live (actual pipeline run, 2026-09-22):** **3,454 records**
  across the 8 counties, 2021–2025. County breakdown: Mecklenburg 2,606,
  Robeson 261, Cabarrus 217, Union 186, Richmond 86, Stanly 47, Anson 28,
  Montgomery 23. Type breakdown: Pedestrian 2,322, Bicyclist 866, other
  micromobility/other 266. 0% missing on every field pulled.
- **Known gaps:** heavy skew toward Mecklenburg (Charlotte) simply reflects
  real population/traffic density, not a data-quality issue — but it means
  Robeson, Anson, Montgomery, and Stanly have far sparser records and any
  per-capita/per-mile rate computed on them will have much higher variance.
  Flag this explicitly in the dashboard rather than showing raw counts
  side-by-side with Mecklenburg's.

## 3. AADT — NCDOT 2025 AADT and Traffic Segments

- **Service:** `NCDOT_2025_AADTandTrafficSegments_gdb`, layer 0
- **URL:** `https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/NCDOT_2025_AADTandTrafficSegments_gdb/FeatureServer/0`
- **Pipeline:** `data/pipelines/aadt.py`
- **What it is:** one static annual-average daily traffic-volume figure per
  road segment (2025 vintage) — the exposure denominator for crash-RATE (not
  just raw crash-count) scoring.
- **Why this service over `NCDOT_AADT_Stations`** (also live/real): Stations
  is point data at fixed count-station locations with one column per year
  (`AADT_2002`..`AADT_2022`, stored as strings, 3+ years stale relative to
  this 2026 build). The 2025 segments service matches `isrn_roads.py`'s unit
  of analysis (linear segments) and is NCDOT's newest published AADT product.
  Stations is not pulled by any pipeline (documented, not silently dropped).
- **License/attribution:** NCDOT; public agency data.
- **Update cadence:** annual (2025 vintage; presumably superseded by a 2026
  release on the same cadence as future NCDOT publications).
- **Fields used:** `TSegID2025`, `RouteID`, `BeginMP`, `EndMP`, `AADT`,
  `AADTT` (truck AADT), `AADT_Year`, `SU_AADT`, `MU_AADT`.
- **Filter method: BOUNDING BOX, not county** — this layer has **no county
  attribute at all** (confirmed via live field schema). Filtered via
  `configs/data.yaml`'s NC-08 bbox (itself derived from the live, exact,
  county-attributed `isrn_roads` extent). A representative segment midpoint
  is computed from the polyline geometry and double-checked against the bbox
  after reprojection to drop any segment whose midpoint falls just outside it.
- **Confirmed live (actual pipeline run):** 7,975 raw records in the bbox →
  7,861 after the midpoint-in-bbox check (114 dropped as bbox-edge
  false-positives). AADT range 10–207,000 vehicles/day, median 3,300.
  `AADTT`/`SU_AADT`/`MU_AADT` are ~75% missing (only measured on segments
  NCDOT independently classifies by vehicle type, mostly higher-class roads).
- **Known gaps:** because this is bbox-filtered (not county-exact), a small
  number of segments just across a county line from NC-08 but inside the
  padded bbox may be included; and conversely no ISRN-style exact-boundary
  guarantee exists for this source the way it does for county-attributed ones.

## 4. OpenStreetMap — Overpass API (supplemental / fallback ONLY)

- **Endpoint (as specified in the task):** `https://overpass-api.de/api/interpreter`
- **Pipeline:** `data/pipelines/osm_fallback.py`
- **What it's for:** filling `SpeedLimit`/`ThruLaneCount` gaps left by ISRN,
  plus pulling `sidewalk`/`cycleway` tags ISRN doesn't carry at all — used
  **only** to supplement, never as a primary source.
- **STATUS: WRITTEN BUT NOT VERIFIED LIVE IN THIS BUILD ENVIRONMENT.** The
  task described this endpoint as "confirmed reachable," but from this
  specific sandbox, `overpass-api.de:443` refused the TCP connection outright,
  and every public mirror tried (`overpass.kumi.systems`,
  `overpass.private.coffee`, `lz4.overpass-api.de`, `z.overpass-api.de`,
  `overpass.openstreetmap.ie`) either timed out or, for
  `overpass.openstreetmap.fr`, returned `403 whitelist-only`. One mirror,
  `overpass.osm.ch`, returned `HTTP 200` but a **literal empty result set**
  even for a `maxspeed` query over central Berlin — one of the highest-density
  OSM areas on Earth — indicating that mirror is itself non-functional
  (stub/placeholder database), not that the query was wrong. General internet
  egress from this environment is otherwise fine (`google.com`,
  `api.github.com`, `openstreetmap.org` itself all responded normally) — the
  issue is specific to Overpass query endpoints from this sandbox.
  `osm_fallback.py` is written correctly against standard Overpass QL/HTTP
  conventions and is config-driven like every other pipeline; **it should be
  re-run in an environment with working Overpass access, and its output
  re-verified, before the dashboard relies on it.** This is stated here
  plainly rather than faking a sample response.
- **License:** OpenStreetMap contributors, ODbL (must attribute "© OpenStreetMap
  contributors" wherever OSM-derived data is shown).

## 5. Live incident overlay — NCDOT TIMS (current conditions only)

- **Service:** `NCDOT_TIMS_Incidents`, layer 0
- **URL:** `https://services.arcgis.com/NuWFvHYDMVmmxMeM/arcgis/rest/services/NCDOT_TIMS_Incidents/FeatureServer/0`
- **Pipeline:** `data/pipelines/tims_overlay.py` (deliberately a **thin
  puller only** — overwrites a single "current snapshot" output file on every
  run, never accumulates a history)
- **What it is:** active/current NCDOT traffic incidents (roadwork, closures,
  crashes-in-progress, weather restrictions) — a live "what's happening right
  now" overlay, not archived training data. TIMS does not archive; NCDOT
  separately publishes `NCDOT_TIMSIncidentsHistory` (also live) but it is
  intentionally **not** pulled here, per the task's explicit scope limit
  ("just document how to pull it if you find a public JSON/API endpoint;
  don't build a full historical pipeline around it").
- **Alternate/documented access path:** DriveNC.gov's own public REST API —
  `https://www.drivenc.gov/help/endpoint/event` (confirmed live; the legacy
  `eapps.ncdot.gov/services/traffic-prod/v1/incidents` host now returns a
  deprecation notice pointing to this doc page as of May 27, 2026). The
  ArcGIS FeatureServer above returns the same class of incident data via a
  stable, unauthenticated, directly-queryable endpoint (and even carries a
  `DriveNCLink` field back to the DriveNC.gov page for each event), so it is
  used as the primary puller; the DriveNC.gov doc URL is kept in
  `configs/data.yaml` as the documented fallback if NCDOT ever retires this
  ArcGIS mirror.
- **License/attribution:** NCDOT; public agency data.
- **Update cadence:** real-time / as-events-change.
- **Fields used:** all (`Road`, `Reason`, `Condition`, `Detour`,
  `DriveNCLink`, `Latitude`, `Longitude`, `EventName`, `LanesAffected`,
  `EventType`, `EventSubType`, `StartDateTime`, `EndDateTime`,
  `LastUpdateDateTime`, `IsFullClosure`, `Direction`, `RouteType`,
  `CountyName`, `Location`).
- **Confirmed live (actual pipeline run, 2026-09-22 ~20:11 UTC):** 75 active
  incidents in NC-08 at pull time — Mecklenburg 47, Robeson 21, Cabarrus 5,
  Richmond 1, Anson 1 (Union/Stanly/Montgomery had zero active incidents at
  that moment, which is an expected, valid outcome for a live snapshot, not a
  fetch failure). Event types: roadwork 52, closures 23; 0 full closures.
- **Known gaps:** `Reason` is 77% missing (many roadwork/closure entries don't
  carry a free-text reason) — expected for this feed, not a fetch bug.

## 6. Fire & EMS stations — NC OneMap (two statewide layers)

- **Pipeline:** `data/pipelines/ems_fire_stations.py`
- **See `EMS_STATIONS_TODO.md` for the full per-county table.** Summary: NC
  OneMap DOES have clean statewide coverage for both fire and EMS across all
  8 NC-08 counties — no manual per-county collection was needed.
- **Fire — NC Fire Stations:**
  `https://services5.arcgis.com/yCv672AxcRF0kngG/arcgis/rest/services/NC_Fire_Stations/FeatureServer/0`.
  Maintained by the NC Office of State Fire Marshal (part of the "9S fire
  rating program," 11 NCAC 05A.0901) via NC OneMap. Fields used: `FD_ID`,
  `DEPT_NAME`, `STATION_NUMBER`, `STATION_ADDRESS`, `CITY`, `COUNTY`,
  `LATITUDE`, `LONGITUDE`. Confirmed live: 219 stations across the 8 counties.
- **EMS — NC1Map_Emergency_Services, layer 0 ("Emergency Medical
  Services"):**
  `https://services.nconemap.gov/secure/rest/services/NC1Map_Emergency_Services/FeatureServer/0`
  (the `secure` in the path is misleading — this layer is publicly queryable
  with no auth, confirmed live). Includes private and government EMS/ambulance
  bases. Native spatial reference is NC State Plane meters (wkid 32119) — the
  pipeline requests `outSR=4326` and reads reprojected geometry rather than
  trusting the raw `x`/`y` attribute columns, which are in meters, not
  degrees (an easy silent-unit bug, flagged in the pipeline's own comments).
  Fields used: `name`, `telephone`, `address`, `city`, `county`, `fips`,
  `type`, `specialty`, `numabul`, `totalpers`. County values are stored
  **UPPERCASE** (`"MECKLENBURG"`, not `"Mecklenburg"`) — handled via
  `configs/data.yaml`'s `counties.nc08_upper`. Confirmed live: 216 stations
  across the 8 counties.
- **License/attribution:** NC OneMap / NC Office of State Fire Marshal / NC
  Department of Insurance; public agency data.
- **Update cadence:** fire layer last modified per its item metadata
  2025-11-20 (recent); EMS layer's exact refresh cadence not stated on the
  service itself — treat as "periodically refreshed," not real-time.
- **Known gaps:** rural/volunteer department records are generally more
  likely to be stale in ANY statewide inventory than urban paid departments —
  flagged as a caveat, not a confirmed problem (no specific stale record was
  identified in this build).

---

## Environment / dependency notes

- Checked with `pip3 list` / `python3 -c "import ..."` before building:
  `requests`, `pandas`, `numpy`, `pyyaml` were **not** pre-installed in the
  system Python (Homebrew Python 3.14, PEP 668 externally-managed — direct
  `pip install` is blocked without `--break-system-packages`).
- A project-local virtualenv was created at `.venv/` (`python3 -m venv .venv`)
  and `requests`, `pandas`, `numpy`, `pyyaml` installed into it. Run pipelines
  with `.venv/bin/python -m data.pipelines.<name>` (or activate the venv
  first). This keeps the system Python untouched.
- All pipeline code is written to be Python 3.9-compatible (no `X | Y` union
  syntax; `typing.Optional`/`Dict`/`List` used throughout) even though the
  dev venv itself runs 3.14 — verified by inspection, not by an actual 3.9
  interpreter run (none was available in this environment: only 3.11 and
  3.14 are installed via Homebrew).
