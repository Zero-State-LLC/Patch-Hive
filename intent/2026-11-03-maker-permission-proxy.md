# Intent

## Problem

The maker crawl has no recorded permission basis, though the source policy says bulk operations fail closed without one. Firecrawl's proxy tier defaults to `auto` with no sign-off. The router sends a bot-check page to the paid render and proxy backends, against spec 003 D7 ("a refused site stays refused").

## Proposed outcome

- A decision brief with options, the owner's decisions of 2026-11-04 and the FR-008 wording: [MAKER_PERMISSION_AND_PROXY_DECISION_2026-11-03.md](../docs/evidence/MAKER_PERMISSION_AND_PROXY_DECISION_2026-11-03.md).
- A PR that records those decisions and:
  - defaults the tier to `basic`;
  - allows `stealth` or `auto` only under a fetch-approvals entry that names the tier;
  - never sends a bot-check page, a page answering 401, 403 or 451, or a robots.txt answering 401 or 403 to a paid backend;
  - records `permission_basis` on every crawl row (`official_publication` by default, `unknown` for a maker who opted out);
  - updates spec 003 and the source policy to match.

Out of scope: any fetch, any load, making the crawl skip a brand set to `unknown`, and changing the hard-coded `official_publication` in the overlay builders (follow-ups after this PR).

## Affected users / systems

The catalog fetch router (`catalog_scrape.py`) and every caller: the maker crawl, the HP enrichment script, the unmatched pass and the corpus-photo finder. Also `maker-sources.json` and the fetch-approvals format. No product runtime path changes.

## Constraints / non-goals

Fail closed: no tier escalation and no route around a block without a recorded approval. Nothing is fetched. This brief is not legal advice.

## Open questions

The owner answered these on 2026-11-04 (`docs/evidence/OWNER_DECISIONS_2026-11-04.md`, items 1 to 3):

- Permission basis A, B or C? C.
- The proxy tier: basic with per-approval exceptions, or basic only? Basic with per-approval exceptions.
- Treat 401, 403 and 451 as blocks too? Yes: on a page, plus 401 and 403 on robots.txt.

`render=True` now makes one free GET first, so it can see a page refuse. The brief explains why.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| main defaulted the tier to `auto` and escalated bot-check pages to paid backends | `OBSERVED` | `catalog_scrape.py:339`, `:437-440` on `3688037` |
| With this PR, a stealth Firecrawl call runs only under an entry naming `stealth` | `OBSERVED` | `tests/test_catalog_scrape_router.py` |
| A bot-check page reaches no paid backend | `OBSERVED` | `tests/test_catalog_scrape_router.py`, `tests/test_maker_crawl.py` |
| A page answering 401, 403 or 451, and a robots.txt answering 401 or 403, reach no paid backend | `OBSERVED` | `tests/test_catalog_scrape_router.py` |
| A refused connection cannot be told from a timeout | `OBSERVED` | `catalog_scrape.py` `default_transport`, `_free_get`; `tests/test_catalog_scrape_router.py` |
| Treating official spec pages as publication for facts is low risk | `INFERRED` | Not legal advice; counsel should review before any bulk sale or export |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-03, updated 2026-11-04
