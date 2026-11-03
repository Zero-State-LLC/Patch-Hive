# Intent

## Problem

The maker crawl has no recorded permission basis, though the source policy says bulk operations fail closed without one. Firecrawl's proxy tier defaults to `auto` with no sign-off. The router sends a bot-check page to the paid render and proxy backends, against spec 003 D7 ("a refused site stays refused").

## Proposed outcome

- A decision brief with options and a recommendation for the permission basis, the proxy tier and what counts as a block, plus proposed FR-008 wording: [MAKER_PERMISSION_AND_PROXY_DECISION_2026-11-03.md](../docs/evidence/MAKER_PERMISSION_AND_PROXY_DECISION_2026-11-03.md).
- A PR held for owner sign-off that:
  - defaults the tier to `basic`;
  - allows `stealth` or `auto` only under a fetch-approvals entry that names the tier;
  - never sends a bot-check page to a paid backend;
  - records `permission_basis` on every crawl row (`unknown` until the owner records one).

Out of scope: editing spec 003 or the source policy, any fetch, any load, and changing the hard-coded `official_publication` in the overlay builders (a follow-up after the decision).

## Affected users / systems

The catalog fetch router (`catalog_scrape.py`) and every caller: the maker crawl, the HP enrichment script, the unmatched pass and the corpus-photo finder. Also `maker-sources.json` and the fetch-approvals format. No product runtime path changes.

## Constraints / non-goals

Fail closed: no tier escalation and no route around a block without a recorded approval. Nothing is fetched. This brief is not legal advice.

## Open questions

- Permission basis A, B or C? Owner.
- The proxy tier: basic with per-approval exceptions, or basic only? Owner.
- Treat 401, 403 and 451 as blocks too (follow-up)? Owner.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| main defaults the tier to `auto` and escalates bot-check pages to paid backends | `OBSERVED` | `catalog_scrape.py:339`, `:437-440` on `3688037` |
| With this PR, a stealth Firecrawl call runs only under an entry naming `stealth` | `OBSERVED` | `tests/test_catalog_scrape_router.py` |
| A bot-check page reaches no paid backend | `OBSERVED` | `tests/test_catalog_scrape_router.py`, `tests/test_maker_crawl.py` |
| Treating official spec pages as publication for facts is low risk | `INFERRED` | Not legal advice; counsel should review before any bulk sale or export |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-03
