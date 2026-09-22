# Map and usability refresh

## Implemented

- Corrected Light Rail's duplicate marker offset and measured path lengths/tangents in image pixels, respecting the 3163 × 4314 map proportions.
- Kept dwell positions on route endpoints; suppressed unsupported straight-line fallback geometry.
- Added map fit/zoom controls and compact overview dots for Light Rail.
- Added a fitted initial network view and retained sharper imagery after zooming back out.
- Added a 123 KiB GeoTD preview; deferred lossless 3.2K/6K upgrades until zoom settles. Removed automatic 13 MB full-map loading; original PDF remains available.
- Reduced Light Rail timetable payload from 3.8 MB to 509 KB and indexed matching by station.
- Fixed duplicate polling loops, request timeouts, route-filter resets, the delay-chart ReferenceError, pre-04:00 service-day selection, and ETA aging between polls.
- Kept matching observations from different routes/destinations separate.
- Preserved per-stop backend observation times so partial refreshes cannot refresh old cached arrivals.
- Official map uses its intrinsic aspect ratio and omits markers when no nearby route pixel is found.
- Refreshed typography, colors, spacing, responsive layout, keyboard focus, train list, and collapsible timetable coverage notes.

## Validation

- `node tests/regressions.cjs`: 360 geometry samples, endpoint positions, aspect-correct rotation, missing geometry, delay chart, observation ages.
- `python3 tests/test_lrt_freshness.py`: partial refresh preserves cached stop timestamps.
- JavaScript syntax and Python compilation checks passed.
- Browser: live arrivals, train details, route-filter persistence after Refresh, official image loading, fit controls, network zoom, and no console errors in checked flows.
- Browser at 390 px: both pages have no document-level horizontal overflow.
- Desktop layout visually inspected at 1440 × 900.

## Limits

Light Rail locations remain ETA/timetable estimates, not GPS. The timetable does not supply a guaranteed live vehicle-to-route identity. The official schematic still uses approximate regional calibration followed by route-pixel snapping; it cannot establish exact route identity at a junction. External feed availability and supplied timetable coverage remain dependencies.

Rebuild generated assets with `python3 tools/build_web_assets.py` (Pillow required).

## Arrival-board update

- Removed modulo-minute substitution of timetable seconds. A modeled time now requires a fresh medium/high live line-delay estimate, a matching terminal, a distinct timetable event, and agreement within 30 seconds of official ETA. Ambiguous matches retain the official estimate; no improvement in measured arrival accuracy is claimed.
- Shared display formatting shows official estimates to the minute and prefixes model predictions with ≈. Raw seconds are available via a comparison toggle.
- Added quick-board direction filter, user-selected platform walking time, approximate same-platform service gaps, per-row observation ages, manual refresh, and up to 12 locally saved stations.
- Prevented old station responses from replacing another station's board; excluded stale quick-board rows. The quick board uses live HKT independently of simulation/replay.
- Tests: eight Python regression cases, arrival-formatting checks, JavaScript syntax checks. Browser verified live model/official rows, UP filter, 5-minute walking check, raw timestamps, saved-station persistence and no console errors in checked flows.
- Source: MTR Next Train Data Dictionary v1.7 describes the time field as estimated arrival/departure time; its HH:mm:ss representation does not establish one-second prediction accuracy: https://opendata.mtr.com.hk/doc/Next_Train_DataDictionary_v1.7.pdf

## Full GeoTD and exploration controls

- Full 12000 × 10910 PNG is the default quality; lightweight preview remains visible while decoding. Automatic quality can be selected explicitly.
- Added station-name/code search with map centering, optional station labels, focus mode, double-click zoom, and keyboard map controls (+/−, arrows, 0 to fit; / to search; Escape to close details).
- Increased maximum GeoTD zoom to 16×. Main-map pan/wheel handlers no longer intercept controls or other map views.
- Verified full image intrinsic dimensions in browser, automatic-quality switching, station lookup, label toggle, focus enter/exit, and 390px layout without horizontal overflow.
- Existing eight Python tests, 360 geometry samples, arrival-format tests and JS syntax checks pass.

## Journey and sharing tools

- Added topology-based journey planner with fewer-changes / fewer-stops preferences, optional Airport Express, origin/destination swap, per-leg stop lists and live-arrival links.
- Added shareable `?station=CODE` URLs and a train-layer visibility toggle.
- Planner explicitly excludes real-time disruptions, fares, walking connections and operating-hour checks. No travel-time claims are synthesized from stop counts.
- Tests: direct route, interchange continuity, optimization preferences, excluded/included Airport Express, unknown and identical stations. Existing arrival and geometry tests pass.
- Browser verified journey → live board, deep links, train visibility and 390px planner layout with no horizontal document overflow.

## September 22 bug fixes

- Recompute journey results when any planning option changes and when reopening with a different starting station; validate identical unknown/excluded stations.
- Deduplicate overlapping station-board requests; ignore out-of-order responses and errors after a station or line selection changes. Add a 15-second timeout.
- Limit the geographic train visibility switch to train-specific panes, preserving other map markers.
- Regression tests cover duplicate requests, stale successes/errors, and invalid planner endpoints. Browser verified automatic route updates and no console errors in the checked flow.
