# v11 feature implementation notes

## Map layers

- `v11.js` owns map-mode switching and geographic/schematic overlays.
- `v11.css` owns the geographic UI, station quick board, radar controls, fleet gallery and sprite styling.
- `assets/mtr-vector-schematic.svg` is generated from the exact v10 GeoTD route geometry, so train overlays use the same normalized x/y coordinates.
- `v11_backend.py` supplies public geodata/radar metadata and image proxying.

## Radar

`/api/weather/radar` parses HKO KML GroundOverlay / NetworkLink structures and returns recent frame URLs plus geographic bounds. `/api/weather/radar-image` only proxies HTTPS hosts under `hko.gov.hk` or `weather.gov.hk`.

## Geographic rail map

`/api/geo/stations` combines a public ArcGIS station layer with local fallback anchors. Missing stations are interpolated client-side in GeoTD coordinate space. `/api/geo/railways` requests OpenStreetMap railway ways from Overpass and caches them for one hour.

The coloured line connectors represent MTR service topology between station coordinates. The thin neutral OSM railway layer represents physical public-map rail geometry.

## Train sprites

`train_models.js` maps each line to an SVG in `assets/train-models/`. They are deliberately labelled representative because the available data does not reliably identify stock type per individual train.

## ETA precision

The quick geographic station popup uses `/api/station-board` directly and refreshes about every 8 seconds. Countdown rendering updates every second. The main Board tab continues to combine direct ETA and historical/WTT predictions.
