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
