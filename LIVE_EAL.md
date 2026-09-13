# Live East Rail Line integration

This build can use the same live train-status feed observed in the supplied `eal-tms.rocteccloud.com.har` capture.

## What the HAR confirms

The EAL TMS web app polls a JSON endpoint approximately every 2 seconds. The captured responses contain 32 train-set records and expose, per train, fields including:

- train set ID (`T1`, `T2`, ...)
- TD/train descriptor (for example `JM0415`)
- destination
- current station and next station
- current speed in km/h
- distance to previous SSP and distance to next SSP in metres
- forward/reverse state
- powering/braking state
- ATO state
- zero-velocity / vehicle-in-station state
- fault and alarm information
- upstream display timestamp

The browser capture includes an API credential. **It is deliberately not embedded in this project.** `serve_live.py` reads the HAR locally at startup and keeps that credential in server memory only.

## Run it

Put the extracted website folder next to your HAR file, then from inside the website folder run:

```bash
python3 serve_live.py
```

The server automatically looks for `eal-tms.rocteccloud.com.har` in the website folder and its parent folder. Or supply the path explicitly:

```bash
python3 serve_live.py --har "/path/to/eal-tms.rocteccloud.com.har"
```

Open `http://localhost:8080` (the script normally opens it automatically).

## How live positioning works

When the display is at **Now**, playing at **1×**, and the live feed is connected:

1. scheduled EAL markers are suppressed;
2. each live train's `current_station` and `next_station` select the correct GeoTD EAL path;
3. position fraction is computed from the TMS distances as:

   `distance_to_previous_SSP / (distance_to_previous_SSP + distance_to_next_SSP)`

4. the marker is placed at that fraction along the extracted GeoTD track polyline;
5. the TMS-reported current speed is displayed directly rather than the timetable speed model.

The HAR shows those two distance fields behaving continuously across station-to-station runs: one rises while the other falls, with the total staying essentially constant for a given run, then resetting when the station pair advances.

Two TMS location aliases are normalized for the geographic map:

- `NHUH` → `HUH` (Hung Hom)
- `ADM_S` → `ADM` (Admiralty)

When you scrub the timeline away from Now, pause/accelerate simulation, lose the upstream feed, or open the site as a plain `file://` page, EAL falls back to the timetable/kinematic model.

## Security / CORS

Do not put the upstream credential in `app.js`. The local Python proxy solves both problems:

- it keeps the credential out of browser-visible source;
- the browser requests only same-origin `/api/eal`, avoiding upstream CORS/auth coupling.

The normalized `/api/eal` response contains only operational fields needed by the display.
