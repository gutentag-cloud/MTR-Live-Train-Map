# October 4 verification

- 35 Python tests pass with ResourceWarning treated as an error. New checks ensure historical tests cannot train on future dates, current-day labels are excluded, and within-one-second metrics reflect actual error.
- Second-display tests pass for official/model times, countdown transitions 60→59→0 seconds, midnight wraparound and invalid numbers. Due stays unconfirmed; an elapsed ETA does not prove departure.
- Existing geometry, journey planning, request race, live-position/freshness, and shared-request cancellation suites pass. JavaScript syntax checks pass for the updated station sheet and data dialog.
- Six dates / 123,033 labels / 7,263 arrival groups are available. Latest test has only 45 arrival groups and is not sufficient for live model activation.
- Four historical test dates use only preceding training/validation dates. Combined observation-weighted MAE 8.10 s; latest test MAE 15.55 s. No one-second accuracy established.
- Fast Exit combinations tested/imported: none. No accessible official bulk car/door dataset or app-control interface found. The feature remains unavailable without a verified mapping.
- No new physical-phone/browser verification was available through this session's tools. Existing October 2 responsive checks remain historical evidence only.
- Publication includes source and aggregate reports; runtime databases, CSV labels and models containing local run IDs remain local.

- Live station countdown uses wall time and is verified to keep ticking when the simulation is paused; accelerated simulation does not redraw it more than once per real second.
