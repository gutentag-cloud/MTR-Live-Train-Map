# v9.3 Operations / Train Inspector

## Per-train inspector

Every active heavy-rail WTT trip can expose:

- line, WTT trip/run number, direction (when a live ETA anchor supplies it), origin, destination, and inferred short-working/turnback flag;
- current timing-point segment, exact GeoTD track-following position, segment progress, distance from the previous timing point and distance to the next timing point;
- modeled instantaneous speed, acceleration/deceleration state, segment average speed, modeled peak speed, line ceiling and any mapped lower permanent restriction;
- journey distance travelled / remaining and timing-stop progress;
- next five timing stops with scheduled and live-corrected expected times;
- train-ahead / train-behind spacing in time and distance against a common terminal where comparable trips exist;
- modeled speed-vs-distance profile with a speed-limit overlay;
- 30-minute line-delay trend from the local history recorder;
- explicit data-source / confidence classification: TMS telemetry, official ETA-corrected, or WTT fallback.

For EAL TMS trains, the inspector additionally exposes actual TMS speed, power/brake state, active cab/direction, ATO indication, in-station / zero-velocity state, faults/alarms, SSP distances and update time. The app attempts an explicitly *inferred* match from the TMS train to an active EAL WTT trip so that telemetry can be shown alongside predicted next stops and WTT/ETA information. Telemetry and inferred timetable information remain visually separated.

## Network Operations tab

The Operations tab calculates, per line:

- active trains;
- source tier (TMS / ETA / WTT);
- current line-level ETA correction when available;
- recent delay trend;
- projected common-terminal service gaps and bunching;
- early-trip late-running alerts;
- worsening delay and recovery alerts.

Operational anomaly alerts are only produced while live ETA data (or recorded ETA replay data) is active. Pure WTT mode still provides scheduled headway information in each train inspector but does not pretend scheduled service patterns are live incidents.

## History / replay

`serve_live.py` stores sanitized rolling snapshots in `runtime/history.sqlite3` for 24 hours. It records:

- EAL normalized TMS snapshots (no API credential / HAR headers);
- official heavy-rail ETA/WTT-fusion snapshots;
- official Light Rail arrival snapshots.

The main page History selector can replay approximately 5, 15, 30 or 60 minutes ago. EAL uses the nearest captured TMS snapshot; other heavy-rail lines use the nearest captured ETA-correction snapshot. If no suitably close historical snapshot exists, the normal WTT fallback remains available.

The local history API is:

- `/api/history?minutes=60&kinds=eal,rail,lrt`
- `/api/history/status`

## Light Rail

The dedicated Light Rail page now adds journey progress, estimated distance travelled/remaining, next timing stops, headway/spacing against comparable trips, train length/platform when exposed by the official arrival feed, a modeled speed profile, and a delay trend collected while the page is open. Public Light Rail data does not expose vehicle GPS or instantaneous speed, so those fields remain clearly labeled as arrival-inferred / modeled.
