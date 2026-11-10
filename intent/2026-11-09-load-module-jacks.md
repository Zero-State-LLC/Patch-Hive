# Intent

## Problem

Almost no catalog row has `io_ports`, so Patch Books print role names. `scripts/read_module_jacks.py` has proposed complete jack lists for 230 Modules, but the loader has no way to write them.

## Proposed outcome

- `overlays/module-jacks-v1.json` holds the 230 lists: each jack's name and type, and the maker document read.
- The loader fills `modules.io_ports` from it, only where the list is empty.

Out of scope: applying the load, which needs the owner's yes on the plan and inputs hashes for each database.

## Affected users / systems

The catalog loader and, once a load is applied, patch generation and Patch Books for those Modules: cables resolve to declared jacks, and Rig port coverage counts them.

## Constraints / non-goals

- A declared list is never overwritten. A different stored list is a conflict and stays as it is.
- Only complete lists are loaded, because the engine sends a cable to the first free jack of the right type.
- Model output stays evidence until it passes the deterministic gate and an operator admits the committed overlay against its hashes (spec 003 FR-032).
- Quotes from makers' documents stay in the private proposal, not the public repo.

## Open questions

Whether to admit the lists both readings agree on when only one reading calls them complete. They are not in this overlay.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The overlay holds 230 lists, 1,638 jacks, 66 makers | `OBSERVED` | `overlays/module-jacks-v1.json` |
| 23 of 25 accepted lists checked by hand were right, and the 2 others are excluded by a later check | `OBSERVED` | `docs/evidence/CATALOG_MODULE_JACKS_2026-11-09.md` |
| A rollback restores an empty list | `OBSERVED` | `backend/tests/test_module_jacks_load.py` against Postgres |
| A list matches the physical panel | `NOT_COMPUTABLE` | Lists were checked against documents only |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-09
