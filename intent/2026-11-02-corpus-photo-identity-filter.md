# Intent

## Problem

The first live run of `scripts/vision/find_corpus_photos.py` (300 approved context.dev searches) produced 668 rights-confirmed rows from only 75 distinct pages. Search engines answer `"<maker> <module>"` with generic rack photos, and the tool kept every result, proposed the searched module as its identity and downloaded it. The review queue had 644 items, nearly all of which named the wrong module. Its token check also matched part of a model number ("A-101-1" inside "A-101-2, A-106-1") and accepted a module name without its maker ("Kraken Supercomputer" for WMD Kraken).

## Proposed outcome

- `identity_match` requires the page to name the maker (a brand token other than a generic word) and the module name as a phrase, with no characters glued on.
- `search` downloads only pages that name the module. Other rows are recorded as `image_reference` with `exclusion_reason: identity_not_named` and no proposed identity, and counted in `summary.json`.
- `refilter` applies the check to an earlier `candidates.jsonl` with no network call, so the 2026-11-02 run is corrected without new spend.
- `docs/evidence/CORPUS_PHOTO_SEARCH_2026-11-02.md` records the run's counts, spend and the 2 images left. The ledger change from the run is committed.

Out of scope: more searches (the approval is used up), admitting or reviewing cases, changing the promotion queue.

## Affected users / systems

The operator building the 007 corpus; the promotion queue gets fewer, better candidates.

## Constraints / non-goals

Vision cannot self-confirm: rows stay UNVERIFIED. No network call in tests. No image bytes in the repo.

## Open questions

- Where the 50 to 100 T010b identities come from: owner photos or maker-licensed photos (owner decision).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The run used 300 paid searches and 295 credits | `OBSERVED` | `summary.json`, ledger diff |
| 6 of 668 rows name their maker and module | `OBSERVED` | `refilter` over the run's `candidates.jsonl` |
| The live false positives are now excluded | `OBSERVED` | parametrized cases in `backend/tests/unit/test_find_corpus_photos.py` |
| Flickr photo pages are disallowed to the crawler | `OBSERVED` | 108 `robots_disallowed` receipts |
