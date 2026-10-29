# Intent

## Problem

The v1 crawl gave several brands another maker's homepage; the v2 crawl then filed that maker's modules under each name. #116 stopped overlay builds from using such brands, but the crawler itself still crawled them, so a new crawl would produce the duplicates again (spec 003 T030).

## Proposed outcome

- `catalog_maker_crawl.py` resolves every brand before crawling any. `guard_shared_homepages` compares each resolved host with the other brands' hosts in this run and in the committed crawl.
- Owner of a shared host: the brand named in the host; failing that, the one brand resolved by a maker adapter or the curated list. Every other brand on that host (all of them with no owner) is recorded as `shared_homepage`, with its owner and candidate URL, in the receipt, and is not crawled.
- Resolution respects the budget stop (`resolve_within_budget`).
- `build_maker_overlays.shared_homepage_conflicts` is the one rule both tools use; `shared_homepage_skips` keeps its name-only behaviour, so committed overlays and the retirement manifest are unchanged.

Out of scope: retiring the duplicates this finds that are still live in prod (ALM Busy Circuits copied under four brands, Instruō, and the hosts with no owner). That is an owner decision, like #116.

## Affected users / systems

- `scripts/catalog_maker_crawl.py`, `scripts/build_maker_overlays.py`, crawl receipts.

## Constraints / non-goals

No fetches in tests; committed crawl data only. Behaviour of committed overlays unchanged.

## Open questions

Whether to retire the newly found live duplicates (about 180 rows) with a second manifest.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The committed v2 resolutions refuse 18 brands, including all 8 retired in #116 | `OBSERVED` | `tests/test_crawl_shared_homepages.py` |
| A dry run records the refusal and crawls the owner | `OBSERVED` | local dry run on Make Noise and Mental Noise, 0 paid calls |
| The newly found duplicates are live in prod | `OBSERVED` | read-only prod query |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
