# 008 Tasks — Dual-Path F5 Cutover & Design Engine Staging Receipts

## Upstream
- Depends on Spec 007 (evaluation corpus frozen, thresholds operator-approved, staging enablement receipt pinned).
- Depends on existing dual-path design (F0–F4 complete; F5 FE inventory list cutover planned).
- Depends on Design Engine foundation and staging enablement docs already on main.
- Constitution and Spec 005 authority boundaries unchanged.

## State machine (Cutover & Receipt)
States: INVENTORY_LEGACY → F5_ALIAS_LIVE → FE_CUTOVER → WALKTHROUGH_PENDING → RECEIPT_CAPTURED → BETA_ELIGIBLE

| From | Event | Guard | To |
|------|-------|-------|----|
| INVENTORY_LEGACY | expose_canon_alias | F2/F4 aliases already present | F5_ALIAS_LIVE |
| F5_ALIAS_LIVE | switch_fe_list | no dual-write regression | FE_CUTOVER |
| FE_CUTOVER | run_walkthrough | Design Engine flags on in test mode | WALKTHROUGH_PENDING |
| WALKTHROUGH_PENDING | capture_receipt | seed auth aligned + health ok | RECEIPT_CAPTURED |
| RECEIPT_CAPTURED | operator_pin | SHA-linked evidence | BETA_ELIGIBLE |

No path reaches BETA_ELIGIBLE without the walkthrough receipt. Production payments remain disabled.

## Tasks (topological order)

Status reflects `main` at e0fb6a1 (see `OPERATOR_NOTES.md`). Each task that pairs repository code
with an operator action is split: sub-task `a` is the code, sub-task `b` is the operator action. A
parent is done only when both are. `scripts/check_spec_dag.py` checks this file.

- [x] T001 Create feature tree `specs/008-dual-path-f5-design-receipts/` and add index line to `specs/README.md`.
  - depends_on: []

- [x] T010 Expose canonical inventory list alias for the FE cutover path.
  - depends_on: [T001]
  - acceptance: alias returns the same authoritative set as the legacy path; no new write surface.

- [x] T020 Switch frontend inventory list to the canonical alias.
  - depends_on: [T010]
  - acceptance: no dual-write regression; existing confirmation and generate gates unchanged.

- [ ] T030 Align demo authentication with seed data on the staging host.
  - depends_on: [T001]
  - acceptance: seeded operator can complete a full Design Engine flow without manual credential patching.
  - [x] T030a Make `scripts/seed_golden_demo.py` the single source of demo credentials; add read-only `check_seed_auth` (code).
    - depends_on: [T001]
  - [ ] T030b Verify seeded auth on the staging host (operator).
    - depends_on: [T030a]

- [ ] T040 Execute Design Engine walkthrough with flags enabled in test mode and capture the receipt.
  - depends_on: [T020, T030]
  - acceptance: debit → fulfillment → download pack succeeds under test payments; receipt includes SHA, flags, and outcome.
  - [x] T040a Implement `scripts/staging/design_engine_walkthrough.py` and receipt capture; pass in-process (code).
    - depends_on: [T020, T030a]
  - [ ] T040b Run the walkthrough against staging and capture the receipt (operator).
    - depends_on: [T030b, T040a]

- [ ] T050 Pin readiness docs and DOMAIN_CUTOVER_CHECKLIST to the walkthrough SHA.
  - depends_on: [T040]
  - acceptance: matrix and checklist reference the exact source SHA; no unresolved P0 integrity regressions.
  - [x] T050a Implement `pin_readiness_docs`; add Spec 008 sections with `PENDING_OPERATOR_WALKTHROUGH` placeholders (code).
    - depends_on: [T040a]
  - [ ] T050b Replace the placeholders with receipt values and pin (operator).
    - depends_on: [T040b, T050a, 007:T060b]

- [x] T060 Integration tests for the cutover state machine and receipt gate.
  - depends_on: [T020, T050a]
  - acceptance: no path reaches BETA_ELIGIBLE without RECEIPT_CAPTURED; fail-closed if seed auth or health checks fail.
