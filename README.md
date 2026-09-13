# HK Train Operations Display v9.3

A local-first Hong Kong railway operations visualization built from the supplied Working Timetables and GeoTD track diagram, augmented with public/live data when available.

## Run

Recommended:

```bash
python3 serve_live.py
```

Then open `http://localhost:8080`.

For EAL TMS telemetry, keep the previously captured `eal-tms.rocteccloud.com.har` beside this folder, pass it with `--har`, or set `EAL_TMS_API_KEY` / `EAL_TMS_URL` in the environment. The upstream credential is read server-side and is never emitted to the browser.

The site can also be opened as `index.html` directly. In that case all trains remain available in WTT fallback mode, but live APIs and persistent history require `serve_live.py`.

## Data hierarchy

1. **EAL:** RocTec TMS normalized telemetry when available and fresh.
2. **Heavy rail:** official MTR Next Train API fused to the supplied WTT.
3. **Light Rail:** official MTR Light Rail arrivals fused to the supplied LR WTT.
4. **Fallback:** supplied WTT + GeoTD track-following geometry.

The UI always identifies whether a train is `TMS`, `ETA`, arrival-inferred, or `WTT`.

## Train information

Click any train to open a full inspector containing identity/direction, operating state, current speed, acceleration/braking model, segment progress, distances to adjacent timing points, speed limits, origin/destination, journey distance, next-stop scheduled/predicted times, headway/spacing, speed-vs-distance profile and delay trend. EAL additionally exposes the direct TMS telemetry fields available in the captured feed.

The **Operations** tab provides line-level active counts, source confidence, ETA offsets, trends, service-gap/bunching detection, late-running flags and recovery/worsening alerts.

The **History** selector replays captured live/ETA state at approximately -5, -15, -30 or -60 minutes. `serve_live.py` keeps a sanitized rolling 24-hour SQLite history under `runtime/history.sqlite3`.

See `OPERATIONS_FEATURES.md`, `LIVE_ACCURACY.md` and `DATA_COVERAGE.md` for methodology and limitations.

## Important accuracy distinction

- EAL TMS fields such as speed/power/brake/ATO are telemetry.
- Other heavy-rail positions remain WTT trajectories corrected with official arrival predictions; they are not GPS positions.
- Light Rail positions are arrival-inferred; public data does not expose GPS or instantaneous speed.
- Track road/junction names are shown only where the available source exposes an unambiguous direction/platform/route relationship. The application does not invent an Up/Down road identifier.


## v9.2 fast ETA / resilience fix

ETA startup was rebuilt in v9.2. Heavy-rail station endpoints are fetched concurrently, with two high-yield anchors per line fetched first. A usable partial ETA solution is published as soon as enough fast bootstrap anchors cover several lines; the rest of the bootstrap and full station sweep continue in the background. On normal refreshes the previous complete solution stays visible until the next complete sweep finishes, avoiding ETA/WTT flicker.

The WTT matcher now uses a station/timing-point index instead of rescanning every trip for every arrival/candidate delay. Station responses are cached independently for up to 120 seconds, so one slow/failing endpoint does not invalidate the whole network. Per-request timeouts are 2.5 seconds, transient failures retain the last good snapshot, and browser freshness is based on the server sample timestamp rather than the time the browser happened to poll it.

The same concurrency/cache hardening is applied to Light Rail. EAL telemetry is now background-polled as well, so `/api/eal` never waits on the upstream TMS request.

For diagnostics open `http://localhost:8080/api/health`; it reports ETA phase, completed/fresh/cached station counts, request failures, elapsed cycle time and source timestamps. WTT remains the final fallback.

## High-resolution GeoTD map

The main map now uses an adaptive multi-resolution render of the supplied original `GeoTD.pdf` vector artwork. It starts at 6000 px wide, drops to 3200 px only when zoomed out, and automatically loads the canonical `assets/geotd-map.png` at 12000 x 10910 above 2.15x map zoom. This avoids decoding the 12K image unnecessarily on initial load while keeping labels and track geometry sharp at close zoom. The original vector `assets/GeoTD.pdf` is also included and can be opened from the **Vector PDF** control above the map.

The Light Rail crop is regenerated from the same 12K source at 3163 x 4314 rather than the earlier 843 x 1150 crop. All train/station coordinates remain in the same normalized GeoTD coordinate frame; this change affects display resolution only, not calibration.
