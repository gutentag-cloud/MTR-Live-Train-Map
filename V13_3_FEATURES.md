# v13.3 features

## Official heavy-rail map rollback

The v13.1/v13.2 official-map renderer attempted to reconstruct a continuous route by repeatedly snapping a dense path to line-coloured pixels. On bundled/parallel sections this could migrate onto a neighbouring part of the official schematic and visibly misalign trains. v13.3 restores the v13 method: interpolate the train on the calibrated schematic route first, then perform one local same-line-colour pixel snap for the final train point. Light Rail remains excluded from this heavy-rail system-map overlay.

## Direct-map train discoverability

The physically scaled body remains the close-zoom representation. Below the physical-body threshold, a small clickable circle marker is placed at exactly the same route-centre position. This keeps trains discoverable at overview zoom without pretending that the marker is physically to scale.

## Second-level station-time estimation

MTR Next Train timestamps are retained as the live arrival/departure window, but their shared seconds field is no longer presented as one-second ground truth. Each live row is matched to a WTT timing event. The displayed second phase comes from the WTT timing point plus the current line-delay model where available, choosing the nearest phase inside the MTR live window. API responses expose both `raw_eta_sec` and `estimated_eta_sec`, along with the estimate method and confidence. The UI labels these times as estimates.

## Light Rail orientation

The Light Rail vehicle SVG is rotated by the local tangent of the exact GeoTD track polyline. The supplied LRV artwork has its cab at the left-hand end, so the intrinsic 180-degree phase is accounted for before applying the track tangent. Route labels remain upright.

## Light Rail official-map dots

The dedicated Light Rail official-map tab now loads MTR's current `lr_system_map.png` through the local proxy. A calibrated schematic warp gives each live ETA-matched train a seed point; the final marker is snapped to saturated route pixels sampled from the official map. These dots are clickable and are explicitly labelled ETA/WTT-inferred rather than GPS.
