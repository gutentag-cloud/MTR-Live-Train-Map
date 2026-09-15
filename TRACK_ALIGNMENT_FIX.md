# v12.2 track-alignment correction

This build replaces the earlier real-map approximation with a direct GeoTD-vector georeference.

## Real map

- Source geometry is the actual coloured vector railway artwork in `assets/GeoTD.pdf`.
- The build extracts the 5-unit line-colour strokes from the supplied vector PDF rather than drawing station-to-station chords.
- The extracted set contains 1,284 separate heavy-rail track paths and 13,689 sampled vector points across TWL, ISL, KTL, TKL, TML, EAL, SIL, DRL, AEL and TCL.
- Parallel running roads, junction curves, crossovers and coloured siding/depot geometry present in the GeoTD source are preserved where they are connected to the operating corridor.
- Decorative/legend strokes are rejected by proximity to the already-validated GeoTD operating track skeleton.
- GeoTD coordinates are mapped to WGS84 using the 98 heavy-rail station anchors. A global affine geographic transform preserves the source geography and a local inverse-distance residual correction makes each supplied station control point exact.
- The live/simulated train position is transformed from its **current GeoTD x/y coordinate** through the same georeference. It no longer follows a separately drawn real-map line. Therefore the train and the detailed track layer share one geometry source.

## Schematic modes

- Vector schematic: rebuilt as a clean line/station SVG. Train vehicles are represented as small coloured dots only. The route lines and dots consume the same 1000 x 586 coordinate table.
- Official MTR map: train vehicles are also dots. The official map image is proxied through the local server, sampled into route-colour masks, and each dot is snapped to the nearest pixel belonging to its line. This prevents the old floating/misaligned train images.

## Station ETA

Station hotspots remain clickable in GeoTD, real-map, clean schematic and official-map modes. The popup keeps the official MTR timestamp including seconds and updates the countdown every second.

## Light Rail

- The existing GeoTD Light Rail operational map remains available.
- A second **Official route map** view lazily loads MTR's official Light Rail route-map PDF.
- Light Rail train markers are now ETA-only. A working is drawn only when a fresh official Light Rail ETA observation can be matched to it. If no current ETA is available, the train is removed instead of being shown as a WTT fallback vehicle.
- Light Rail position remains arrival-inferred because the public feed does not expose GPS.
