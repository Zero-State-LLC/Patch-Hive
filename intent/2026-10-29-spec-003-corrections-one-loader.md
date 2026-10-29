# Intent

## Problem

Spec 003 did not record what the 2026-10-28 catalog work decided (tombstones, the crawl-time guard). It also forbade ever overwriting an admitted HP, which leaves Sovage CHICANE stuck at the 1U tile's 14 HP. Two unused seed scripts still overwrite catalog values and invent defaults.

## Proposed outcome

- **spec.md:**
  - owner decisions D3–D6;
  - a row lifecycle state machine (LIVE, FLAGGED, TOMBSTONED) with transitions and illegal transitions;
  - FR-036 (tombstones), FR-037 (shared homepages) and FR-038 (reviewed corrections);
  - the HP illegal transition now allows a reviewed correction.
- **research.md:** R1–R6, evidence and recommendations for each open decision, with costs.
- **plan.md:** a scoped addendum for T032–T033. T002 stays open until T001.
- **tasks.md:** T032 (done here), T033 (corrections, next PR), T034 (power configs, after a schema decision).
- **Deleted:** `scripts/seed_catalog_from_synth.py`, `backend/scripts/seed_catalog_from_synth.py`, `backend/tests/unit/test_seeder_catalog.py`.

## Affected users / systems

Spec 003 docs; nothing runtime (no workflow, script or import used the deleted files).

## Constraints / non-goals

No paid runs are approved here (R3, R4 wait on caps). T034 waits on a schema decision.

## Open questions

Caps for R3 and R4; the `power_configs` schema (R5).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Nothing calls the seed scripts | `OBSERVED` | repo grep |
| Backend suite passes without them | `OBSERVED` | 1,025 passed |
| Spec DAG valid | `OBSERVED` | `check_spec_dag --strict`, 0 errors |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
