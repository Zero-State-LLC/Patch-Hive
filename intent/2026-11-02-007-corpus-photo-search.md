# Intent

## Problem

Spec 007 T010b needs 50 to 100 identities of rights-cleared, reviewed photos, and the pilot manifest has 0 cases. The owner (2026-11-02, in chat) asked to use context.dev to find photos of modular synths and approved a cap of 300 searches. No tool searched for openly licensed photos, checked their licenses, or kept the image bytes out of the repo.

## Proposed outcome

`scripts/vision/find_corpus_photos.py`:

- `starter` writes an identities file (brand, name, slug, manufacturer_url) from the committed catalog seeds and addition overlays for slugs the operator picks; retired slugs are skipped.
- `search` runs one search per identity through `CatalogScraper.for_repo` (DuckDuckGo first, then context.dev; never Firecrawl), keeps only Commons File pages and Flickr photo pages, fetches each page free, accepts only CC0, public domain, CC BY and CC BY-SA, downloads accepted originals into an out-dir outside any git checkout, and writes `candidates.jsonl`, `modules.jsonl`, `receipts.jsonl` and `summary.json` in the shape `scripts/build_vision_promotion_queue.py` reads.
- Approval entry `corpus-photos-2026-11` (300 fetches, 300 credits, baseline at the 2026-11-02 ledger totals) in `data/synth-catalog/receipts/fetch-approvals.json`.

Out of scope: running the search, admitting or reviewing any case, changing the promotion queue or the pilot validator, storing images in the repo or in R2.

## Affected users / systems

The operator collecting the 007 corpus. The FR-003 approval gate: the new entry has `brands: ["*"]`, so until it expires (2026-11-30) or its caps are reached it also covers other paid catalog runs (for example `scripts/catalog_maker_crawl.py`) that share the same ledger. The test that pinned the empty approvals file now pins exactly this entry.

## Constraints / non-goals

Vision cannot self-confirm: rows stay `UNVERIFIED` / `DISCOVERED`, the searched identity is only a proposal, and no row is marked `OPERATOR_VERIFIED`, `TWO_SOURCE_VERIFIED` or `REVIEWED`. Rights fail closed: no readable license, NC, ND, other licenses, or BY without an author are not `RIGHTS_CONFIRMED`. Free fetches respect robots.txt with 2 s spacing per host; Commons' API is not used because robots.txt disallows it. No ModularGrid source. No real network call in tests.

## Open questions

- Flickr page markup was not observed live in this work; parsing relies on the `rel="license"` link and the `live.staticflickr.com` size suffixes. If Flickr no longer serves those in plain HTML, Flickr rows fall back to `no_license_found` (excluded), which is safe but finds less.
- The `*` brand scope of the approval also opens other paid runs. The owner may prefer a narrower entry; that needs a gate change (approval per tool) and is not made here.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| License parsing accepts and excludes the sample Commons and Flickr pages as specified | `OBSERVED` | `backend/tests/unit/test_find_corpus_photos.py` |
| The run never calls Firecrawl and refuses without a matching approval, before any request | `OBSERVED` | same tests, fake transport |
| Rows feed `build_vision_promotion_queue.build_queue` unchanged | `OBSERVED` | same tests |
| Ledger baseline 2569 fetches / 1149 credits matches `receipts/scrape-ledger.json` at commit | `OBSERVED` | ledger file on the branch base |
| Live Commons and Flickr pages carry the parsed markup | `INFERRED` | MediaWiki license templates; not fetched in this work |
| How many usable photos 300 searches yield | `NOT_COMPUTABLE` | no live run |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-02
