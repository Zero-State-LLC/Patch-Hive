# Intent

## Problem

Spec 003 OQ-2 (Jev decision 2026-11-01, `hand_check_then_correct`): nine modules had a v1 HP that disagreed with a maker-sourced value, and nobody had checked which was right.

## Proposed outcome

Read each maker page or manual (free GETs, robots.txt honoured, 2 s apart, stop at the first block) and add a reviewed `correct` entry for any wrong stored value. Result: eight of the nine have a maker quote equal to what staging and production already store, so no stored value is wrong and no correction is needed; `module-catalog-hp-v7` records the quotes so a fresh load takes the maker value, never v1's. Akemie's Castle is left open.

Out of scope: retailer sources for Akemie's Castle (FR-039 retailer evidence only moves markers), and any load (v7 changes nothing in either database).

## Affected users / systems

Catalog inputs only (`inputs_hash` changes, so the next dry run's hash changes); no row changes.

## Constraints / non-goals

Maker sources only; quotes verbatim from the saved page; no route around a block (ALM's manual host answered with a bot check, so it was not fetched further).

## Open questions

- Akemie's Castle: staging's `module_catalog` holds 18 (v1, filled before #152), while `modules` holds 38 and a fresh load gives 38 (maker-crawl overlay v2). A `correct` entry needs a maker quote: ALM's spec sheet or an owner decision.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Staging stores 14, 14, 20, 24, 10, 12, 12, 14, 14 for the nine slugs | `OBSERVED` | staging catalog and modules APIs, 2026-11-02 |
| Each quote appears in the saved maker page or manual | `OBSERVED` | script check before writing the overlay |
| v7 plans no change on a database holding those values | `OBSERVED` | `tests/unit/test_hp_v7_hand_check.py`, replica dry run |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-02
