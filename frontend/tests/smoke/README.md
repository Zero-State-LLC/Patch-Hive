# Live smoke

Read-only checks against a deployed PatchHive. Run them after every `wrangler deploy`. There is no dev server, no sign-in and no write.

```bash
cd frontend
npm run test:smoke                                          # staging (default)
SMOKE_BASE_URL=https://patch-hive.com npm run test:smoke    # production
```

Or dispatch the **Live smoke** workflow (`.github/workflows/smoke.yml`) and choose `staging` or `production`.

What it checks:

- **API health:** `/health/ready` on the matching API is `healthy`, with `database: ok`, and reports the version in `frontend/package.json`. A deploy built from a different commit fails here.
- **Security headers:** CSP, HSTS, `nosniff` and a referrer policy. Staging is `noindex` and production is not.
- **Routing:** deep links return the app with 200, and unknown paths return it with 404.
- **Pages:** Home, Modules, Products, Cases, sign-in, the privacy notice and not-found render live data, with no alert, no lingering skeleton, and no console or CSP error.

For any other host, set `SMOKE_API_URL`.
