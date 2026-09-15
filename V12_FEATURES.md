# v12 feature implementation

## Startup path

`data.js` + 3.2K GeoTD + `app.js` start immediately. `v12_geo_data.js` is a small local geometry bundle. Leaflet and OSM are lazy/idle-loaded; HKO is user-triggered.

## Geographic track transform

For every non-Light-Rail pair in `TRAIN_DATA.trackRoutes`, v12 preserves the supplied GeoTD polyline shape and maps it between WGS84 endpoint anchors using a local tangent/perpendicular transform. A train uses its `pairFraction` against that transformed polyline, so it follows the same curved operational route in geographic mode.

## Schematic/official projection

A full line graph contains public stations including stations that are not WTT timing points. For a current WTT pair, v12 finds the line path between the two timing points and moves the train through intermediate schematic stations according to pair progress. The vector schematic is generated from exactly the same coordinate table used by its marker overlay.

The official map uses MTR's public `system_map.png` as a remote background. The train/station layer is calibrated to its 1000×586 presentation coordinates. This is a visual projection and does not claim exact MTR artwork control-point coordinates.

## Station ETA

Clicking any station hotspot calls `/api/station-board`. The backend accepts the full public line station catalogue, not only matcher timing points. Recent cache is returned immediately and refreshed asynchronously where possible. Exact MTR timestamps are shown to `HH:MM:SS`; countdown rendering ticks every second.


## v12.2 correction

See `TRACK_ALIGNMENT_FIX.md`. Real-map geometry is now direct GeoTD-vector geometry georeferenced to WGS84 rather than per-pair line approximations. Schematic/official train symbols are dots; official dots are route-colour-snapped. Light Rail includes an official route-map mode and hides trains without matched fresh ETA.
