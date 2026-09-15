> **v13.3 note:** the old direct timestamp below is no longer treated as independently second-accurate. v13.3 keeps the MTR ETA as the live time window and estimates the displayed second phase from the matched WTT timing point plus the live line-delay model. See `V13_3_FEATURES.md`.

# v10 delay prediction and second-accurate station board

## Historical delay predictor

The predictor uses the rolling sanitized history database written by `serve_live.py` (`runtime/history.sqlite3`). It never stores or uses the upstream EAL API credential.

For each train, v10 first tries to use that trip's recent matched ETA corrections. If there are not enough reliable trip samples, it falls back to the line-level delay history. Recent samples receive exponentially greater weight than older samples. A weighted linear trend is estimated in seconds of delay per minute, capped to avoid runaway extrapolation. Future trend influence is also damped with forecast horizon so a short disruption does not create an unrealistic long-range prediction.

Predictions are anchored to the newest usable live correction when one exists. Otherwise, they use the recent historical delay level. The UI shows sample count, trend, confidence and RMSE. Low-data cases fall back to current ETA or WTT rather than fabricating a prediction.

The train inspector shows delay forecasts for now, +5, +10 and +20 minutes. Predicted next-stop times and terminal ETA use the same forecast model.

## Station board

The Board tab is deliberately separate from the network-wide ETA fusion worker. When a station is selected, the local server queries the official MTR Next Train API for that station directly. This makes the first board result independent of the slower all-network ETA sweep.

Rows use this priority:

1. `LIVE ETA` — the official MTR station timestamp is used directly, including seconds.
2. `HISTORY PRED` — WTT time plus the historical delay forecast when no direct arrival row is available.
3. `ETA-CORRECTED` — current matched ETA correction without enough history for a trend forecast.
4. `WTT` — pure working-timetable fallback.

The board refreshes direct station data about every 8 seconds and displays a countdown updated once per second. A timestamp such as `23:18:42` therefore has second-level precision, but this should not be confused with guaranteed second-level physical arrival accuracy: MTR controls the upstream prediction quality and refresh cadence.

The station board uses a short server cache to avoid over-polling the public API. Direct station responses older than 30 seconds are not presented as live; the board reverts to prediction/WTT until fresh data returns.

## Service-day handling

The same 04:00 railway service-day rollover as the WTT model is used. The direct station API path also normalizes post-midnight times into the 24:00–28:00 service-day range.
