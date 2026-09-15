# v13.2 features

## GeoTD station ETA interaction

- Every heavy-rail station in the GeoTD coordinate catalogue has a larger, invisible click target.
- Pointer-down is intercepted on station targets so map panning no longer steals the station click.
- Clicking a GeoTD station immediately opens the selected station in the full **Board** sidebar.
- The Board continues to merge direct MTR station ETA rows with ETA-corrected timetable/WTT fallback.
- A compact station ETA popup remains on the map for the next direct MTR ETA rows and updates every eight seconds.
- The selected GeoTD station receives a visible focus ring, removed when the quick board is closed.
- All displayed ETA clock times remain Hong Kong time/service-day seconds.

This preserves independent train clicking and does not modify the geographic train/track renderer introduced in v13.1.
