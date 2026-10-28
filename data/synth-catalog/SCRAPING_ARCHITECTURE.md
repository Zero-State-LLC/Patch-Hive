# Catalog scraping architecture audit and method inventory (2026-10-16)

Labels: OBSERVED means checked on the box or in the repo. INFERRED means a recommendation.

## Current architecture (OBSERVED)

- **In-repo scrapers** (before batch 7):
  - `scripts/hermes_hp_enrich_firecrawl.py` calls Firecrawl v1 `/scrape` directly with urllib.
  - `scripts/hermes_hp_enrich_direct.py` and `scripts/enrich_module_power_depth_mg.py` use plain urllib against ModularGrid with a fixed sleep.
  - Each script has its own retry loop. None has a shared ledger, cache, or rate limiter. Provenance is per row (`source_url`, `provenance`, `notes`), but there are no per-fetch receipts (content hash, backend, credits).
- **Data flow**: targets JSON, then `*-results.json`, then `*.filtered.json`, then `overlays/*-vN.json`, then `apply_*_overlay.py --dry-run --receipt`, then admit. Overlays are fill-null only and never invent values.
- **Shared Zero State pipeline**: `/workspace/tools/scrape-router` (package `scrape_router`). It routes by rights, then capability, then budget, then measured success times cost. Order: official API, plain HTTP, Crawl4AI, then context.dev or Firecrawl. Firecrawl uses the enhanced proxy only after a block. The router keeps a sqlite ledger, a 24 h cache, per-domain token-bucket rate limits, and a receipt for every call in `~/.scrape-router/`. Daily and monthly caps are set per backend, with a kill switch. Its MIGRATION.md lists the slang, vernacular, athanor, and Hyperlex pipelines as migration targets. PatchHive was not on that list.

## Batch 7 changes

- `scripts/catalog_batch7_router.py` and `scripts/catalog_batch7b_new_brand_modules.py` call `Router.fetch` and `Router.search` (caller `patchhive:batch7`). They reuse the existing ModularGrid parser (`enrich_module_power_depth_mg.extract_power_depth`, `candidate_urls`) and add a per-run credit cap. Receipts are in `receipts/batch7-router-receipts.json`.

## Recommendations (INFERRED)

1. Route every catalog scraper through scrape-router. Retire the direct Firecrawl and urllib calls in the three legacy scripts. This gives one budget, one cache, rate limits, and receipts.
2. Add retries and backoff in the router layer only, not per script. Leave the router's free-404 rule on so paid backends are never called for a slug that 404s.
3. Use search-first URL resolution for residuals. Slug guessing failed for the 22 power and depth residuals, because pages exist but carry no power block. Next, search manufacturer manuals, and accept only strict `+12V ... mA` patterns, labeled OBSERVED with `source_url`.
4. Dedupe on `(brand, slug)` across the seed, the overlays, and the candidates before admitting. Verify brand from the page's manufacturer field, not from the URL prefix.
5. Add a candidate importer for `catalog-new-brand-candidates-v1.json`, with a dry run and a receipt. None exists yet.
6. Never fetch ModularGrid (Danny 2026-10-17). The in-repo router and the shared scrape-router both deny that host; `scripts/check_no_modulargrid.py` runs in CI.
7. Store receipts in the repo (hashes and metadata only, never page text). This matches the shared rule that repos hold row refs only.

## Paid scraping methods and proxies on the box (names only; no values printed)

| Method | Present | Notes |
|---|---|---|
| Firecrawl (`FIRECRAWL_API_KEY`, env and box secrets) | yes | Hobby plan, about 5,000 credits/mo. Router cap is 100/day and 1,000/mo. Enhanced proxy is included at 1 credit/page. Balance 1,767 at run time. |
| context.dev (`CONTEXT_DEV_API_KEY`, env and box secrets; `user-Context` MCP) | yes | Developer plan, 7,500/mo. Proxies and JS rendering are included. Overage is $2.20 per 1k, with auto top-up on. Router cap is 300/day and 7,000/mo. |
| Browserbase (Hermes `.env` has `BROWSERBASE_PROXIES` and `BROWSERBASE_ADVANCED_STEALTH` flags) | flags only | No Browserbase API key variable was found, so it is not usable. |
| Browser-use MCP, Chrome DevTools MCP | yes | Interactive fallback only. Not suitable for batch runs. |
| Crawl4AI | no | No venv has it installed (router MIGRATION.md blocker). |
| OpenRouter (`OPENROUTER_API_KEY`) | yes | LLM extraction only. Not used in batch 7. |
| Sandbox egress proxy (`SAND_EGRESS_TUNNEL_PROXY_ADDR`, `SAND_HTTP_PROXY_NAME`) | yes | Box network tunnel. It is not a residential or scraping proxy. |
| Tavily, Bright Data, Oxylabs, ScraperAPI, Zyte, Apify, Smartproxy/Decodo | no | Not in env or box secrets. |

**Best method for this batch**: scrape-router. It tries free HTTP first and escalates to context.dev (proxied) or Firecrawl with the enhanced proxy on a block. It is wired into both batch 7 scripts.

## In-repo router (batch 8)

OBSERVED in this change:

- `data/synth-catalog/catalog_scrape.py` tries a polite free fetch first (robots, per-host delay, disk cache under `data/synth-catalog/.cache/`, retries). It then calls context.dev (`POST https://api.context.dev/v1/web/scrape` and `/v1/web/search`) and Firecrawl v1 when `CONTEXT_DEV_API_KEY` or `FIRECRAWL_API_KEY` is set. Missing keys and `--max-paid-fetches 0` skip paid calls. Receipts keep url, method, status, sha256, and timestamp. Page text stays in the disk cache.
- `scripts/hermes_hp_enrich_firecrawl.py`, `scripts/hermes_hp_enrich_direct.py`, `scripts/enrich_module_power_depth_mg.py`, and the batch 7 scripts call that router. Paid fetches default to 0.
- `scripts/catalog_batch8.py` verifies the 179 candidate brands and searches the unresolved power/depth rows.
- `scripts/import_catalog_population.py` defaults to dry-run. `.github/workflows/db-load.yml` runs the full-population importer from Actions (`env` staging or prod, `mode` dry-run by default or apply) because this box cannot open port 5432. Apply mode runs `pg_dump` of the affected tables first and uploads that dump. The receipt is an artifact, and the job summary lists before/after row counts. The workflow does not echo the database URL. It refuses to load unless the database revision is this checkout's alembic head, so run `.github/workflows/db-migrate.yml` on this ref first (`20261017_module_verification` adds the verification columns).

Paid batch, on a machine that already has the two keys in the environment:

```bash
python scripts/catalog_batch8.py --max-paid-fetches 200
```

Free-only run on 2026-10-17 (`--max-paid-fetches 0`, `paid_attempts` 0). OBSERVED:

- 179 candidate pages returned HTTP 200. 178 `verified` (`span.vendor-name` matched the candidate brand). **Correction 2026-10-17:** these were ModularGrid pages and `verified` only meant the ModularGrid vendor name matched; the rows are now `unverified` with `needs_reverify`, and the batch 7/8 scripts and results were removed from the repo. 1 `corrected`: the URL-inferred brand Analogue Systems is Analogue Solutions HH88 (ModularGrid page; URL removed 2026-10-17). 0 flagged. 0 slug duplicates against the phase 2 and phase 3 catalogs.
- Batch 7's power/depth target list has 22 rows. 1 was already `found` (Intellijel μAtt). The other 21 were searched. 3 resolved from a single Perfect Circuit spec line, written to `overlays/module-power-depth-v6.json` and not applied by the importer (the importer still stops at v5): Befaco STmix 8 mA +12V / 10 mA −12V / 20 mm; Joranalogue Filter 8 75 / 75 mA / 43 mm; Joranalogue Generate 3 130 / 115 mA / 43 mm. 18 stay unresolved. DuckDuckGo lite answered HTTP 202 with no result links. `www.befaco.org`, `www.dreadbox-fx.com`, and `cwejman.net` did not return a readable robots.txt, so those free fetches were skipped. Several guessed official URLs returned HTTP 404 and were not sent to a paid backend.

## Batch 7 spend (OBSERVED from the router ledger)

68 router credits: 54 context.dev (40 for new-brand discovery searches, 14 for fetch fallbacks) and 14 Firecrawl (fetch fallbacks). Ledger day counters went from 41 to 95 for context.dev and from 4 to 18 for Firecrawl. Most fetches were free HTTP or cache. Marginal cost is $0 inside the prepaid plan quotas. The worst case at context.dev overage pricing is about $0.15. The cap was $10.

## Manufacturer crawl v2 (2026-10-27)

`scripts/catalog_maker_crawl.py` now uses the same in-repo router as every other catalog scraper (`catalog_scrape.py`). The external `scrape_router` package is no longer used. Free HTTP comes first (robots.txt, the deny list, a per-host delay of at least 2 s, and the disk cache), then context.dev, then Firecrawl with its managed proxy tier, all under one `--max-paid-fetches` cap and one ledger. The router gained a lock (the crawler shares one instance across worker threads), an `on_receipt` hook (the crawler books spend from it), `robots_info()` (sitemaps and crawl-delay), and escalation to the paid backends when a 200 response is a bot-check page.

- `data/synth-catalog/maker-sources.json`:
  - Curated homepages for brands the v1 crawl could not resolve, each with a check status. 39 `verified_free`, 46 `candidate` (the run must see the brand on the page first), 2 `robots_disallowed`, 2 `rejected` (domains now hold unrelated content).
  - 25 adapters for the top makers: Shopify, Squarespace or WooCommerce store feeds, or `listing` (index pages plus a product URL pattern; sitemap URLs are filtered, never crawled).
- `scripts/maker_adapters.py` enumerates products through the router. The crawler parses HP, power and depth deterministically from the feed text, or from the page when the feed has none. A labelled width ("Width 12HP") beats other mentions; two unlabelled widths count as ambiguous and go to the model on a paid run.
- The resolution order is: adapter, curated homepage, the v1 crawl's resolved homepage, then search.
- The page cap is `--max-pages` (default 250 per maker; v1 stopped at 80 model-picked pages plus 60 one-hop pages).
- Fixed in v2: the reseller exclusion now matches host labels. Its `x.com` entry used to drop any maker whose domain ends in x.com, including Metasonix and Qu-Bit.

`--dry-run` makes no paid fetch, search or model call and writes `receipts/maker-crawl-v2.dry-run.json`.

Dry run on 2026-10-27, 703 brands. OBSERVED:

- 3,213 candidate modules from 293 brands. v1 found 751 from 245. 1,462 candidates have +12 V power.
- By path: generic 2,644; Shopify 288; listing 175; Squarespace 56; WooCommerce 50.
- Top makers, v1 to v2: Make Noise 7 to 49, Intellijel 0 to 50, Noise Engineering 4 to 65, ALM 10 to 47, 2hp 0 to 26, Bastl 0 to 44, After Later 10 to 95, Mutable 0 to 30.
- Still 0 on free HTTP, so they need the paid tier: 4ms, Erica, Xaoc (script-rendered), and Befaco, Tiptop, Frap (no free response from this box).
- Generic-path candidates are regex-only in a dry run. The paid run confirms each one with the model, so the accepted count may be lower.
- 145 brands still need a search, and 37 curated candidates could not be confirmed over free HTTP.
- Projection for the paid run: 417 paid fetch URLs and 145 paid searches. That is 562 credits if context.dev answers, 1,124 in the worst case where every call also falls through to Firecrawl. About 3,530 model calls, about $0.63 at v1's measured cost per call. Paid overage if no included plan credits remain is at most $4.05.

Paid run, after approval:

```bash
python scripts/catalog_maker_crawl.py --max-paid-fetches 1200 --cap 10 --ctx-start <included context.dev credits left> --fc-start <included Firecrawl credits left>
```

### Paid run (T024), 2026-10-27, context.dev only. OBSERVED

Approved by Danny: `--max-paid-fetches 1200 --cap 10`, context.dev only (no Firecrawl key). It ran in three passes:

1. **`--no-model`, before the OpenRouter key arrived.** 1,200 paid attempts, but only 147 succeeded: the router gave paid calls the free-fetch 25 s timeout, and rendered scrapes need longer. 286 context.dev credits, which includes the 145 searches. Fixed: paid calls now get 120 s.
2. **With the model.** 1,200 paid attempts, 530 succeeded, 702 credits. Most of the failures are long-tail maker sites context.dev cannot reach either. Only about 9% of the 3,346 model calls returned usable JSON: `deepseek-v4.1-flash` now reasons by default, and the reasoning ran past `max_tokens` and cut off the answer. Fixed: model calls send `reasoning: {enabled: false}`.
3. **Model pass on cached pages, `--max-paid-fetches 0`.** No context.dev calls. 3,641 model calls, $0.41.

Result (`receipts/maker-crawl-v2.json`, rows in `hermes-research/maker-crawl-v2.json`):

- **3,429 accepted modules from 315 brands.** v1 found 751 from 245.
- With +12 V: 1,807. With −12 V: 1,800. With depth: 1,715.
- By path: generic 2,821 (model-confirmed under v1's verbatim rule); Shopify 291; listing 202; Squarespace 65; WooCommerce 50.
- **Spend:** context.dev 988 credits for the crawl, plus 6 for API checks; the balance went from 55,295 to 54,301. Firecrawl 0. OpenRouter $1.19. No overage, against a $10 cap.
- **Still empty:**
  - 4ms and Erica. The `render` flag was served the cached free shell; this is now fixed and needs a small paid render pass.
  - Frap, Tiptop and Pittsburgh. Their adapter patterns need checking against the rendered pages.
  - 79 brands with no search candidates and 40 with no model pick, plus 27 curated candidates still unconfirmed.

### Overlays from the v2 crawl (T025), 2026-10-27

Built with:

```bash
python scripts/build_maker_overlays.py --crawl maker-crawl-v2.json --additions-version 3 --power-version 11
```

The loader reads up to `catalog-additions-v3` and `module-power-depth-v11`.

The builder:

- **Drops non-modules.** It discards HP outside 1 to 42 (FR-007; the crawler now enforces the same bound) and store items named as pedals, upgrades, bare panels, PSUs or cases.
- **Cleans store-title boilerplate.** "Bastl CRUST Eurorack Module" becomes "CRUST".
- **Matches identities case-insensitively.** It reuses the stored spelling of catalog rows, HP overlays and the provenance manifest, so an addition never claims a slug under a different name.

Result: 2,721 new catalog rows from 290 brands (`access_basis = official_publication`) and 3,576 power/depth entries. 620 crawled modules matched existing rows.

Loader dry run against a migrated Postgres 15, compared with main:

| | main | this build |
|---|---|---|
| Catalog rows | 1,157 | 3,878 |
| Power targets | 848 | 3,601 |
| Unmatched HP | 60 | 34 |
| Unmatched power/depth | 67 | 41 |

All 17 conflicts are `verification_conflict`: the v2 crawl disagrees with a value a v1 overlay marked verified, so the loader flags the row instead of overwriting it.

Staging load, 2026-10-27: `db-load.yml` apply took staging from 1,336 to 4,019 catalog rows and from 1,302 to 3,988 modules, with 25 conflicts flagged.

### Rail-parser fix, 2026-10-27

Reviewing the 25 staging conflicts showed that the crawler misread some rail draws. Two causes:

- **Rail order.** The -12V pattern read the number before "-12V" first, so "+12V 140mA -12V 115mA" (Verbos) gave -12V = 140, and "+12V current 100mA -12V current 15mA" (Mutable docs) gave -12V = 100 with no +12V.
- **The model could overrule the parse.** A model value was kept when it appeared anywhere on the page, so Joranalogue Dim 2's "+12: 150 mA" lost to "delivers 500 mA at 12 V" from the lamp output.

`rails()` in `catalog_maker_crawl.py` now picks the style each page writes first (rail first, value first, signed values, or both rails then both values) and reads every rail in that style, with no fallback to another style. It also handles decimals, "ca.", "@", "|" and " - " separators, and a dropped "+" or "V". When the parse and the model disagree on a draw, neither value is stored.

The crawl was replayed from the cache with no paid fetches ($0.003 of model calls; `receipts/maker-crawl-v2-rail-fix-replay.json`), and `catalog-additions-v3` and `module-power-depth-v11` were rebuilt in place. Prod has never loaded them. 88 modules changed values, and 16 more modules gained a draw and a catalog row.

The loader never overwrites a stored value, so `provenance/maker-crawl-v2-rail-fix-v1.json` (from `scripts/build_rail_fix_manifest.py`) lists the 61 values staging may hold from the first v11, each with its misread value (`only_if_value`). On load the loader archives and clears a field only while the database still holds that exact value, and the rebuilt v11 refills it in the same run. Rows are not flagged `needs_reverify` (`flag_reverify: false`). A database that never loaded the first v11 is left alone.

Simulated against main's load on Postgres 15: 49 values were cleared and refilled, 12 were left because the database held a value from an earlier source, and a second run was a no-op.

The conflicts left are real disagreements for review. Some are two products under one name: ALM MCO legacy vs current, Atonal SEE V1 vs V2, Sovage CHICANE Eurorack vs 1U, Wackylab Lords of Chaos 4 HP vs 10 HP, and TLM "ST MODULAR". The others are older stored values that differ from the maker page.

### False conflicts, 2026-10-27

Of the 19 conflicts left on staging after the rail fix, 14 came from the loader, not the data:

- **Decimals.** `modules.power_*` are INTEGER columns, so a published 3.5 mA is stored as 4, and every later load compared 3.5 with 4 and flagged the row (Ghost in Translation, Ginko, shkrjn, TubeOhm, Delptronics, Archaea, gregsbrain, Hexdevices, Rare Waves). Values are now compared as the column stores them, rounding half away from zero; depth keeps its decimals.
- **Unverified sources.** An unverified seed row (Make Noise Maths) raised a conflict against the verified module on every rerun. Only a source that claims verification can conflict now.

On a replica of staging this leaves 5 conflicts, each a real choice: ALM MCO (legacy vs current), Atonal SEE (V1 vs V2), Sovage CHICANE (Eurorack depth 12 mm vs the 1U page's 24), TLM "ST MODULAR" (a product-line prefix, not a product), and Wackylab Lords of Chaos (4 HP vs 10 HP).

### Conflict review decisions, 2026-10-27

The last 5 staging conflicts were pages for two different products filed under one name. `overlays/maker-review-v1.json` re-keys each overlay entry or catalog row by brand, name and source page (`url_prefix`), and adds catalog rows for the products it names. `provenance/maker-review-v1.json` clears the stored values that belong to the other product, using `only_if_value`, so the right page refills them in the same run.

- **ALM MCO:** now the current MCO (alm046, 70/30 mA). The legacy page becomes "MCO (Legacy)" (40/15 mA).
- **Atonal SEE:** now the current SEE (65/8/0 mA, 41 mm). The V1 page becomes "SEE (V1)" (27/8/0 mA, 26 mm).
- **Sovage CHICANE:** depth 12 mm and catalog HP 4 from the Eurorack page. The 1U page is `not_module`: its catalog addition and power entry are dropped, so the 14 HP tile never becomes a Eurorack row. `modules.hp` still holds the 1U tile's 14 and cannot be cleared, so it is flagged and placement waits for re-verification (FR-035).
- **TLM "ST MODULAR":** this is TLM's product-line prefix, not a product. The CV PAN page becomes "CV PAN" (35/21 mA). The Langer Arm expansion (84 HP) is `not_module` and is dropped. The ST MODULAR row's values are cleared and the row is flagged.
- **Wackylab Lords of Chaos:** the stored row is the 10 HP tube version (220/15 mA). The 4 HP diode page becomes "Lords Of Chaos 4HP" (10/10 mA).

Simulated on a fresh database and on a staging replica. Fresh: the current SEE and MCO and the legacy rows are all present, and nothing named CHICANE 1U, ST MODULAR or Langer Arm. Replica: 12 values archived (10 cleared, 2 HP flags), 4 catalog rows added, no conflicts left, and a second run was a no-op.

### T026 adapter fixes, 2026-10-27

All five T026 makers yielded no modules in the paid run. Free probes found:

- **4ms:** `modules.php` lists all 41 products as relative `p.php?p=N` links over free HTTP. The forced paid render was unnecessary, so it is removed.
- **Pittsburgh:** the Squarespace store feed holds only merch, cases and pages without specs. Each module has a root info page with Size, Depth and Power Usage. The adapter is now a sitemap-filtered listing that excludes systems, cases and keyboards.
- **Erica:** products live at the root as `/<name>-<id>/` and their pages carry full specs over free HTTP. The series pages build their product grid with script, so only those index pages need a paid render (`render_index`). robots.txt disallows `/graphql/` and `/rest/`, and neither is used.
- **Tiptop:** every path, robots.txt included, answers `202` with a SiteGround CAPTCHA (`sg-captcha: challenge`). The new `challenged` status marks it as never fetched and never routed through a paid proxy to get past the challenge.
- **Frap:** the host resolves, but connections time out from the crawl host.

The parser also misread pages where the spec window began at a nav-menu "Power" far above the specs (4ms). When that window gives no draws, HP or depth, `deterministic()` now reads them around the page's first mA value. This only adds values where there were none.

A `--brands` run now writes its own receipt (`--tag`) and, when real, replaces only those brands in `maker-crawl-v2.json` instead of overwriting it.

Free dry run (`receipts/maker-crawl-v2-t026.dry-run.json`): 4ms 44 modules (36 with +12V), Pittsburgh 56 (38), Erica 9 from the site-wide product widget, Frap 0, Tiptop not fetched.

### T026 paid pass, 2026-10-27, context.dev only

Approved cap: 30 paid fetches and $3. Firecrawl was disabled by leaving its key unset for the run. Runs, each with its own receipt:

- `--tag t026`: 4ms, Pittsburgh, Erica and Frap. 2 credits.
- `--tag t026-erica`: Erica again, after a fix. Its `exclude` pattern had filtered out the series links it should follow. 8 credits.
- `--tag t026-erica-replay`: a replay from cache, no spend. It applies the signed-pair fix: Hexinverter writes "+49mA, -39mA @ 12V".

| Maker | Modules | With +12V | Notes |
|---|---|---|---|
| 4ms | 44 | 36 | free HTTP; the VCA Matrix lists draws per jumper setting and its +5V read is the internal-5V mode's +12V |
| Pittsburgh | 56 | 38 | free HTTP, root info pages |
| Erica | 46 | 19 | 7 index pages rendered by context.dev; product pages fetched free |
| Frap | 0 | 0 | 1 paid fetch: context.dev returns rendered HTML for Squarespace's `?format=json`, so the JSON adapter reads nothing |
| Tiptop | not fetched | | CAPTCHA (`challenged`) |

Spend: 10 context.dev credits (ledger 1,106 to 1,116), Firecrawl 0, OpenRouter $0.0003, no overage. A rescan of all 3,322 cached crawl pages found that the signed-pair fix changes only the two Erica Hexinverter pages.
