# Intent

## Problem

The loader only fills nulls, so a wrong value can never be fixed. Sovage CHICANE's `modules` row holds the 1U tile's 14 HP, and its verification URL points at the 1U page, while the Eurorack page says 4 HP. The row is flagged, so FR-035 blocks placing it.

## Proposed outcome

- A `correct` provenance action (spec 003 D4, FR-038). Each entry needs the field, `only_if_value`, `value` and an https `evidence_url`; HP must be 1–42.
- The loader archives the old value (as for every action), then writes the new value only where the archived copy still equals the stored value. A value changed since review is neither archived nor overwritten. Each row is processed once per batch.
- `hp_needs_reverify` lifts when an `hp` correction exists.
- `provenance/maker-corrections-v1.json`: CHICANE `hp` 14 → 4, and `verification_source_url` → the Eurorack page.

## Affected users / systems

`modules` (one row on staging and prod), the loader, the FR-035 guard.

## Constraints / non-goals

Values only from a cited maker page. No new flag. Dry run, then apply with the reviewed `plan_hash`.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The Eurorack page gives 4 HP; the module's power and depth already match it | `OBSERVED` | `maker-crawl-v2.json`, prod query |
| Postgres: the correction writes once, archives the old values, and a rerun changes nothing | `OBSERVED` | `test_a_reviewed_correction_fixes_a_stored_value_once` |
| A correction lifts the placement block | `OBSERVED` | `test_a_reviewed_hp_correction_lifts_the_placement_block` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
