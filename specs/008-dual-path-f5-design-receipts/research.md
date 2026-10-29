# Research: 008-dual-path-f5-design-receipts

Decision research for the open cutover and receipt decisions (2026-10-29). Each item gives the evidence, the options and the recommendation. Labels: `[OBSERVED: <source>]` or `[INFERRED]`. Effort: S (under a day), M (one to three days), L (more).

Already fixed and reconciled in [spec.md](spec.md): the demo seeder refuses production, and refuses a hosted database unless `ENVIRONMENT=staging` with its own passwords (#129) [OBSERVED: scripts/seed_golden_demo.py].

## R1. Pinning trusts a forgeable 007 receipt (FR-005)

**Evidence:** `pin_readiness_docs` and the `operator_pin` guard call `verify_enablement_receipt`, which recomputes an unkeyed SHA over the receipt's own content. A forged mapping passes [OBSERVED: backend/core/ops/f5_cutover.py, backend/intelligence/evaluation_enablement.py; scratch run 2026-10-29]. The walkthrough receipt and `ReadinessPin` use the same unkeyed `record_sha256` [OBSERVED: f5_cutover.py `_Sealed`]. `pinned_by` is free text [OBSERVED: f5_cutover.py].

**Recommendation:** use the 007 verifier once it checks an Ed25519 signature and replays the chain ([007 research R1](../007-evaluation-staging-enablement/research.md)). Sign the `ReadinessPin` with the same approver key, so `pinned_by` is a key id. Effort S after 007 T081.

## R2. The walkthrough accepts any non-production environment

**Evidence**

- `flags_test_mode_failures` rejects only `production` and `prod`. `development`, `test`, a typo or an empty string pass [OBSERVED: backend/core/ops/f5_cutover.py].
- `verify_server_flags` and `run_staging_walkthrough` take `expected_environment: str | None = None`; `None` skips the check [OBSERVED: backend/core/ops/design_walkthrough.py].
- The CLI defaults `--environment staging` but lets the operator pass any value [OBSERVED: scripts/staging/design_engine_walkthrough.py].
- SC-001 asks for a staging receipt [OBSERVED: spec.md].

**Options:** (1) keep the denylist; (2) allowlist: the server must report exactly `staging`, and `expected_environment` becomes a required `Literal["staging"]`.

**Recommendation:** option 2. A beta claim rests on a staging run, so anything else should fail with `SERVER_ENVIRONMENT_NOT_STAGING`. In-process tests pass `staging` explicitly. Effort S.

## R3. Rollback (spec "Rollback", `[INFERRED]`)

**Evidence:** `OPERATOR_NOTES.md` T010 records that no route was added or changed: the canon list alias predates this feature, and the cutover audit compares the legacy list route with the canon alias [OBSERVED: OPERATOR_NOTES.md, backend/core/ops/f5_cutover.py `LEGACY_LIST_ROUTE`].

**Recommendation:** the rollback claim holds. Mark it RESOLVED. No task.
