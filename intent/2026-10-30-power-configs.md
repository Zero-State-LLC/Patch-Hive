# Intent

## Problem

Some modules draw different current depending on a jumper (4ms modules with a +5V-source jumper, Velectronic A-Envelope). The catalog keeps one draw per rail, so those rails are stored as unknown (FR-022) and a rack with such a module can never confirm its budget. Spec 003 D8 decided to store one +12 V / −12 V / +5 V set per setting (`power_configs`); T035 read the settings from the maker pages into `data/synth-catalog/receipts/t035-jumper-power.json`. T034 builds the storage, the loader action and the setting picker.

## Proposed outcome

- Migration `20261030_power_configs`: a `power_configs` table keyed to `modules` (the table rack budgets read), one row per setting with label, three nullable rails, `unit_stated`, per-rail status and quote, source URL, the page's power block verbatim, `is_recommended`, and timestamps; `rack_modules.power_config_id` (nullable).
- Loader action in `data/synth-catalog/population.py`: insert each clean setting of a jumper-dependent page from the T035 receipt, matched by brand and source URL; fill-only, idempotent, with plan counts and receipt stats.
- Rack budget: a placement can name a setting; the budget uses its draws. With none chosen, the module's own columns count and a jumper rail stays unknown (`POWER_RAIL_INCOMPLETE`). API exposes the settings and accepts the choice; the rack builder gets a select.

Out of scope: the receipt's open questions (Otool's unlabelled alternatives, the Spectral Multiband Resonator's unlabelled base setting, the VCA Matrix value with no unit) load nothing until the owner answers; changing the single draw columns (D8 says they stay unknown, and they hold only rails every setting shares); staging and prod loads.

## Affected users / systems

Catalog loader and db-load workflow (new insert kind), `modules` and `racks` APIs, rack validation and the dual gate, the rack builder page.

## Constraints / non-goals

`NOT_COMPUTABLE` over invented facts: no neutral labels, no default setting, no unit assumed, no worst-case merge. A rail the page gives no number for stays NULL. No network fetch; the receipt is the source. Additive migration only.

## Open questions

The receipt's `for_t034` questions for the owner (listed above). Whether a "not used" rail with no number should count as 0 in a chosen setting's budget (kept NULL, as the single columns store it).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Rack budgets read power from `modules`, not `module_catalog` | `OBSERVED` | `backend/racks/validation.py`; `module_catalog` has no power columns |
| Every receipt page URL equals its module's `source_reference` | `OBSERVED` | replica load, 0 unmatched |
| The single columns of the loaded modules hold only values every stated setting shares | `OBSERVED` | loader check on the replica: 0 `single_draw_differs_from_setting` |

## Author / date

- Author: Claude
- Date: 2026-10-30
