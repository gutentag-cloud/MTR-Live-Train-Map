# v13.1 — track-locked geographic rendering

## Changes requested after v13

### 1. Official map: heavy rail only
The live overlay and clickable station hotspots on the official MTR system-map view now exclude Light Rail (`LRL`). The underlying MTR raster is kept unedited so it remains an authentic official source image.

The official overlay also no longer snaps every moving train independently to the nearest same-colour pixel. v13.1 samples a continuous same-line path between the relevant station anchors, snaps that path to the official raster, and then interpolates the train along the resulting path. This reduces branch/parallel-line snapping errors and marker jitter.

### 2. Geographic trains are physically track-locked
The old 48 × 24 pixel train SVG marker is removed from the real map. A train is now rendered as a short geographic polyline sliced directly from the exact route polyline used for its location. This means its visible centreline cannot be offset from the application's track geometry.

Each train remains clickable. A transparent hit-polyline is wider than the visible train, but it does not alter the visible footprint.

### 3. Real physical train length
Published MTR train lengths are used on the geographic map:

- KTL / TWL / ISL / TKL: 182 m
- TCL / AEL: 184 m
- EAL: 219 m
- TML: 195 m
- SIL: 70 m
- DRL: 91 m

A representative ~3.0–3.1 m heavy-rail width envelope is converted to pixels from latitude and zoom. The outer rendered footprint is therefore map-scale rather than icon-scale. Trains are deliberately hidden below zoom 15, when a physically correct width would be sub-pixel or visually misleading.

### 4. Hong Kong time
All user-facing TMS update timestamps are formatted as `HKT` (`Asia/Hong_Kong`, UTC+8). Timetable/service-day selection and the main clock already used Hong Kong time and remain unchanged. Machine timestamps can remain ISO/UTC internally for age calculations; they are converted before display.

Light Rail's displayed upstream update time is also converted to HKT.

### 5. Tung Chung East current infrastructure
MTR announced that Hong Kong-bound Tung Chung Line trains would begin using the first diverted track section at Tung Chung East from 13 September 2026. v13.1 therefore:

- loads current heavy-rail physical topology from OpenStreetMap/Overpass as a fine geographic underlay;
- attempts to derive the current TUC → SUN corridor from that physical topology for Hong Kong-bound TCL train placement;
- retains the independent MTR-route geometry / baked WGS84 route as deterministic fallback;
- marks Tung Chung East as an under-construction reference, not as an open passenger/ETA station.

This avoids inventing survey coordinates for the new diversion while still allowing the app to follow current mapped track geometry when available.

## Accuracy hierarchy on Real Map
1. Current physical heavy-rail topology (OSM/Overpass), used where a safe line-corridor path can be derived (notably TCE HK-bound).
2. Independent MTR geographic route geometry.
3. Baked WGS84 station-to-station route geometry bundled with the app.
4. Straight station chord only as last-resort failure fallback.

GeoTD-to-map warping is not used by the Real Map renderer.
