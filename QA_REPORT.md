# QA Report — HK Train Operations Display v9.3

Date: 12 September 2026

## Static / syntax checks

- `node --check app.js`: PASS
- `node --check light_rail.js`: PASS
- `python3 -m py_compile serve_live.py`: PASS
- core HTML/CSS/data assets present: PASS
- packaged EAL credential scan: PASS — the supplied upstream credential is not embedded in the project

## ETA startup / matcher performance

A synthetic MTR API harness was used so the live pipeline could be timed deterministically without depending on external network conditions.

- 55 heavy-rail station endpoints exercised
- artificial per-endpoint latency: 80 ms
- concurrent heavy-rail workers: 18
- cold-start fast ETA published after 8 of the high-yield bootstrap anchors had returned (~0.84 s in the synthetic harness)
- full bootstrap (18 anchors) published at ~1.05 s
- cold-start full 55-station sweep completed in approximately 1.5 s in the synthetic harness
- subsequent warm refresh completed in approximately 0.5 s
- normal refreshes retained the previous complete ETA solution while the next sweep ran, preventing bootstrap/full-sweep flicker

The WTT matcher was also benchmarked with 136 synthetic observations carrying a known +120 s delay:

- line-offset estimation: ~45 ms
- trip matching: ~58 ms
- total matching stage: ~103 ms
- recovered delay: +120 s on all representative lines

The matcher now uses a profile/line/station timing-point index rather than rescanning every trip/timing point for each arrival and each candidate delay.

## Failure / cache regression test

A complete successful heavy-rail refresh was followed by a synthetic all-endpoint failure.

- previous ETA snapshot remained available: PASS
- response marked `stale`: PASS
- original `fetched_at` timestamp was preserved: PASS
- all 55 station caches remained usable inside the 120-second cache window: PASS
- browser freshness clock therefore continues to age naturally instead of being reset on every stale poll: PASS

## Live-source responsiveness

The HTTP server starts independently of upstream feed completion. `/api/rail-live` and `/api/health` return immediately while the ETA worker is still in `bootstrap`, so the browser never blocks on the network sweep.

`/api/health` reports:

- current ETA phase
- completed / total requests
- fresh / cached stations
- request failures
- cycle elapsed time
- source timestamps
- representative upstream errors

Static HTML/JS/CSS responses are served with `Cache-Control: no-store` so replacing one build with another at the same localhost URL does not leave an old frontend cached.

## EAL / Light Rail hardening

- EAL upstream polling moved to a background worker; `/api/eal` no longer waits for RocTec on each browser request
- Light Rail station polling is concurrent
- Light Rail retains recent cached arrivals across transient failures
- stale Light Rail/EAL samples preserve their original server timestamp so they age out correctly

## Timetable / service-day regression checks

- WTT schedules and GeoTD track-following data are unchanged from v9.1
- ETA matcher service-day rollover now matches the browser/WTT rule: before 04:00 HKT it uses the previous railway service day
- WTT remains the final fallback whenever no sufficiently fresh live/ETA source is available

## Known limitations

- Non-EAL heavy-rail train position and speed are ETA-corrected WTT estimates, not GPS/ATS telemetry.
- Public Light Rail data provides arrivals but not vehicle GPS or instantaneous speed.
- The public MTR API may still be slow, blocked or rate-limited on a particular network. v9.2 bounds that failure with short per-request timeouts and exposes the exact failing endpoints in `/api/health` instead of remaining indefinitely on “warming up”.

## GeoTD high-resolution map QA

- Original source retained: `assets/GeoTD.pdf` (Illustrator vector PDF).
- Main raster levels: 3200 x 2910, 6000 x 5455, and canonical `geotd-map.png` at 12000 x 10910.
- Adaptive selector: 3.2K below 0.9x zoom, 6K from 0.9x to <2.15x, 12K at >=2.15x.
- Train/station coordinates were not recalculated; every raster uses the same full-page GeoTD bounds, preserving the existing normalized coordinate frame.
- Light Rail map rebuilt from the 12K render: 3163 x 4314.
- Original vector PDF is exposed as a read-only map source link in the UI.

- Mean absolute RGB difference after downsampling the 12K render back to the legacy 3200 x 2910 raster: about 1 channel value, consistent with antialiasing only and confirming the same page bounds/content.
