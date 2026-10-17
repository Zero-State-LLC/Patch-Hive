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
6. Respect rate limits: ModularGrid at 1 req/s (router default). Add `domains.modulargrid.net.min_interval_s: 2` for bulk runs.
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

## Batch 7 spend (OBSERVED from the router ledger)

68 router credits: 54 context.dev (40 for new-brand discovery searches, 14 for fetch fallbacks) and 14 Firecrawl (fetch fallbacks). Ledger day counters went from 41 to 95 for context.dev and from 4 to 18 for Firecrawl. Most fetches were free HTTP or cache. Marginal cost is $0 inside the prepaid plan quotas. The worst case at context.dev overage pricing is about $0.15. The cap was $10.
