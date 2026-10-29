# Intent

## Problem

Tombstoned modules (#116, #120) are hidden from browse and can't be materialized, but a rack that already holds one shows nothing: the rack response only carried warnings from the last write, and Rack Builder showed none.

## Proposed outcome

- `racks/validation.py`:
  - `tombstone_note` gives a placed tombstoned module's reason (from its catalog row) and up to three live modules with the same name under other brands.
  - `tombstone_warning` builds a `MODULE_TOMBSTONED` warning from it.
- `build_rack_response` adds that warning on every rack response, reads included, and puts `status`, `tombstone_reason` and `alternatives` on each placed module.
- Rack Builder lists retired placements with the reason and the alternatives.
- The module stays placed: a warning, never an error or removal.

## Affected users / systems

- Rack API responses and Rack Builder. No prod rack holds a tombstoned module today.

## Constraints / non-goals

No automatic swap. No change for live modules (one status check, no extra query).

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| A read of a rack with a tombstoned module returns the warning, reason and alternatives | `OBSERVED` | `tests/test_rack_catalog_compatibility.py` |
| Live racks are unchanged | `OBSERVED` | same tests; backend suite 1,025 passed |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
