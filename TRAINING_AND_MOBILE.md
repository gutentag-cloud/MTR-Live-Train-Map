# Position, phone and training update

## Position estimates
East Rail validates every train's upstream timestamp and omits telemetry older than 20 seconds. Moving trains receive at most three seconds of speed-based latency compensation, bounded to the current segment. Stopped trains do not advance. This is still an estimate, not GPS or exact physical location. When no usable telemetry remains, timetable/ETA fallback applies and must not be read as a measured position.

Other lines now require a medium/high-confidence match to an individual timetable trip; a line-wide delay is no longer applied to unmatched trains. Large corrections take effect immediately rather than accumulating minutes of smoothing lag. Server ETA anchors expire after 30 seconds.

## Phone
Bottom navigation separates Map and Arrivals and opens Journey/Data dialogs. Controls use larger touch targets, native inputs avoid small-text zoom, and station details fit the viewport. The original 12,000 × 10,910 GeoTD remains the default; Automatic quality is available for constrained devices.

## Observation archive
Run `python3 serve_live.py --no-browser --port 8080` to collect observations while the server runs. `runtime/training.sqlite3` stores deduplicated, whitelisted East Rail telemetry and official ETA predictions separately. Credentials and raw request headers are excluded. This archive is separate from the rolling replay database and has no automatic pruning. Monitor disk use and back it up using SQLite's backup API.

Set `TRAINING_DB_PATH` to a path on a persistent volume for hosted deployments. The current free Render service cannot guarantee continuous collection or retention across sleep/redeploy. GitHub Pages cannot run this collector. No paid service or storage upgrade is configured by this change.

`GET /api/training/status` returns aggregate counts. Raw databases and training outputs are excluded from Git and blocked from static HTTP downloads.

## Training
Run `python3 tools/train_arrival_model.py` to backfill available local replay snapshots, produce `runtime/training/arrival_labels.csv`, and evaluate `runtime/training/arrival_model.json`. This cannot recover observations never recorded.

The initial September 27 retraining used 85,065 labeled observations across 5,900 arrival groups from September 21–23. Stopped telemetry sometimes retains the arriving station pair: the labeler uses SSP distances to identify the arrival station, normalizes station aliases, and breaks sequences on gaps, reversals and unobserved stops. These labels are still a telemetry proxy, not independently verified doors-open times.

Entire dates are separated: September 21 training, September 22 model selection/uncertainty estimation, September 23 final test. Arrival groups crossing midnight are purged. Cells need five independent arrival groups; repeated polling frames do not count as independent training support. The selected model uses directed station pair, progress decile and speed band. Missing cells fall back to the learned progress-only baseline, then distance/speed. All held-out rows, including fallbacks, contribute to the reported error.

On 45,652 final-test rows (3,330 arrival groups), mean absolute error is 7.61 seconds; the learned progress-only baseline is 8.80 seconds and distance/speed is 46.67 seconds. Giving each arrival group equal evaluation weight yields 6.52 seconds. The 90th-percentile row error is 15 seconds. Direct model support is 96.1%. A ±28-second error band estimated on validation data covers 97.5% of test rows; it is an empirical band, not a guaranteed confidence interval.

For MKK → HUH, HUH → EXC and EXC → ADM, held-out mean errors are 4.89, 4.92 and 6.47 seconds respectively. These are next-stop time errors, not full-journey ETA errors or physical-position errors. The experiment uses only three partial calendar dates and correlated samples; disruption/generalization performance remains unknown. The results are not directly comparable to the earlier 12.1-second result because the labels and split changed.

The learned model remains offline and is not loaded by the live app. At least five labeled dates, sufficient held-out journeys, support and uncertainty coverage are required even for a review recommendation. No gate automatically activates the model. Official ETA predictions are never treated as ground truth.

## October 1 evaluation update

Retraining includes the additional archived September 27 observations: 86,932 labeled rows and 5,993 arrival groups across four dates. Training is September 21–22; validation is September 23; the untouched final test is September 27 (1,867 rows / 93 arrival groups). The prior result above is historical and does not describe this newer test.

The selected progress-and-speed model has 27.46 seconds mean absolute error, versus 32.83 seconds for the learned progress-only baseline and 63.22 seconds for distance/speed. Its 90th-percentile error is 66.5 seconds and direct model support is 91.5%. The ±14-second validation-derived band covers only 59.5% of test rows. This is evidence of poor generalization; there are too few test arrival groups, insufficient dates, and inadequate uncertainty coverage for live use. No tuning was performed on this final test to conceal the regression.

For MKK → HUH specifically, mean error is 34.58 seconds with a 105-second 90th percentile (209 correlated rows). HUH → EXC has 5.39 seconds mean error (60 rows); EXC → ADM has 3.06 seconds (36 rows). These small samples must not be read as guaranteed journey accuracy. The model remains offline. The static report and Data dialog now show the October 1 evaluation.

## Prediction review fixes
- Periodic timetable patterns can fit several line delays equally well; such offsets now have low confidence.
- Individual trip corrections require an unambiguous candidate and corroboration at two different stations. A single anchor stays low confidence.
- Heavy-rail responses with stale, missing or future upstream timestamps are rejected, even if fetched just now.
- Board trip matching requires the exact terminal and rejects nearby ambiguous candidates.
- Live polling has request deadlines; invalid timestamps and non-finite/missing distances cannot become fresh measured positions.
- Historical delay trends older than 60 seconds no longer steer current forecasts.
- The Data dialog loads its historical report independently of collector availability and handles missing evaluation metrics.

## Exit F
The boarding guidance form defaults to Mong Kok East → Admiralty, Exit F. There is no verified platform/car/door mapping in this repository, so the app does not invent an optimal door. It links the official MTR Mobile Fast Exit instructions. An actual shortest-walk recommendation remains pending verified mapping for the arrival platform and exit.
