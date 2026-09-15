# v12 public/external sources

- **MTR official Next Train API** — live station ETA source used by `serve_live.py`.
- **MTR official system map** — `https://www.mtr.com.hk/en/customer/services/system_map.html`; v12 displays MTR's public `system_map.png` directly from the MTR host in Official mode rather than redistributing the image in this ZIP.
- **Hong Kong Observatory radar** — HKO public georeferenced 256 km radar KML/image family, proxied only from HKO/weather.gov.hk hosts after the user enables the radar layer.
- **OpenStreetMap** — base-map tiles in Real map mode. v12 does not draw the v11 Overpass all-railway layer by default; the colored overlay is the supplied GeoTD geometry transformed to map coordinates.

The supplied GeoTD, WTTs and local generated train-model SVGs remain the primary project assets.

## Geographic railway geometry (v13)

The Direct map loads public MTR route waypoint GeoJSON through the local backend proxy. The primary runtime source is the HK Bus route-waypoints dataset (`hkbus/route-waypoints`), using one line-code GeoJSON file per MTR line. These coordinates are used only for geographic rendering/interpolation; GeoTD remains the operational/schematic source. If route geometry is unavailable, v13 falls back to station-to-station geographic chords rather than warping GeoTD onto the street map.

Project: https://github.com/hkbus/route-waypoints


## v13.3 Light Rail official schematic

- MTR Light Rail system-map image: `https://www.mtr.com.hk/en/customer/jp/images/lr/lr_system_map.png`
- Used only as a background/raster-snap reference in the dedicated Light Rail official-map tab. Moving dots are model estimates from the public ETA/WTT fusion and are not supplied by MTR as train coordinates.
