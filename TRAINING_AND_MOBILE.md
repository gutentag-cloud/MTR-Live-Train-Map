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

The initial public `training_report.json` describes 42,087 labeled observations and 2,832 arrival groups across two calendar dates. Chronological 80/20 evaluation keeps each complete arrival group in one partition. On 7,682 supported held-out rows, mean absolute error was 12.1 seconds versus 46.5 seconds for distance/speed. Unsupported station/progress buckets are excluded from that metric. Labels are the first stopped telemetry sample with gaps up to 30 seconds, not independently measured doors-open times. Adjacent observations are correlated; these figures are an experiment, not guaranteed passenger accuracy.

The learned baseline is a median by directed station pair and progress decile. It is not deployed. More dates, disruption coverage and independent measurements are needed. The eligibility flag is only a preliminary review gate; it never automatically activates a model. Official ETA predictions are never treated as ground truth.

## Exit F
The boarding guidance form defaults to Mong Kok East → Admiralty, Exit F. There is no verified platform/car/door mapping in this repository, so the app does not invent an optimal door. It links the official MTR Mobile Fast Exit instructions. An actual shortest-walk recommendation remains pending verified mapping for the arrival platform and exit.
