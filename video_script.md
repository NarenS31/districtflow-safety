# AfterImpact NC — Congressional App Challenge Demo Video Script

**Target runtime: ~2:00–2:15** (CAC hard limit is 3:00 — this script is
deliberately timed with margin below that, since a first-time narrator
usually runs slower than a written word-count estimate, not faster).

**Before recording:** fill in `[TEAM NAME]` everywhere it appears below —
that's the one piece of required content this script cannot supply, since
it's not something in the project data. Everything else spoken is pulled
directly from the real files in `dashboard/public/data/` (see the
verification appendix at the bottom — check those numbers against the live
dashboard right before you record, in case the pipeline has been re-run
since this was written).

---

## Shot list

### Scene 1 — Open
**0:00–0:12 (~12s)**

**On screen:** App loads on the full-bleed map, already centered/zoomed on
the Cabarrus County cluster so Alvin Hough Rd's colored line is visible
without extra panning. Team/project name as a text overlay in the first
2–3 seconds.

**Spoken:**
> "Hi, we're [TEAM NAME] — this is AfterImpact NC. Out of fifty-seven
> hundred forty-four road segments we scored across North Carolina's 8th
> Congressional District, this one — Alvin Hough Road — came out highest
> for pedestrian and cyclist risk."

**Data point referenced:** `meta.json` → `n_segments: 5744`;
`priority_list.json` rank 1 → `segment_name: "Alvin Hough Rd (Cabarrus)"`.

---

### Scene 2 — Problem / purpose / audience
**0:12–0:32 (~20s)**

**On screen:** Brief pull-back on the map (or hold on the same view) —
this scene is carried by narration, not new visuals, so don't rush a
camera move here.

**Spoken:**
> "AfterImpact NC scores every road in the district for real pedestrian
> and cyclist crash risk, then combines that with how far it is from the
> nearest EMS station — so county planners and safety engineers can see
> not just where it's dangerous, but where it's dangerous *and* help is
> far away."

**Data point referenced:** none specific — this is the purpose statement
(matches the README's "Risk-Exposure Index" framing).

---

### Scene 3 — Live demo (the centerpiece)
**0:32–1:24 (~46s spoken + ~6s of click/animation dead time = ~52s)**

**On screen, beat by beat:**
1. Click the #1 row in the leaderboard ("Alvin Hough Rd (Cabarrus)").
   *(Hold ~1s — let the map's flyTo animation and amber selection
   highlight actually play out before talking over it.)*
2. Detail panel slides in; Risk-Exposure score is visible (`1.186`) with
   the feature-attribution bars underneath.
3. Click the **"25 mph speed limit"** pill under "What if?"
   *(Hold ~1–2s on the strikethrough → new-value transition.)*

**Spoken:**
> "Let's click into it. The panel shows a Risk-Exposure score of 1.186 —
> the highest in the district — and it tells us why: Cabarrus County has
> logged over 30,000 crashes in the last five years, and the nearest EMS
> station is almost four miles away by actual road distance, not a
> straight line. Now let's simulate lowering the speed limit here. Watch
> the score — it barely moves. That's the model being honest with us: for
> this segment, the real danger isn't the speed limit, it's the county's
> crash history and how far away help is. A flat priority list would've
> just told us to post a new sign. Ours tells us why that wouldn't be
> enough."

**Data point referenced:**
- `priority_list.json` rank 1 → `risk_exposure_score: 1.1861`
- Same entry, `top_features[0]` → `general_crash_count_5yr_county: 30368.0`
- Same entry, `top_features[1]` → `ems_distance_m: 6202.7393` (≈3.85 mi)
- `counterfactuals.json["28317"]["reduce_speed_limit_25"]` →
  `baseline_risk_score: 0.0076`, `updated_risk_score: 0.0076`,
  `delta: 0.0` (confirmed exactly 0.0 at 4 decimal places — this is the
  real, computed number, not an approximation)

**Why this framing, not a "bigger" fake number:** every one of the real
Top-25 segments shows a delta of exactly `0.0000` for both speed-limit
interventions (checked directly against the real data, not assumed) —
`add_crosswalk`/`add_sidewalk`/`add_lighting` aren't real data yet either
(blocked on an OSM/Overpass pull, documented in the README's Limitations).
Rather than picking a misleadingly "impressive" moment that doesn't exist
in the real output, this script uses the honest null result as the actual
point: the tool tells a viewer *when* an intervention won't help, and
*why* — which is a stronger, more credible demo beat for a judged
competition than a fabricated win.

---

### Scene 4 — Impact / civic-differentiation
**1:24–1:44 (~20s)**

**On screen:** Switch the left panel to the "Disparity" tab — the bar
chart and callout text are the visual here.

**Spoken:**
> "Zoom out, and the pattern gets bigger: rural segments in our district
> score forty-four percent of suburban and urban ones on Risk-Exposure —
> but that's not because rural roads are safer. Rural counties simply
> have far sparser crash reporting, and our tool flags that gap instead
> of hiding it."

**Data point referenced:** `disparity.json.gap` →
`rural_vs_suburban_exposure_ratio: 0.4444` (spoken as "forty-four
percent"); `rural_vs_suburban_confidence_gap_pct: 4.9` (available if you
want a second sentence — see "what to cut" section for whether to include
it).

---

### Scene 5 — Tech stack / what's next / sign-off
**1:44–2:02 (~18s)**

**On screen:** Quick cut back to the full map view, or a brief GitHub repo
shot, then a closing title card with team name + project name.

**Spoken:**
> "We built the risk model in PyTorch — a graph neural network trained on
> real NCDOT crash and traffic data — and the dashboard in React and
> MapLibre. Next, we want real crosswalk and sidewalk data wired in.
> We're [TEAM NAME] — thanks for watching."

**Data point referenced:** `requirements.txt` (`torch==2.14.0`, `numpy`,
`pandas`, `scipy`); `dashboard/package.json` (`react`, `maplibre-gl`,
`vite`, `tailwindcss`, `recharts`); real data sources named in
`data/pipelines/DATA_SOURCES.md` (NCDOT ISRN/AADT/crash tables).

---

## Total runtime estimate

| Scene | Spoken time | Screen-action time | Scene total |
|---|---|---|---|
| 1. Open | ~12s | — | ~12s |
| 2. Problem/purpose | ~20s | — | ~20s |
| 3. Live demo | ~46s | ~6s (clicks + flyTo + panel slide) | ~52s |
| 4. Disparity | ~19s | ~1s (tab switch) | ~20s |
| 5. Tech/close | ~17s | ~1s (cut to title card) | ~18s |
| **Total** | **~114s** | **~8s** | **~122s ≈ 2:02** |

This is calculated at a natural ~150 words/minute spoken pace (already
slower than a script-read pace, to account for a real narrator, not a
professional voiceover). **2:02 leaves just under a minute of margin
below CAC's 3:00 hard cutoff** — comfortable, but if your actual recorded
take runs long (very common for a first take — nerves and re-takes both
slow real speech down), cut in this order:

1. **First cut — Scene 2's second half.** Drop "so county planners and
   safety engineers can see not just where it's dangerous, but where it's
   dangerous *and* help is far away" down to "...so planners can see not
   just where it's dangerous, but where help is hardest to reach." Saves
   ~4s.
2. **Second cut — Scene 3's last two sentences.** Drop "A flat priority
   list would've just told us to post a new sign. Ours tells us why that
   wouldn't be enough." — the point is already made by "that's the model
   being honest with us." Saves ~8s.
3. **Third cut — Scene 5's tech detail.** Drop "a graph neural network
   trained on real NCDOT crash and traffic data" down to "a graph neural
   network on real NCDOT data." Saves ~3s.

Do **not** cut Scene 1 (team/project name), Scene 3's core demo beat, or
Scene 4's disparity number — those are the required-content and
differentiation beats respectively.

---

## Appendix: real numbers to verify before recording

Re-check every number below against the **live dashboard**
(districtflow-safety.vercel.app) immediately before recording — the
underlying data was correct as of this script's writing, but if the
pipeline gets re-run with new data (e.g. once the OSM crosswalk/sidewalk
pull lands), these will change and the script needs updating to match.

| # | Number used in script | Source file | Exact field |
|---|---|---|---|
| 1 | 5,744 total segments | `dashboard/public/data/meta.json` | `n_segments` |
| 2 | "Alvin Hough Rd (Cabarrus)" is rank #1 | `dashboard/public/data/priority_list.json` | `[0].segment_name`, `[0].rank` |
| 3 | Risk-Exposure score **1.186** | `dashboard/public/data/priority_list.json` | `[0].risk_exposure_score` (1.1861, displayed as 1.186 in the UI's 3-decimal format) |
| 4 | Cabarrus County crash count **"over 30,000"** | `dashboard/public/data/priority_list.json` | `[0].top_features[0].value` (30368.0, feature `general_crash_count_5yr_county`) |
| 5 | EMS distance **"almost four miles"** | `dashboard/public/data/priority_list.json` | `[0].top_features[1].value` (6202.7393 meters = 3.85 miles, feature `ems_distance_m`) |
| 6 | Speed-limit counterfactual **delta = 0.0000** (no meaningful change) | `dashboard/public/data/counterfactuals.json` | `["28317"]["reduce_speed_limit_25"].target.delta` — verified this is `0.0` for **all 25** Top-25 segments, not just this one |
| 7 | Rural Risk-Exposure = **44% of** suburban/urban | `dashboard/public/data/disparity.json` | `gap.rural_vs_suburban_exposure_ratio` (0.4444) |
| 8 | (optional, not currently spoken) rural low-confidence gap = **+4.9 percentage points** | `dashboard/public/data/disparity.json` | `gap.rural_vs_suburban_confidence_gap_pct` (4.9006) |
| 9 | Tech stack: PyTorch, React, MapLibre, Vite, Tailwind, Recharts | `requirements.txt`, `dashboard/package.json` | full dependency lists |
| 10 | Real data sources: NCDOT ISRN/AADT/crash tables, NC OneMap EMS stations | `data/pipelines/DATA_SOURCES.md` | full per-source writeup |

**Not yet real, don't claim it on camera:** crosswalk, sidewalk, and
lighting features are written into the pipeline (`data/pipelines/
osm_fallback.py`) but blocked on Overpass API access in the current build
environment — if you click "Add crosswalk" during a live demo, the app
will honestly show "No feature matching 'crosswalk' found for this
segment — intervention not simulated," which is correct behavior, not a
bug. Don't script around clicking that pill unless you want to show that
honesty explicitly (it's a legitimate thing to point out, just wasn't
included in this cut to keep runtime down).
