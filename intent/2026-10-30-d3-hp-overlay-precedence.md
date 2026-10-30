# Intent

## Problem

The catalog loader (`data/synth-catalog/population.py`) reads HP overlays in sorted file order and only fills an empty HP. The unsourced legacy `overlays/module-catalog-hp-v1.json` (grandfathered in `UNSOURCED_HP_OVERLAYS`) therefore fills before the maker-cited `module-catalog-hp-v2.json`, and wherever both carry a module the v1 value wins. Found during the 2026-10-30 open-decisions research (`docs/evidence/OPEN_DECISIONS_2026-10-30.md`, PR #148, "A bug found during the research").

Overlapping slugs (v1 / v2): `acid-rain-technology-junction` 6 / 4, `alm-busy-circuits-akemie-s-castle` 18 / 38, `doepfer-a-101-3` 10 / 30, `doepfer-a-137-2` 10 / 14, `doepfer-a-101-9` 8 / 8.

## Proposed outcome

When planning an HP fill, a maker-cited entry takes precedence over an unsourced legacy entry for the same module: the legacy entry is skipped wherever any sourced overlay carries an HP for that slug. Fill-null semantics are unchanged (a stored HP is never overwritten; a stored wrong value is fixed only by a reviewed `correct` entry, D4). Plan order stays deterministic: overlays are still read in sorted order, so the plan and its `plan_hash` are unchanged for any database where these slugs already hold an HP.

Out of scope: `correct` provenance entries for values already stored on staging and prod (follow-up under T039); the legacy single-overlay script `scripts/apply_module_catalog_hp_overlay.py`.

## Affected users / systems

Catalog population (`db-load` dry run and apply), `module_catalog.hp` on fresh databases, rack placement that reads HP.

## Constraints / non-goals

Fill-null only. No overwrite of stored values. Maker pages are the only HP source (FR-024, FR-027). Hand checks use a plain free HTTP GET of the cited maker page; ModularGrid is never fetched.

## Open questions

- Staging and prod already hold the v1 values for slugs where v1 filled first. Which need a reviewed `correct` entry (T039) is decided in the follow-up, not here.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Doepfer A-101-3 is 30 HP | `OBSERVED` | https://doepfer.de/A1013.htm, "Breite/Width: 30TE / 30HP", fetched 2026-10-29 |
| Doepfer A-137-2 is 14 HP | `OBSERVED` | https://doepfer.de/a1372.htm, "Breite/Width: 14TE / 14HP", fetched 2026-10-29 |
| Doepfer A-101-9 is 8 HP | `OBSERVED` | https://doepfer.de/A1019.htm, "Breite/Width: 8 TE / 8 HP", fetched 2026-10-29 |
| Acid Rain Junction is 4 HP | `OBSERVED` | https://acidraintechnology.com/products/junction, specifications "4hp 25mm deep", fetched 2026-10-29 |
| ALM Akemie's Castle is 38 HP | `OBSERVED` | https://busycircuits.com/pages/alm011, "Size: 38HP Depth: 32mm", fetched 2026-10-29 |
| A fresh load on this branch writes the maker values and nothing stored changes | `OBSERVED` | throwaway Postgres simulation, see PR body |
| Staging and prod hold the v1 values for the overlapping slugs | `INFERRED` | v1 loaded first under fill-null; stored databases not queried |

## Author / date

- Author: Claude Code (for Daniel Meyer)
- Date: 2026-10-30
