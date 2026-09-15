# v13 QA / release checks

## Automated checks performed

- `node --check app.js` — pass.
- `node --check v12.js` — pass.
- `python -m py_compile serve_live.py v12_backend.py` — pass.
- Parsed `index.html` and verified every local `script`, `link`, and `img` reference exists — pass.
- Local server smoke test: `/api/health` returned HTTP 200 and `version: 13.0` — pass.
- Root page smoke test: HTTP 200 — pass.
- Geographic-route backend parser tested with injected valid GeoJSON — pass.
- Runtime external geographic-route request could not be integration-tested inside the build container because that environment has no outbound DNS. v13 therefore includes an explicit dashed geographic station-chord fallback; no GeoTD warp is used in Direct-map mode when the independent route feed is unavailable.

## Regression targets fixed

1. Direct-map track alignment is no longer produced by `geoWarpPoint()` / GeoTD anchor warping.
2. Train geographic position is computed on the independent route graph; if absent, it falls back to the geographic station chord.
3. ETA changes are no longer injected as an instantaneous `modelSec` discontinuity; the displayed correction is slew-limited.
4. `EAL6240P` late Lok Ma Chau workings are surfaced as operational anomalies without asserting an unsupported working type.

## Operational caveats

- MTR public ETA data is an arrival prediction feed, not a train-coordinate feed. Non-EAL train positions remain inferred between timing/ETA anchors.
- Exact classification of EAL timetable trip prefixes requires an authoritative prefix/working-code legend not present in this package.
- Direct geographic route geometry is network-delivered and cached by the local backend; OSM tiles also require internet access.
