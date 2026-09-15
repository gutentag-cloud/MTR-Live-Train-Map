# v12 PREVIEW QA report

## Static checks

- `node --check app.js` — pass
- `node --check v12.js` — pass
- `node --check light_rail.js` — pass
- `node --check v12_geo_data.js` — pass
- `python3 -m py_compile serve_live.py v12_backend.py tools/build_v12_assets.py` — pass
- generated v12 schematic is valid XML/SVG
- every full public heavy-rail station has a station name and line membership
- all train-model asset paths resolve
- no `.git`, HAR, `.env`, runtime SQLite or production deployment config is included

## Geometry checks

- Real-map route data is generated from `TRAIN_DATA.trackRoutes` rather than straight station chords.
- Geographic transformed route endpoints exactly equal their station WGS84 anchors.
- Vector schematic SVG and train overlay consume the same v12 official-coordinate table.
- Official and vector modes share the same station graph/path logic, so a train between non-adjacent WTT timing points passes through intermediate schematic stations.
- GeoTD train markers receive a local tangent angle from the exact active GeoTD polyline segment.

## Startup/resilience

- Initial HTML no longer includes render-blocking Leaflet JS/CSS.
- initial GeoTD source is 3.2K; higher resolutions are demand-loaded by zoom.
- geographic station/track geometry is local; ArcGIS and Overpass are not startup dependencies.
- radar metadata/image requests are lazy and only begin when Radar is enabled.
- WTT remains the final fallback when live sources are unavailable.

## ETA behavior

- `/api/station-board` accepts the complete v12 public heavy-rail station catalogue.
- recent network station cache can be returned immediately, with refresh performed in the background.
- API timestamps retain second fields and the UI countdown is re-rendered against the running service clock.

## Limits

This environment cannot exercise the user's own browser/CDN path or the external MTR/HKO/OSM hosts end-to-end. External layers therefore remain graceful network dependencies; local GeoTD, local schematic and WTT operation remain available without them.


## Performance hotfix QA

- `app.js`, `v12.js`, `light_rail.js`: Node syntax checks passed.
- `serve_live.py`, `v12_backend.py`: Python compile checks passed.
- Local smoke test: `/` returns HTTP 200 and `/api/health` returns JSON immediately while live workers warm in background.
- Weekday active-trip index: 7,661 total trips -> median 438 candidates per 5-minute bucket, p95 662, max 678 (with ±1,200 s delay margin).
- No startup 120-minute history fetch; history loads on demand.
