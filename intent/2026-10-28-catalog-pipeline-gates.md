# Intent

## Problem

The 2026-10-27 gap analysis found that the catalog pipeline (spec 003) fell short of its own requirements:

- **Downloads unchecked (FR-011):** the direct transport read any response body in full, of any type and any size, and threw away the headers.
- **Apply not bound to a review (FR-020):** apply needed no reviewed dry run. Whatever the overlays and the database produced at apply time was written, even if it differed from what the operator approved.
- **Receipts unidentified (FR-030):** receipts had no run id, no timestamps and no hash of the plan or its inputs.
- **Conflicts undercounted (FR-016):** only the first 50 conflicts were kept, with no total.

## Proposed outcome

- **Downloads:** direct fetches accept only pages, XML/sitemaps, JSON, text and gzip, at most 10 MiB, and keep response headers. Refusals are coded.
- **Apply gate:** a dry run reports `plan_hash`. The Actions apply must be given that hash, and writes nothing if the plan has changed since.
- **Receipts:** every receipt carries `run_id`, `started_at`, `finished_at`, `plan_hash`, `inputs_hash` and `conflicts_total`.

Out of scope:
- Per-run rollback (FR-031). The pre-apply dump never leaves the runner because the repo's artifacts are public; keeping it needs private storage, which is an operator decision.
- The residual targets file (FR-017).
- Gating apply on conflicts. Conflicts are values the loader declines to write, and past applies went ahead with reviewed conflicts.

## Affected users / systems

- `data/synth-catalog/catalog_scrape.py` (every direct fetch: maker crawl, HP enrich).
- `data/synth-catalog/population.py`, `scripts/catalog_actions_load.py` and `.github/workflows/db-load.yml`.
- Operators running loads, who now need the dry run's `plan_hash` to apply.

## Constraints / non-goals

- No paid fetches; ModularGrid is never fetched.
- Receipts stay counts-only in the public artifacts.
- Local apply (`import_catalog_population.py`) is unchanged.

## Open questions

- **Rollback:** where may a pre-apply dump be kept privately (R2 bucket, Neon branch)? Operator decides.
- **Conflict gate:** should a conflict count above a threshold block apply? Owner decides.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Non-allowed content types and oversized bodies are refused before being read | `OBSERVED` | `tests/test_catalog_transport_limits.py` |
| A dry run and an apply over the same database produce the same `plan_hash` | `OBSERVED` | `test_an_apply_must_name_the_reviewed_plan` (Postgres 15) |
| A wrong or missing hash writes nothing | `OBSERVED` | same test: row counts unchanged |
| Receipts carry run identity, hashes and the full conflict count | `OBSERVED` | `test_receipts_carry_run_identity_hashes_and_the_full_conflict_count` |
| No real maker page is a refused type or over 10 MiB | `INFERRED` | crawl fetches HTML, sitemaps and robots.txt; not re-measured |

## Author / date

- Author: Claude (for Zero-State-LLC)
- Date: 2026-10-28
