# Catalog paid render and bot checks, 2026-11-09

The owner approved up to 500 context.dev credits to render 21 makers whose home pages had come back almost empty and looked script-built. Eight of those sites were serving a bot check, and the render went past it. Decision 3 forbids that. This records what happened and what was done about it.

## What happened

The page is titled "One moment, please..." and arrives with status 200. The router's `CHALLENGE` pattern didn't include that title, so it read as a thin page and not as a refusal. The agent running the crawl called the thin pages script-built without reading them, and told the owner that none of the 21 sites had refused.

The run made 261 paid calls and used 254 credits. It cached 250 pages, and 226 of them came from these hosts:

| Maker | Host | Pages |
|---|---|---:|
| 333modules | `333modules.com` | 66 |
| Encore Electronics | `encoreelectronics.com` | 53 |
| ADDAC System | `addacsystem.com` | 39 |
| Seaside Modular | `seaside.digital` | 22 |
| Antumbra | `antumbra.eu` | 18 |
| MH Eurorack | `mheurorack.com` | 12 |
| Iron Ether | `ironether.com` | 8 |
| omsonic | `omsonic.co.uk` | 8 |

The other 24 pages came from sites that serve real pages to a plain request.

It came to light when 316 of the 363 files linked from the rendered pages came back as a web page and not as a file. A plain request to each host then returned the bot check.

## What was done

- The run was stopped by hand at 254 credits. By then its second pass was spending on API and duplicate addresses.
- The 226 pages were taken out of the crawl data and the indexes built from it. They were never in the repository, and they were permanently deleted on the owner's word on 2026-11-09. No manuals or pictures from these hosts were saved.
- The approval is closed, so its unused credits can't be spent.
- `CHALLENGE` now includes this title, so these hosts are refused on a free or a paid fetch.

## Still open

- These eight makers need their own permission before anything of theirs is read.

The spend and every paid address are in [`receipts/maker-render-2026-11.json`](../../data/synth-catalog/receipts/maker-render-2026-11.json).
