# Live accuracy model — v7

The display uses three distinct data-confidence tiers.

## 1. EAL telemetry — highest confidence

When the RocTec EAL TMS feed is available, East Rail train position and speed come from the live TMS data captured/discovered via the supplied HAR. Distance-to-previous/next SSP is projected along the extracted GeoTD EAL track polyline. The upstream API credential remains in the local Python process only.

## 2. Heavy rail ETA fusion — official live correction

AEL, TCL, TML, TKL, SIL, TWL, ISL, KTL and DRL use MTR's official Next Train API as a live correction layer. The API is documented as updating every 10 seconds and returns up to the next four trains for a station/direction.

`serve_live.py` polls strategic timing-point stations on each line and fuses those observations with the supplied working timetable:

1. Estimate a line-level delay by cross-correlating many ETA observations against scheduled arrivals over a -10 to +15 minute window.
2. Greedily match individual ETA observations to WTT trips using station, destination, order and timing.
3. Accept a trip-specific correction only if it agrees with the line-level solution; otherwise use the safer line-level correction.
4. Shift the WTT time axis by that live correction and keep the existing GeoTD track-following + acceleration/deceleration model.

This is **not vehicle telemetry**. Position between stations remains inferred from timetable geometry, but the trajectory phase is continuously corrected by official live ETAs.

## 3. Light Rail arrival-inferred map

`light_rail.html` uses MTR's official Light Rail Next Train API. The public feed supplies platform, route, destination, train length and time-to-arrival but does not expose public GPS coordinates or a stable vehicle identifier.

The page therefore:

1. polls a distributed set of Light Rail stops;
2. matches live arrivals to the supplied Light Rail WTT timing points;
3. estimates a delay for matched WTT workings;
4. positions those matched workings on the cropped GeoTD Light Rail track map.

Markers are explicitly labelled **arrival-inferred**, and displayed speed is modeled rather than telemetry-derived.

## Fallback

If a live feed is unavailable, unmatched trains remain on the original timetable simulation. Scrubbing away from Now or using accelerated simulation also disables live correction because a real-time feed cannot represent a historical/future simulated clock.


## v8 WTT fallback hardening
When a live source is unavailable, stale, malformed, or cannot be matched, the display keeps the affected train/line visible using the supplied working timetable and GeoTD track-following trajectory. Stale EAL cached telemetry is no longer used as a live position; Light Rail now renders active WTT trips even with zero live-arrival data.

## v9.2 inspector / operations derivations

The richer fields in v9.2 are derived conservatively:

- journey distance is the sum of the GeoTD-derived polylines between WTT timing points;
- next-stop predictions add the accepted ETA correction to future WTT timing points;
- train-ahead/behind spacing uses comparable trips sharing a common terminal and compares remaining route distance and terminal passage time;
- service-gap/bunching alerts use projected common-terminal headways and only run when live ETA corrections (or their replay snapshots) are active;
- short-working/turnback is inferred when the WTT destination is not a normal endpoint in the extracted line paths;
- non-EAL speed remains kinematic/model-derived; EAL TMS speed is telemetry;
- Up/Down running road is displayed only when a matched official ETA anchor supplies a direction. Exact physical parallel-road/crossover identity is not invented when the available data is ambiguous.


## v9.2 live-feed latency / cache behavior

Heavy-rail ETA requests are made concurrently. A cold start first requests two bootstrap anchors per line and publishes that partial solution before the full strategic-station sweep completes. During later refresh cycles the previous complete solution stays active until the new full sweep is ready. Each station has an independent 120-second cache and each upstream request has a 2.5-second timeout. This keeps one slow station from blocking or clearing the rest of the network.

The browser ages ETA using the server's actual `fetched_at` timestamp; repeatedly polling a stale cached response no longer resets the freshness clock.
