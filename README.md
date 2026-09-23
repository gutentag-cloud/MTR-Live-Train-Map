# HK Train Operations v13.3

v13 is the geographic/ETA-stability revision of the Hong Kong live train operations display.

## Run

```bash
python3 serve_live.py
```

Open the localhost URL printed by the server (default `http://localhost:8080`). The Direct map, official ETA fusion, OSM tiles and weather overlays require internet access. EAL TMS telemetry additionally requires the same authorized HAR/API credential setup supported by the previous build.

## GitHub Pages vs live mode

The GitHub Pages deployment (https://gutentag-cloud.github.io/MTR-Live-Train-Map/) is served from a static host: it cannot run Python, so same-origin `/api/*` calls would return the host's HTML 404 page (seen previously as `Unexpected token '<' … is not valid JSON` / `HTTP 404` on the EAL and ETA badges).

`config.js` routes all `/api/*` calls to the Render backend declared in `render.yaml` when the page is hosted on `gutentag-cloud.github.io`, and keeps same-origin calls when `serve_live.py` hosts the page locally. Notes:

- The EAL TMS credential is configured **server-side only** — as `EAL_TMS_API_KEY` in the Render dashboard (never committed), or locally via a git-ignored HAR capture (`*.har`) picked up by `serve_live.py`.
- The Render free tier sleeps when idle; the first request after inactivity can take up to a minute while the service cold-starts. The UI retries automatically.

## v13.3 refinement

- Heavy-rail **Official MTR** positioning is reverted to the stable v13 nearest-line-pixel snap; the v13.1/v13.2 dense line-reconstruction algorithm is no longer used for train placement.
- Direct geographic view always shows a small clickable track-centred train dot while zoomed out; at close zoom it hands over to the physical-length train body.
- Station boards no longer present the MTR response second as exact prediction precision. The MTR ETA supplies the live arrival window, while matched WTT timing seconds plus the current line-delay model provide an explicitly labelled second-level estimate.
- Light Rail vehicle artwork is rotated onto the instantaneous GeoTD track tangent, with its cab facing the direction of travel.
- The Light Rail official-map tab now uses MTR's official system-map image and overlays clickable ETA-inferred dots snapped to coloured route pixels.

See `V13_3_FEATURES.md` and `QA_V13_3.md`.

## v13.1 refinement

v13.1 adds track-locked, physical-scale train geometry on the real map; HKT-only user-facing live timestamps; a current Tung Chung East track-topology path; and a heavy-rail-only, continuously path-snapped official-map overlay. See `V13_1_FEATURES.md` and `QA_V13_1.md`.

## What v13 changes

- **Direct map is actually geographic.** The OpenStreetMap view no longer warps GeoTD into latitude/longitude. It requests independent MTR geographic route GeoJSON and routes train markers along that graph. Until route geometry is available, dashed station chords are shown explicitly rather than a pseudo-geographic warp.
- **ETA correction no longer teleports trains.** Raw MTR ETA delay updates are retained for diagnostics but the displayed WTT correction is slew-limited, preventing abrupt position jumps when an ETA match changes.
- **Special EAL working diagnostics.** Late `EAL6240P` workings terminating at Lok Ma Chau after the normal control-point window are flagged for review rather than silently presented as ordinary passenger services.
- **Operations diagnostics expanded.** The Operations page counts absorbed ETA discontinuities and active special EAL workings.
- Existing GeoTD, calibrated schematic, official MTR overlay, station boards, speed/restriction model, headways, history replay, HKO radar, fleet view, Light Rail companion and EAL telemetry are retained.

See `V13_FEATURES.md` for implementation detail, `QA_V13.md` for release checks, and `LIVE_ACCURACY.md` for source/accuracy limitations. The old v12 documents remain in the package as historical notes only and do not describe the v13 Direct-map renderer.


## v13.1.1 direction correction

Train-model SVGs have their cab/front at the left edge. The GeoTD renderer rotates that intrinsic front by 180° onto the movement tangent, so the cab faces the next station instead of the previous station. Geographic route paths are also endpoint-validated against the current station pair and reversed automatically if a source geometry arrives backwards.

## v13.2 station interaction

Clicking a GeoTD station opens both the compact ETA panel and the full station board, with larger station hit targets and WTT fallback. v13.3 supersedes the old claim that the API-provided seconds themselves are exact.

## Map and usability refresh

This workspace includes faster progressive GeoTD images, corrected Light Rail marker centering and rotation, persistent route filters, per-stop arrival freshness, and a responsive map-first layout. See `QA_REFRESH.md` for validation and remaining data limitations.

Checks:

```bash
for t in tests/*.cjs; do node "$t"; done
for t in tests/test_*.py; do python3 "$t"; done
```

## Maintenance refinement (2026-09-23)

- `runtime/history.sqlite3` now uses incremental auto-vacuum. Before, the 24 h retention deleted rows but SQLite kept the freed pages, so a ~80 MB window sat in a ~480 MB file. Existing files are converted once at startup (about 1 s for 480 MB) and shrink every 10 minutes after that.
- The Light Rail page stops polling while its tab is hidden (30 s back-off) and fetches immediately when it becomes visible again.
- `tests/test_training.py` runs from any working directory.
