# Intent

## Problem

From the 2026-10-29 gap analysis (P1):
- **Unsourced HP.** The loader filled null HP from any HP overlay entry, with no check of its source. HP decides placement, so only a maker page may supply it (spec 003 FR-024, FR-027). `module-catalog-hp-v1` (221 entries, no `source_url`; 186 tagged `maker_or_retail`) was loaded this way.
- **Decision providers.** They were enabled by flags alone. Nothing in the backend refused them in production; only the Worker's env filter kept them out.

## Proposed outcome

- **HP gate.** `_schedule_hp` refuses an entry without `source_class = maker` and an https `source_url` (conflict `hp_overlay_unsourced`). `module-catalog-hp-v1.json` is named as grandfathered, so the database and the reviewed plan don't change. What to do with its values is a separate owner decision.
- **Provider guard.** `core.startup_policy.validate_decision_startup_policy` refuses to start in production with `enable_decision_intelligence`, `enable_clef_provider` or a `decision_provider` other than `disabled`. Staging is unaffected.

Not here: signing evaluation and enablement receipts, and routing the Jev path through the guarded resolution machine (gap analysis P1 13; needs a key-management decision).

## Affected users / systems

Catalog loader HP overlays; API startup in production.

## Constraints / non-goals

No change to loaded data. Production currently sets none of these flags (`edge/api/wrangler.jsonc`).

## Open questions

- Keep, flag or retire the 221 unsourced v1 HP values.
- A signing key for 007/008 receipts.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| v1 entries have no source_url; v2 all cite maker pages | `OBSERVED` | overlay files |
| Gates behave as stated | `OBSERVED` | `tests/unit/test_startup_and_hp_gates.py` |
| Production sets no decision flags | `OBSERVED` | `edge/api/wrangler.jsonc` |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
