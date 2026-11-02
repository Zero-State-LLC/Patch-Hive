# Intent

## Problem

Spec 003 FR-003 says the fetch job must not start or resume without a recorded budget approval. Caps lived in chat and `SCRAPING_ARCHITECTURE.md`; nothing in code stopped a paid fetch without one (OQ-3).

## Proposed outcome

Per the 2026-11-01 Jev decision (`approvals_file`), `receipts/fetch-approvals.json` holds approval entries (id, approver, expires_at, brands, cap_fetches, cap_credits, optional ledger baseline). `CatalogScraper` refuses a paid fetch or search without a matching unexpired entry whose caps the spend ledger has not reached, and `catalog_maker_crawl.py` refuses to start a non-dry-run without one. The file ships with no active entries.

Out of scope: free fetches, dry runs, `population.py`, any real paid run.

## Affected users / systems

`data/synth-catalog/catalog_scrape.py`, `scripts/catalog_maker_crawl.py`, and every script using `CatalogScraper.for_repo` (they now need an entry when `--max-paid-fetches` is above 0).

## Constraints / non-goals

Fail closed: a missing or unreadable file, an expired entry, an unlisted brand or a reached cap all deny. A run without `--brands` needs a `"*"` entry. Ledger spend is counted since the entry's baseline, because `scrape-ledger.json` is cumulative.

## Open questions

- The owner adds the first real entry (cap, brands, expiry) when approving the next paid run.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Paid calls are refused without a matching entry and free fetches still work | `OBSERVED` | `backend/tests/test_catalog_scrape_router.py` |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-01
