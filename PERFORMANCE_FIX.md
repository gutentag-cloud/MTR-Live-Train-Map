# v12 performance hotfix

This build keeps the v12 feature set and changes the rendering/runtime architecture. The map artwork itself was not the primary bottleneck.

## Root causes fixed

- The old animation loop called the full `render()` every 250 ms.
- Every full render scanned every trip in the selected profile (~6.5k–7.7k trips) and rebuilt the train list, operations cards/table, inspector, status pills and board even when those panels were hidden.
- ETA lookup re-tested live-mode/time alignment for every candidate trip.
- Hong Kong time formatting recreated an `Intl.DateTimeFormat` repeatedly in hot paths.
- The v12 geographic/schematic projection recalculated route geometry and polyline segment lengths on every train update.
- The station quick board rebuilt its whole DOM on every 250 ms state event even though its visible countdown only changes once per second.
- Full 120-minute history was downloaded and parsed immediately at startup and then again every 15 seconds even when replay/operations/history were not in use.
- GeoTD marker CSS used an 0.8 s transition while positions were updated every 0.25 s, making markers continuously chase old positions.

## New runtime policy

- Train position/state loop: 250 ms.
- Sidebar/list/inspector/status: at most 1 Hz unless the user explicitly changes something.
- Operations calculations: at most once every 5 s and only while Operations is visible.
- Board countdown: 1 Hz; direct ETA fetch stays on its existing station polling cadence.
- History: loaded on demand for Operations, Replay, or a selected train; no large startup history request.
- Active-trip calculation: 5-minute service-time buckets with delay margin instead of scanning every timetable trip.
- Geographic and official/schematic route geometry: cached by line + station pair.
- Polyline lengths: cached per route.

## Measured structural reduction

For the weekday profile, the previous active-state pass considered 7,661 trips each frame. The new index has a median candidate set of 438 trips, p95 662, max 678: about 17.5x fewer trip candidates in the median bucket before line/live filtering.

This does not claim a browser FPS benchmark because the build environment cannot run the user's exact browser/GPU workload. It does eliminate the main deterministic sources of main-thread churn found in the code.
