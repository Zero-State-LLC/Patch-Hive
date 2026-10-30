# Intent

## Problem

Some modules draw different currents depending on a jumper (usually whether +5V comes from the bus or is made on board from +12V). The crawl kept one value per page, so these rails stay unknown in the catalog (FR-022). D8 chose a `power_configs` column (T034), but there is nothing to load until the per-setting draws are read from the maker pages (spec 003 T035).

## Proposed outcome

- A free re-fetch (plain HTTP GET, robots.txt checked per host, 2 s apart or the host's Crawl-delay) of the jumper-candidate pages named in committed data: every 4ms Company row in `hermes-research/maker-crawl-v2.json` except the Row Power rows, the 2 Dave Jones Design rows and Velectronic A-Envelope.
- `data/synth-catalog/receipts/t035-jumper-power.json`: per page the url, fetch time, HTTP status, content sha256, the verbatim power block and each setting's +12V/−12V/+5V draws, each value with the quote it came from. A rail the page does not give for a setting is recorded as not stated.
- The scrape ledger counts the 42 free fetches.
- A test that checks the receipt's shape and that every value has a verbatim quote from the page's power block.
- Out of scope: T034 (migration, loader action, setting picker). No overlay, manifest or database value changes.

## Affected users / systems

Catalog data receipts only. T034 will consume the receipt later.

## Constraints / non-goals

Free fetch only (Decision 10): no context.dev, no Firecrawl, no paid cap. No ModularGrid. Stop for a host on any block or challenge; never route around it. Raw HTML stays out of git. `NOT_COMPUTABLE` over invented values: no rail is filled from another source or by inference.

## Open questions

- Otool's two power alternatives are not tied to a jumper position on the page. T034 needs neutral labels or an owner mapping.
- 4ms VCA Matrix states "80 max" with no unit for one +12V value. T034 decides whether to load it.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The committed crawl holds 44 4ms rows, 5 of them Row Power, and no 4ms row is marked retired | `OBSERVED` | `maker-crawl-v2.json`, `overlays/catalog-retirements-v1.json` |
| All 42 pages returned HTTP 200 to a plain GET with no block or challenge | `OBSERVED` | fetch run 2026-10-30, receipt `counts` |
| robots.txt on all three hosts allows the product pages | `OBSERVED` | receipt `robots` |
| 11 pages state jumper-dependent draws | `OBSERVED` | receipt `pages[].settings` |
| The earlier "42 live 4ms modules" estimate counted something other than committed rows | `INFERRED` | committed data gives 39 4ms pages |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-30
