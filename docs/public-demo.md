# Public Web Demo

URL: [Epidemic Analytics](https://epidemic-khanh-demo.vercel.app).

Vercel project `epidemic-khanh-demo`, owner scope `khanhgiauten`, Git root directory `web-map`, Node.js `24.x`.

## Data Boundary

`scripts/export_web_demo.py` invokes the original FastAPI analysis helpers to export aggregate overview, network summary, cluster excerpt, and illustrative GeoJSON. Individual contact rows, raw demographics, node IDs, warehouse files, environment values, and the local pipeline are not uploaded. Public clusters are limited to 50 groups with at least 20 records. Geometry is generated for demonstration, not real outbreak locations or administrative boundaries.

The same-origin Next.js API serves these snapshots. `/api/predict` implements the original deterministic weighted scoring formula with finite-number validation, bounds, size checks, and explicit limitations. It does not run the trained Random Forest and is not medical advice. `NEXT_PUBLIC_API_BASE_URL` remains available when running against the full local FastAPI service.

Regenerate using a Python environment with FastAPI/Pydantic installed:

```powershell
python scripts/export_web_demo.py
cd web-map
npm ci
npm test
npm run build
```

Commit the regenerated `web-map/data/public-demo.json`. Pushes build the `web-map` directory, not the data pipeline. `.next` and `.vercel` are ignored; previously tracked build files were removed from the index without deleting local files.

## Verification

- Next.js patched to 15.5.26; build and TypeScript pass.
- Scoring tests cover zero/max/representative values, missing/extra keys, strings, NaN, negative and out-of-range values.
- Public overview/cluster/network/map endpoints return 200 without authentication; the representative POST returns 0.494.
- Runtime dependency audit reports zero vulnerabilities. The development lint dependency tree has outstanding advisories; no forced major downgrade was performed.
- Browser acceptance results are recorded in the portfolio launch report.
