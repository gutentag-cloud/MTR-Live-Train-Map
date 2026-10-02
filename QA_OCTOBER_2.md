# October 2 verification

- Python: 30 tests pass with ResourceWarning treated as an error. Covers station transition continuity, missing/invalid speed, countdown resets, archive whitelist, explicit countdown retention, prediction matching, freshness, and training evaluation.
- JavaScript regression suites pass: 360 geometry samples, arrival presentation, journey planning, station request race handling, live-position bounds, and shared API requests with independent caller cancellation.
- Syntax checks pass for app.js, v12.js, passenger_tools.js and config.js.
- Browser: tested 320×740 and 390×844 layouts without horizontal document overflow. Station quick view loads Mong Kok East arrivals without switching away from the map. Explicit full-board button selects Arrivals and closes the sheet. Options exposes map controls and Exit & door. Empty personal-note validation works. Prediction Data displays reports independently of collector status. Desktop viewport restores correctly with Options hidden.
- Browser error log was empty at capture. Local phone screenshot is tmp/mobile-after.png; screenshots and raw datasets are excluded from publication.
- Pointer-based pinch zoom is implemented, but physical phone multi-touch and mobile browser memory limits are not validated.
- Station duration baseline: 11,201 historical intervals across four dates. September 27 held-out travel MAE 36.92 s / p90 81 s (73 intervals); dwell MAE 29.67 s / p90 110 s (75 intervals). Both remain offline. No one-second accuracy established.
- Explicit countdown archive: 23,764 rows, 158 observed 1→0 transitions, median observed span 57.02 s. First observation may be inside the countdown phase. Disappearing sequence rows do not count as measured departures. No verified train identity join between ETA countdowns and telemetry departures.
- Best-door research: official Admiralty layout and MTR Fast Exit instructions checked. Public layout does not label car/door numbers. MKK→ADM Exit F has no verified recommendation available in this release.
- Full 12K GeoTD remains selectable/default. It can use substantial phone memory. API cold starts and upstream refresh delays remain; continuous archive retention requires persistent storage and an always-on collector.
