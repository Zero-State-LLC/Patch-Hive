# Maker permission basis and proxy tier: decision brief (2026-11-03)

**Status: decided by the owner on 2026-11-04** (`docs/evidence/OWNER_DECISIONS_2026-11-04.md`, items 1 to 3, in #278). The owner took the recommendation on all three decisions, and the PR that ships this brief (#254) applies them. The options stay below as the record of what was chosen from.

Project card: "[decision] Maker permission metadata and stealth proxy sign-off".

OBSERVED means read in the checkout on `main` at `3688037`; INFERRED means reasoned from it. This is an engineering policy brief, not legal advice.

## Summary

| # | Decision | What the owner decided |
|---|---|---|
| 1 | Permission basis for crawling maker pages | C: official spec pages count as publication for facts, with written conditions and an opt-out; ask the maker for anything beyond facts, or where its terms forbid automated access |
| 2 | Firecrawl proxy tier | `basic` by default; `stealth` or `auto` only under an unexpired fetch-approvals entry that names the tier |
| 3 | What counts as a block | A bot-check page; 401, 403 and 451 on a page; 401 or 403 on robots.txt. None of these reach a paid backend. Refused connections stay out of scope, because the code cannot tell them from timeouts |

## Where things stood before this PR (OBSERVED)

**Permission.** The policy says "bulk operations fail closed without permission metadata", and that "an unknown or disputed access basis blocks bulk publication" ([EXTERNAL_SOURCE_POLICY.md](../EXTERNAL_SOURCE_POLICY.md), release gates and the provenance packet).

- Spec 003 D2, FR-033 and OQ-11 label maker-page rows `access_basis = official_publication`.
- The overlay builders hard-code that value: `scripts/build_maker_overlays.py:239` and `scripts/build_reattribution.py:154`.
- A load from the committed inputs holds 2,492 live `module_catalog` rows with that basis.
- No owner record said whether official spec pages permit bulk crawling: [OPEN_DESIGN_DECISIONS_2026-10-28.md](OPEN_DESIGN_DECISIONS_2026-10-28.md) §5 left it open.
- The crawl rows themselves carried no basis.
- The committed crawl (`maker-crawl-v2.json`) covers 703 brands and 3,536 module rows. It cost 2,569 paid fetches, about 1,116 context.dev and 33 Firecrawl credits (spec 003, "Fetch cost and budget").

**Proxy.**

- `catalog_scrape.py` defaulted Firecrawl's proxy tier to `auto` (`:339`).
- FR-008 recorded that default. The 2026-10-28 review recommended basic only, and no sign-off was recorded.
- The paid-fetch approvals file (`receipts/fetch-approvals.json`, FR-003) covered spend, not the tier.

**Blocks.**

- D7 says a refused site stays refused and is never fetched "through a paid renderer or proxy from another network".
- The router still sent a 200 bot-check page to context.dev, then Firecrawl (`catalog_scrape.py:437-440`). Only Frap and Tiptop were protected, by being excluded by name.
- Three other refusals also reached the paid backends:
  - a robots.txt that answered anything but 200 or 404, such as 403 (`:423-428`, `robots_unavailable`);
  - a page that answered 401, 403 or 451;
  - a refused connection, which shares status 0 with timeouts (`:450-452`).

## Decision 1: the permission basis

| Option | What it means | For | Against |
|---|---|---|---|
| A. Official spec pages count as publication | Record `official_publication` for every maker. Conditions: maker-owned domains only, robots.txt honoured, facts only (name, HP, power, depth, category), no copied descriptions or images, a per-host delay, no route around a block. | Matches D2 and the 2,492 rows already loaded. Costs nothing. The crawl can resume once fetching is allowed. | A maker may object, and A has no opt-out unless one is added. |
| B. Ask every maker | Default `unknown`. Crawl and publish only brands that said yes, recorded as `maker_permission`. | The strongest basis. Answers may lead to data feeds (`authorized_feed`). | Slow, and replies from 703 brands will be partial (INFERRED). The catalog stays frozen meanwhile. The 2,492 loaded rows would have to drop to `unknown` and leave bulk publication and export. |
| C. A for facts, B for the rest | `official_publication` by default, under A's conditions plus an opt-out: a maker who asks is set to `unknown` in `maker-sources.json` and left out. Ask first for descriptions, images or manuals beyond facts, and for makers whose terms forbid automated access. | Keeps the loaded catalog. Gives makers a way out. Matches the policy's source hierarchy, which puts official pages first. | Needs a short, published opt-out note (a contact address), and a per-brand terms check for the top makers. |

**Decided: C.**

- `permission_basis.default` in `data/synth-catalog/maker-sources.json` is now `official_publication`.
- When a maker opts out, or its terms forbid automated access, set that brand to `unknown` under `brands`.
- The conditions and the opt-out rule are in [EXTERNAL_SOURCE_POLICY.md](../EXTERNAL_SOURCE_POLICY.md). The opt-out contact address follows once the owner has created it.
- If PatchHive sells or exports the catalog in bulk, counsel reads the policy first. That is the point where "publication" matters most.

This PR adds `permission_basis` to every crawl row, read from `maker-sources.json`: the brand's own entry, else the default. The allowed values are the policy's `access_basis` values that apply to a crawl, including `maker_permission` for "the maker said yes", which is now in the policy's list.

## Decision 2: the proxy tier

| Option | Effect |
|---|---|
| Keep `auto` (main before this PR) | Firecrawl may switch to stealth whenever it decides, with no record of approval. |
| `basic` only | No exceptions. Simplest. |
| `basic` by default; `stealth` or `auto` per approval | A non-basic tier needs an unexpired `fetch-approvals.json` entry that covers the run's brands and names the tier (`"proxy_tier": "stealth"`). Without one, the Firecrawl call is skipped and recorded (`skipped_no_approval`, or `skipped_proxy_unapproved` when there is no approvals file). The crawler also refuses a paid run up front. |

**Decided: basic by default, with per-approval exceptions.** Expect almost no exceptions. Stealth exists to get past anti-bot systems, and under D7 (and decision 3) a host that blocks is not fetched at all. The approval route keeps a deliberate, recorded owner exception possible, for example a maker that asks PatchHive to fetch through a particular tier.

## Decision 3: what counts as a block

These are refusals. None of them reach a paid backend:

- **A 200 bot-check page** (the router's `CHALLENGE` pattern), recorded with the note `challenge`.
- **401, 403 and 451 on a page**, recorded as `free_http` with that status and the note `refused`.
- **401 or 403 on robots.txt**, recorded as `robots_refused` with a note such as `robots.txt answered 403`. The page itself is not fetched either.

A refusal is remembered for the run, and it is not written to the disk cache, so the next run asks again.

`render=True` used to skip the free GET, so it could never see a page refuse. It now makes one free GET first, with no retry and without using the body. The decision does not hold without this: the Befaco adapter uses `render`, and `www.befaco.org` answered 403 to a plain GET ([OWNER_ACTIONS_2026-11-02.md](OWNER_ACTIONS_2026-11-02.md)). The cost is one more request per rendered page. It also changed an assertion in an existing test, which had required no free GET (now `test_render_uses_the_paid_body_and_still_applies_robots`).

429, 5xx and timeouts stay eligible for a paid retry: those are load, not refusal.

**Not covered:**

- **Refused connections (Frap).** The code cannot tell these from timeouts: `default_transport` and `_free_get` turn every transport error into status 0. Telling them apart needs the transport to report the error kind. Until then, a host that refuses connections stays excluded by name, as D7 does now.
- **A robots.txt that is unreadable for another reason.** After a 5xx, a 429 or a timeout on robots.txt, the page is not fetched directly, so its own answer is unseen, and a paid backend may still run (`test_robots_unavailable_may_use_paid_backend`).
- **451 on robots.txt.** The decision names 401 and 403 there, so a 451 stays `robots_unavailable`, which may still use a paid backend.

## What this PR changes

- `data/synth-catalog/catalog_scrape.py`:
  - The Firecrawl tier defaults to `basic` (`firecrawl_proxy_tier()`).
  - `check_paid_approval(..., proxy_tier=)` matches a non-basic tier only to an entry that names it.
  - `_reserve_paid` refuses a non-basic Firecrawl call without such an entry.
  - A bot-check page, a page answering 401, 403 or 451, and a robots.txt answering 401 or 403 return a recorded refusal with no paid fallback (`PAGE_REFUSAL_STATUSES`, `ROBOTS_REFUSAL_STATUSES`).
  - `render=True` makes one free GET first, recorded with the note `render_check` unless it is a refusal.
- `scripts/catalog_maker_crawl.py`:
  - The paid-run gate passes the configured tier.
  - Every crawl row, and the brand record, carry `permission_basis`.
- `scripts/maker_adapters.py` and `data/synth-catalog/maker-sources.json`: a `permission_basis` block (`default: official_publication`, `brands: {}`), validated on load.
- `receipts/fetch-approvals.json`: `proxy_tier` is documented in `entry_format`. The committed corpus-photos entry is unchanged and stays basic.
- Docs:
  - Spec 003: FR-008, a new FR-040, and updates under D2 and D7.
  - `EXTERNAL_SOURCE_POLICY.md`: the option C conditions, the opt-out rule and `maker_permission`.
  - `SCRAPING_ARCHITECTURE.md` and the `hermes_hp_enrich_firecrawl.py` docstring describe the new behaviour.

Nothing is fetched or loaded. The committed crawl and overlays are unchanged.

## After merge

1. Catalog fetching can resume under FR-003 approvals:
   - the T031 feed re-crawl (281 untagged rows, [#253](https://github.com/Zero-State-LLC/Patch-Hive/pull/253));
   - the maker-page pass (the 7 rows in [#250](https://github.com/Zero-State-LLC/Patch-Hive/pull/250), the Plum ex2 HP, and the 59 rows #253 lists).
2. Follow-ups:
   - make the crawl leave out a brand set to `unknown`: today it records `unknown` on the rows but still fetches the brand;
   - make `build_maker_overlays.py` and `build_reattribution.py` copy the crawl row's `permission_basis` instead of hard-coding `official_publication`;
   - publish the opt-out contact address in the policy once the owner has created it;
   - check the terms of the top makers, and set any that forbid automated access to `unknown`. This needs reading their pages, so it was not done here.
3. For the owner to review: the committed crawl holds 26 Befaco rows from the `render` adapter, and that brand's record shows 40 `cache` and 49 `robots_unavailable` results. It does not record how those pages first came in, or what robots.txt answered. This PR leaves those rows unchanged.

## Wording applied to spec 003

The proposed FR-008 wording is now in spec 003, and the proposed provenance line is FR-040. Two things differ from the proposal:

- FR-008 also names the 401, 403 and 451 refusals, because decision 3 no longer leaves them to a follow-up.
- FR-040 says `unknown` marks a maker who opted out or whose terms forbid automated access. The proposal called it "the default until the owner records a basis", which stopped being true when the owner recorded one.
