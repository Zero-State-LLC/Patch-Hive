# Maker permission basis and proxy tier: decision brief (2026-11-03)

Project card: "[decision] Maker permission metadata and stealth proxy sign-off". This brief ships in the PR that is held for owner sign-off. That PR changes code only where the recommendation below needs it. It edits no spec: the proposed FR-008 wording is [at the end](#proposed-fr-008-wording).

OBSERVED means read in the checkout on `main` at `3688037`; INFERRED means reasoned from it. This is an engineering policy brief, not legal advice.

## Summary

| # | Decision | Recommendation | Owner must answer |
|---|---|---|---|
| 1 | Permission basis for crawling maker pages | C: official spec pages count as publication for facts, with written conditions and an opt-out; ask the maker for anything beyond facts, or where its terms forbid automated access | A, B or C |
| 2 | Firecrawl proxy tier | `basic` by default; `stealth` or `auto` only under a fetch-approvals entry that names the tier | Accept, or allow no exceptions |
| 3 | What counts as a block | A bot-check page now (held PR); 401, 403 and 451 later | Accept the held PR; approve the 401/403 follow-up |

## Where things stand (OBSERVED)

**Permission.** The policy says "bulk operations fail closed without permission metadata", and that "an unknown or disputed access basis blocks bulk publication" ([EXTERNAL_SOURCE_POLICY.md](../EXTERNAL_SOURCE_POLICY.md), release gates and the provenance packet).

- Spec 003 D2, FR-033 and OQ-11 label maker-page rows `access_basis = official_publication`.
- The overlay builders hard-code that value: `scripts/build_maker_overlays.py:239` and `scripts/build_reattribution.py:154`.
- A load from the committed inputs holds 2,492 live `module_catalog` rows with that basis.
- No owner record says whether official spec pages permit bulk crawling: [OPEN_DESIGN_DECISIONS_2026-10-28.md](OPEN_DESIGN_DECISIONS_2026-10-28.md) §5 left it open.
- The crawl rows themselves carry no basis.
- The committed crawl (`maker-crawl-v2.json`) covers 703 brands and 3,536 module rows. It cost 2,569 paid fetches, about 1,116 context.dev and 33 Firecrawl credits (spec 003, "Fetch cost and budget").

**Proxy.**

- `catalog_scrape.py` defaults Firecrawl's proxy tier to `auto` (`:339`).
- FR-008 records that default. The 2026-10-28 review recommended basic only, and no sign-off is recorded.
- The paid-fetch approvals file (`receipts/fetch-approvals.json`, FR-003) covers spend, not the tier.

**Blocks.**

- D7 says a refused site stays refused and is never fetched "through a paid renderer or proxy from another network".
- The router still sent a 200 bot-check page to context.dev, then Firecrawl (`catalog_scrape.py:437-440`). Only Frap and Tiptop were protected, by being excluded by name.
- Three other refusals still reach the paid backends:
  - a robots.txt that answers anything but 200 or 404, such as 403 (`:423-428`, `robots_unavailable`);
  - a page that answers 401, 403 or 451;
  - a refused connection, which shares status 0 with timeouts (`:450-452`).

## Decision 1: the permission basis

| Option | What it means | For | Against |
|---|---|---|---|
| A. Official spec pages count as publication | Record `official_publication` for every maker. Conditions: maker-owned domains only, robots.txt honoured, facts only (name, HP, power, depth, category), no copied descriptions or images, a per-host delay, no route around a block. | Matches D2 and the 2,492 rows already loaded. Costs nothing. The crawl can resume once fetching is allowed. | A maker may object, and A has no opt-out unless one is added. |
| B. Ask every maker | Default `unknown`. Crawl and publish only brands that said yes, recorded as `maker_permission`. | The strongest basis. Answers may lead to data feeds (`authorized_feed`). | Slow, and replies from 703 brands will be partial (INFERRED). The catalog stays frozen meanwhile. The 2,492 loaded rows would have to drop to `unknown` and leave bulk publication and export. |
| C. A for facts, B for the rest | `official_publication` by default, under A's conditions plus an opt-out: a maker who asks is set to `unknown` in `maker-sources.json` and left out. Ask first for descriptions, images or manuals beyond facts, and for makers whose terms forbid automated access. | Keeps the loaded catalog. Gives makers a way out. Matches the policy's source hierarchy, which puts official pages first. | Needs a short, published opt-out note (a contact address), and a per-brand terms check for the top makers. |

**Recommendation: C.**

- On sign-off, set `permission_basis.default` in `data/synth-catalog/maker-sources.json` to `official_publication`.
- When a maker opts out, or its terms forbid automated access, set that brand to `unknown` under `brands`.
- If PatchHive sells or exports the catalog in bulk, have counsel read the policy first. That is the point where "publication" matters most.

The held PR adds `permission_basis` to every crawl row, read from `maker-sources.json`: the brand's own entry, else the default. The default ships as `unknown`, so nothing a new crawl writes claims a basis before the owner records one. The allowed values are the policy's `access_basis` values that apply to a crawl, plus `maker_permission` for "the maker said yes". If B or C is chosen, add `maker_permission` to the policy's list.

## Decision 2: the proxy tier

| Option | Effect |
|---|---|
| Keep `auto` (main today) | Firecrawl may switch to stealth whenever it decides, with no record of approval. |
| `basic` only | No exceptions. Simplest. |
| `basic` by default; `stealth` or `auto` per approval (held PR) | A non-basic tier needs an unexpired `fetch-approvals.json` entry that covers the run's brands and names the tier (`"proxy_tier": "stealth"`). Without one, the Firecrawl call is skipped and recorded (`skipped_no_approval`, or `skipped_proxy_unapproved` when there is no approvals file). The crawler also refuses a paid run up front. |

**Recommendation: basic by default, with per-approval exceptions.** Expect almost no exceptions. Stealth exists to get past anti-bot systems, and under D7 (and decision 3) a host that blocks is not fetched at all. The approval route keeps a deliberate, recorded owner exception possible, for example a maker that asks PatchHive to fetch through a particular tier.

## Decision 3: what counts as a block

- **Held PR.** A 200 bot-check page (the router's `CHALLENGE` pattern) is a refusal. It is recorded with the note `challenge` and never sent to a paid backend.
- **Still open: 401, 403 and 451 on a page, and 401 or 403 on robots.txt.** These still fall through to the paid backends.
  - Recommendation: treat them as refusals too, in a follow-up PR after sign-off.
  - Keep 429, 5xx and timeouts eligible for a paid retry: those are load, not refusal.
- **Refused connections (Frap).** These cannot be told apart from timeouts today: both are status 0. Telling them apart needs the transport to report the error kind. Until then, a host that refuses connections stays excluded by name, as D7 does now.

## What the held PR changes

- `data/synth-catalog/catalog_scrape.py`:
  - The Firecrawl tier defaults to `basic` (`firecrawl_proxy_tier()`).
  - `check_paid_approval(..., proxy_tier=)` matches a non-basic tier only to an entry that names it.
  - `_reserve_paid` refuses a non-basic Firecrawl call without such an entry.
  - A bot-check page returns the refusal without a paid fallback.
- `scripts/catalog_maker_crawl.py`:
  - The paid-run gate passes the configured tier.
  - Every crawl row, and the brand record, carry `permission_basis`.
- `scripts/maker_adapters.py` and `data/synth-catalog/maker-sources.json`: a `permission_basis` block (`default: unknown`, `brands: {}`), validated on load.
- `receipts/fetch-approvals.json`: `proxy_tier` is documented in `entry_format`. The committed corpus-photos entry is unchanged and stays basic.
- Docs: `SCRAPING_ARCHITECTURE.md` and the `hermes_hp_enrich_firecrawl.py` docstring describe the new default.

Nothing is fetched or loaded. The committed crawl and overlays are unchanged.

## After sign-off

1. Retitle and merge the held PR.
2. Record the basis in `maker-sources.json`.
3. Then catalog fetching can resume under FR-003 approvals:
   - the T031 feed re-crawl (281 untagged rows, [#253](https://github.com/Zero-State-LLC/Patch-Hive/pull/253));
   - the maker-page pass (the 7 rows in [#250](https://github.com/Zero-State-LLC/Patch-Hive/pull/250), the Plum ex2 HP, and the 59 rows #253 lists).
4. Follow-ups:
   - make `build_maker_overlays.py` copy the crawl row's `permission_basis` instead of hard-coding `official_publication`;
   - the 401/403/451 refusals (decision 3).

## Proposed FR-008 wording

Not applied: spec 003 belongs to another session. Proposed replacement for FR-008:

> **FR-008**: The fetch job MUST rate-limit requests with a delay between scrapes [OBSERVED: scripts/hermes_hp_enrich_firecrawl.py]. Paid fetches through Firecrawl use its `basic` proxy tier. A `stealth` or `auto` tier (`PATCHHIVE_FIRECRAWL_PROXY`) is used only under an unexpired `receipts/fetch-approvals.json` entry that covers the run's brands and names that tier (`proxy_tier`); without one the Firecrawl call is skipped and recorded (`skipped_no_approval`, or `skipped_proxy_unapproved` when no approvals file is set). A proxy changes where a fetch comes from, never what may be fetched: a page that answers with a bot check is recorded as a refusal and is never sent to a paid backend (D7). context.dev documents no proxy option.

If decision 1 is taken, a matching line for the provenance requirements:

> Every maker-crawl row MUST record `permission_basis`, from `maker-sources.json` (`permission_basis.default`, or the brand's own entry). `unknown`, the default until the owner records a basis, blocks bulk publication (EXTERNAL_SOURCE_POLICY release gates).
