# Preview-only build

v12.2 track-corrected preview is intentionally isolated from the production Git repository.

```bash
unzip MTR_Live_Train_Display_v12_2_TRACK_CORRECTED_PREVIEW.zip
cd MTR_Live_Train_Display_v12_2_TRACK_CORRECTED_PREVIEW
python3 serve_live.py
```

It deliberately omits `.git`, `.nojekyll`, `render.yaml`, `config.js`, HAR captures, API credentials and persistent runtime history databases. Do not unzip it over the production working tree.
