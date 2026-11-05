# Intent

## Problem

A Module that sits in a Case can supply power. Owner decision 15 ([OWNER_DECISIONS_2026-11-04.md](../docs/evidence/OWNER_DECISIONS_2026-11-04.md), #278) says that output is never added to a Rig's power budget and the builder warns that it isn't counted. Nothing warns today.

## Proposed outcome

- `racks/validation.py` adds one `IN_RACK_SUPPLY_NOT_COUNTED` warning per Rig, naming each placed Module whose `module_type` is `SYSTEM`.
- The rack response and `GET /api/canon/rigs/{id}` carry it on every read, because the builder loads the Rig through the canon route.
- Rack Builder shows it beside the power meters.
- No rail capacity changes. No supply is credited.

## Affected users / systems

Rack validation, the rack and canon Rig read responses, and Rack Builder's placement step. No Rig has a `SYSTEM` Module until #286 lands and its rows are materialized.

## Constraints / non-goals

No capacity is invented. The warning stays a warning, never a hard fail. This doesn't change how a Module's draw is counted.

## Open questions

Nothing stored for a placed Module tells a power supply from a fan, so this warns on every `SYSTEM` Module in wording that's true of both. A later catalog field could narrow it. The owner decides whether that's worth adding.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `module_catalog` has no tags column, and a materialized `modules` row keeps `tags: []` | `OBSERVED` | `backend/modules/catalog.py`, `backend/modules/catalog_routes.py` |
| The overlay's `power` and `fan` tags exist only in overlay files | `OBSERVED` | `overlays/module-catalog-category-v4.json` on #286 |
| The builder read no `validation_warnings` before this | `OBSERVED` | Playwright test failed on `main`'s frontend |
| A filled category doesn't reach `modules.module_type` on a loaded database, so this warning can miss such a row until decision 51 is done | `INFERRED` | `CATALOG_TAXONOMY_DECISIONS_2026-11-04.md` on #286 |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-11-04
