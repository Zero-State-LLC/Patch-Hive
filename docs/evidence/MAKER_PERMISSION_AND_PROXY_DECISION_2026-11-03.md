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

This PR also goes further than the decisions in one place: a robots.txt that cannot be read stops that host, free and paid (see decision 3).

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
- When a maker opts out, or its terms forbid automated access, set that brand to `unknown` under `brands`. That is enforced:
  - the crawl does not resolve or fetch the brand, under any spelling of its name (`Instruo` and `Instruō` are both in the committed crawl);
  - the router refuses the maker's known hosts for every script, so a second brand name, the HP enrichment or the unmatched pass cannot reach them;
  - `build_maker_overlays.py` and `build_reattribution.py` read the basis from `maker-sources.json` and give that maker no rows.
- An opt-out does not reach rows already in committed overlays. Those keep `official_publication` and still load, until a retirement manifest removes them (spec 003 D3).
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

On a page, 429, 5xx and timeouts stay eligible for a paid retry: those are load, not refusal.

**robots.txt fails closed.** This goes further than the owner's decision. A robots.txt that gives any answer but 200 or 404, or no answer, means no fetch of that host for the run, free or paid. It is recorded as `robots_unavailable` with a note such as `robots.txt answered 503` or `robots.txt did not answer`. 401 and 403 keep their own `robots_refused` record from the decision.

This covers 451, 429, 5xx, other 4xx, timeouts and refused connections on robots.txt. The last two are both status 0, so it does not matter that the code cannot tell them apart there. A host that refuses every connection (Frap) now stops at robots.txt, and stays excluded by name as well.

The cost is yield, and nothing was fetched to measure it. In the committed crawl, 34 of 703 brands (89 module rows, including Befaco's 26 and Instruo's) have `robots_unavailable` results, and 38 curated homepages are noted as inconclusive for that reason. Their committed rows stay. If their robots.txt still cannot be read, those hosts cannot be re-fetched, and those homepages cannot be confirmed. The T035 makers (4ms Company, Dave Jones Design, Velectronic) have no `robots_unavailable` results.

**Not covered: a refused connection on a page.** `default_transport` and `_free_get` turn every transport error into status 0. So if robots.txt was readable and the page then gives status 0, it stays eligible for a paid retry, whether that was a timeout or a refusal. Telling them apart needs the transport to report the error kind.

## What this PR changes

- `data/synth-catalog/catalog_scrape.py`:
  - The Firecrawl tier defaults to `basic` (`firecrawl_proxy_tier()`).
  - `check_paid_approval(..., proxy_tier=)` matches a non-basic tier only to an entry that names it.
  - `_reserve_paid` refuses a non-basic Firecrawl call without such an entry.
  - A bot-check page, a page answering 401, 403 or 451, and a robots.txt answering 401 or 403 return a recorded refusal with no paid fallback (`PAGE_REFUSAL_STATUSES`, `ROBOTS_REFUSAL_STATUSES`).
  - `render=True` makes one free GET first, recorded with the note `render_check` unless it is a refusal.
  - A robots.txt that cannot be read stops the host, with the reason recorded.
  - `left_out_hosts` and `_block_reason` refuse a left-out maker's known hosts, before the disk cache and in `robots_info`.
- `scripts/catalog_maker_crawl.py`:
  - The paid-run gate passes the configured tier.
  - Every crawl row, and the brand record, carry `permission_basis`.
  - A left-out brand is recorded with the status `left_out` and is not resolved or crawled.
- `scripts/build_maker_overlays.py` and `scripts/build_reattribution.py`: the basis comes from `maker-sources.json`, and a left-out maker gets no rows.
- `scripts/maker_adapters.py` and `data/synth-catalog/maker-sources.json`: a `permission_basis` block (`default: official_publication`, `brands: {}`), validated on load.
- `receipts/fetch-approvals.json`: `proxy_tier` is documented in `entry_format`. The committed corpus-photos entry is unchanged and stays basic.
- Docs:
  - Spec 003: FR-008, a new FR-040, and updates under D2 and D7.
  - `EXTERNAL_SOURCE_POLICY.md`: the option C conditions, the opt-out rule and `maker_permission`.
  - `SCRAPING_ARCHITECTURE.md` and the `hermes_hp_enrich_firecrawl.py` docstring describe the new behaviour.

Nothing is fetched or loaded. The committed crawl and overlays are unchanged.

## What this does to committed overlay output

Both builders delete and rewrite overlay files, so they were run on throwaway copies of the repo at `54c96a5`, with the old code and the new code, using the invocations recorded in `SCRAPING_ARCHITECTURE.md` and the A3 intent. No overlay in this PR was regenerated.

**This PR's change to the builders alters no output.** With no maker opted out, old and new builders wrote byte-identical files for all four builds.

**A rebuild, by either builder, would change committed data.** This drift predates this PR. Later overlays and later builder rules change what the older versions come out as:

| Build | File | Against the committed file |
|---|---|---|
| T025 | `catalog-additions-v3.json` | Differs: 2,492 rows rebuilt, 2,737 committed; 1 only in the rebuild, 246 only in the committed file |
| T025 | `module-power-depth-v11.json` | Differs: 3,114 rows rebuilt, 3,241 committed; 139 only in the rebuild, 266 only in the committed file |
| T026 | `catalog-additions-v4.json` | Differs: 134 rows rebuilt, 136 committed; 2 only in the committed file |
| T026 | `module-power-depth-v12.json` | Same |
| A3 | `catalog-additions-v6.json`, `module-power-depth-v14.json` | Same |
| Reattribution v2 | `catalog-retirements-v2.json` | Same |
| Reattribution v2 | `module-power-depth-v15.json` | **Deleted.** It is the hand-built Endorphin.es overlay from #178, on a version number `build_reattribution.py --version 2 --rebuild` also claims |

**An opt-out does what it should.** With Befaco set to `unknown` on a throwaway copy, the T025 build lost 21 additions rows and 25 power rows, all Befaco, and gained none. The committed files would not change until someone rebuilt them, and rebuilding them brings the drift above with it. So use a retirement manifest for an opt-out, not a rebuild.

## The 26 Befaco rows

Flagged because the adapter uses `render`, and `www.befaco.org` answered 403 to a plain GET ([OWNER_ACTIONS_2026-11-02.md](OWNER_ACTIONS_2026-11-02.md)). This PR does not change them.

**Recorded (OBSERVED):**

- All 26 are in `hermes-research/maker-crawl-v2.json` with `fetch_method: cache` and `extracted_by: regex`. That crawl is dated 2026-10-27.
- The brand's record shows `adapter:listing`, 89 pages discovered, and fetch results of 40 `cache` and 49 `robots_unavailable`.
- The T024 paid run was context.dev only, in three passes. The last used `--max-paid-fetches 0` on cached pages, which fits `cache` here.
- The adapter's note then read "unreachable over free HTTP from the dev box; needs the paid tier".
- No entry in `receipts/fetch-approvals.json` names Befaco. That file's committed entry covers the corpus photos.
- `catalog-additions-v3` and `module-power-depth-v11` were loaded to staging and production (tasks T025, T027).

**Not recorded:** which backend first fetched each page, and what robots.txt answered at the time. `robots_unavailable` says only that it was neither 200 nor 404. The disk cache holding each page's first method is gitignored and is not on this machine.

**Inferred:** these pages probably came from a paid context.dev render. The router makes no free GET when robots.txt cannot be read, and the adapter asked for a render. If the 403 seen on 2026-11-02 also held on 2026-10-27, these rows came through what decision 3 now calls a refusal. Nothing here proves that it did.

The first row looks wrong: "Befaco" at 18 HP, from `/feed/`, is not a module. The builder already drops it, so no overlay holds it.

| Crawl row | HP | Page on www.befaco.org | Overlays holding that name |
|---|---|---|---|
| Befaco | 18 | `/feed/` | none |
| 1 U Motion MTR | 34 | `/1u-motion-mtr/` | additions v3, power v11 |
| 1U OUT | 16 | `/1u-out/` | additions v3, power v11 |
| 1U STMIX | 28 | `/1u-stmix/` | additions v3, power v11 |
| 1U ST AMP | 10 | `/1u-st-amp/` | additions v3, power v11 |
| 1U TRS | 6 | `/1u-trs/` | additions v3, power v11 |
| A\*B+C | 6 | `/axbc/` | additions v3, power v11 |
| ARK | 40 | `/ark/` | additions v3, power v11 |
| Atte | 4 | `/atte/` | additions v3, power v11 |
| Bandit | 8 | `/bandit/` | power v11 |
| BF-22 | 17 | `/bf-22/` | additions v3, power v11 |
| Burst | 8 | `/burst-2/` | additions v3, power v11 |
| Chopping Kinky | 8 | `/chopping-kinky/` | power v11 |
| Crush Delay V3 | 11 | `/crush-delay-v3/` | additions v3, power v11 |
| Even VCO | 8 | `/even-vco/` | power v11 |
| FX BOY | 12 | `/fx-boy/` | additions v3, power v11 |
| Hexmix | 28 | `/hexmix/` | additions v3, power v11 |
| Hexmix VCA | 14 | `/hexmix-vca/` | additions v1, power v8, power v11 |
| Hexpander | 28 | `/hexpander/` | additions v3, power v11 |
| I4 | 8 | `/i4-instrument-interface/` | additions v3, power v11 |
| InAmp | 4 | `/inamp/` | additions v3, power v11 |
| VC ADSR | 8 | `/vc-adsr/` | additions v3, power v11 |
| VCMC | 20 | `/vcmc-2/` | additions v3, power v11 |
| Voltio | 6 | `/voltio/` | additions v3, power v11 |
| Oneiroi | 42 | `/oneiroi-pod/` | additions v3, power v11 |
| Trolley Bus | 4 | `/trolley-bus/` | additions v3, power v11 |

A name in an older overlay can have come from another source: Hexmix VCA is in `catalog-additions-v1`, which predates this crawl.

## After merge

1. Catalog fetching can resume under FR-003 approvals:
   - the T031 feed re-crawl (281 untagged rows, [#253](https://github.com/Zero-State-LLC/Patch-Hive/pull/253));
   - the maker-page pass (the 7 rows in [#250](https://github.com/Zero-State-LLC/Patch-Hive/pull/250), the Plum ex2 HP, and the 59 rows #253 lists).
2. Follow-ups:
   - publish the opt-out contact address in the policy once the owner has created it;
   - check the terms of the top makers, and set any that forbid automated access to `unknown`. This needs reading their pages, so it was not done here;
   - give `module-power-depth-v15.json` or the reattribution builder another version number, so `--rebuild` cannot delete it.
3. For the owner to decide: whether to keep the 26 Befaco rows above.

## Wording applied to spec 003

The proposed FR-008 wording is now in spec 003, and the proposed provenance line is FR-040. Two things differ from the proposal:

- FR-008 also names the 401, 403 and 451 refusals, because decision 3 no longer leaves them to a follow-up.
- FR-040 says `unknown` marks a maker who opted out or whose terms forbid automated access. The proposal called it "the default until the owner records a basis", which stopped being true when the owner recorded one.
