# v13 upgrade notes

## Core corrections

### 1. Direct geographic railway map
The previous real-map mode warped GeoTD coordinates into latitude/longitude. That preserved GeoTD distortions and could leave visible gaps or displaced corridors. v13 no longer uses that warp for the geographic map. It loads public MTR route GeoJSON through the local server, builds a graph from the real geographic polyline, snaps each station pair to that graph, and interpolates the train directly along the geographic route. GeoTD remains a separate operational diagram.

If public route geometry is temporarily unavailable, v13 falls back to dashed station-to-station geographic chords rather than presenting warped GeoTD as if it were true geography.

### 2. ETA anti-jump fusion
The previous renderer immediately substituted every new ETA delay correction into `modelSec = wallSec - delay`, so a refresh that changed delay by tens of seconds could visibly teleport a train. v13 keeps the raw correction but applies a slew-limited exponential transition (18 s time constant, capped correction velocity) to the map clock. The raw-vs-displayed difference is exposed in Operations as “ETA jumps absorbed”.

Direct EAL TMS telemetry remains unsmoothed and higher-priority.

### 3. Special-working diagnostics
The weekend EAL6240P parsed timetable includes Admiralty→Lok Ma Chau workings after the normal Lok Ma Chau Spur Line control-point closing time. v13 marks active examples as `post-control-point-hours working · verify operating purpose` rather than assuming ordinary passenger status. This is deliberately a diagnostic classification: the attached timetable does not currently include a decoded trip-prefix legend proving whether JH/JM/JA/JL/TT denotes passenger, empty-stock, depot, or another operating class.

## New/expanded functions

- Direct geographic map with route-following train interpolation.
- GeoTD kept as an operational track diagram instead of being georeferenced by distortion.
- ETA discontinuity absorption with raw-correction observability.
- Operations counters for absorbed ETA jumps and special EAL workings.
- Existing second-by-second station boards, timetable simulation, headways, speed model, fixed speed restrictions, EAL TMS telemetry, history replay, HKO radar, official MTR map overlay, fleet models and Light Rail companion are retained.
- Geographic route data is cached server-side for one day to reduce network requests.

## Data source note
Direct geographic route geometry is requested at runtime from HK Bus WayPoints Crawling / its mirror, which republishes MTR route GeoJSON. Station anchors and the operational GeoTD remain separate sources.
