# Intent

## Problem

Catalog batch 7 left 179 new-brand candidates with URL-inferred brands, 22 power/depth gaps, and no in-repo fetch path. The batch 7 scripts import an external scrape router that is not in this repository. Direct Firecrawl calls still live in `scripts/hermes_hp_enrich_firecrawl.py`. The `modules` table cannot store verification status, and no importer can populate an empty database from the seeds, overlays, and candidates.

## Proposed outcome

- An in-repo scraper that tries a polite, robots-aware, rate-limited, disk-cached free fetch, then context.dev, then Firecrawl when keys are present. Missing keys and a paid-fetch cap skip cleanly. Receipts store url, method, status, sha256, and timestamp. Page text stays out of git.
- Batch 8 verifies candidate brands and searches the 22 power/depth gaps. This run is free-only. Resolved rows keep a source URL. Unresolved rows stay unresolved.
- A non-destructive migration adds `modules.verification_status` and `modules.verification_source_url`.
- An importer defaults to dry-run, writes a receipt and idempotent upsert SQL, and can populate an empty local database from the phase 2 seed, phase 3 seed, cases seed, HP overlay v1, power/depth overlays v1–v5, and batch 7 candidates.
- A manual Actions workflow `db-load.yml` runs that importer against staging or prod. Dry-run is the default. Apply mode dumps the affected tables first. The database URL is never echoed. The load runs only from Actions.
- Tests cover the router with mock HTTP and the importer against a throwaway local Postgres.

Out of scope: admitting rows to staging or production, paid fetches in this environment, audio, and hardware control.

## Affected users / systems

Catalog dataset, `modules` schema, importer scripts, CI (backend pytest, version consistency, CodeQL).

## Constraints / non-goals

No invented hardware facts. No secrets in the tree or logs. No destructive SQL. No staging or production database access. Payments and product behavior stay untouched.

## Open questions

Operator runs the paid batch later on a machine that has `FIRECRAWL_API_KEY` and `CONTEXT_DEV_API_KEY`. This environment does not.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| PR #30 is on `main` as `fdfbe93` | `OBSERVED` | `git log origin/main` |
| 179 candidates, 39 brands, brand taken from the URL prefix | `OBSERVED` | `overlays/catalog-new-brand-candidates-v1.json` and batch 7 receipt |
| 22 power/depth targets remained unresolved after batch 7 | `OBSERVED` | `receipts/batch7.dry-run.json` |
| ModularGrid `robots.txt` allows `User-agent: *` on `/e/` module pages and disallows a listed set of paths | `OBSERVED` | fetched `https://modulargrid.net/robots.txt` |
| A module page exposes the manufacturer in `span.vendor-name` | `OBSERVED` | fetched `https://modulargrid.net/e/1010-music-bitbox-2-0` |
| context.dev scrape is `POST https://api.context.dev/v1/web/scrape`; search is `POST https://api.context.dev/v1/web/search` | `OBSERVED` | docs.context.dev |
| This VM has no paid scrape keys | `OBSERVED` | task statement; keys are read only from the environment at run time |
| Phase 2 seed counts are 703 brands, 376 catalog modules, 3 full-spec modules | `OBSERVED` | `seed-phase2-v1.json` |
| Free batch 8 fetched 179/179 candidate pages; 178 verified, 1 corrected (Analogue Solutions HH88), 0 flagged | `OBSERVED` | `hermes-research/batch8-brand-verification.json` |
| 3 of 21 remaining power/depth targets resolved from Perfect Circuit spec lines; 18 unresolved | `OBSERVED` | cached retailer pages and `batch8-power-depth.json` |
| Empty-database dry-run plans 703 manufacturers, 564 catalog rows, 3 full-spec modules, 179 candidates, 348 power-target modules, 50 cases, 0 conflicts | `OBSERVED` | throwaway local Postgres dry-run receipt |

## Author / date

- Author: catalog batch 8 agent
- Date: 2026-10-17
