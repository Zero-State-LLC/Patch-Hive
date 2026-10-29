# Research: 007-evaluation-staging-enablement

Decision research for the open enablement decisions (2026-10-29). Each item gives the evidence, the options and the recommendation. Labels follow the spec: `[OBSERVED: <source>]` or `[INFERRED]`. Effort: S (under a day), M (one to three days), L (more).

## R1. Receipts are self-consistent only (FR-006; 006 `gates_pass`; 008 FR-005)

**Evidence**

- `verify_enablement_receipt` checks the schema id and a 64-hex `receipt_sha256`, then recomputes an unkeyed SHA-256 over the receipt's own content [OBSERVED: backend/intelligence/evaluation_enablement.py, backend/intelligence/clef_evaluation.py `verify_pinned_receipt`]. The brief named `core/ops/evaluation_enablement.py`; the module is under `backend/intelligence/`.
- A mapping is not validated against `EvaluationEnablementReceipt`. A dict with only `schema_version`, `approved_by` and a matching SHA passes [OBSERVED: scratch run 2026-10-29, `verify_enablement_receipt(forged) == True`].
- Every chain record (`_Record.intact`) uses the same unkeyed SHA, so the whole chain can be rebuilt by anyone who edits a field [OBSERVED: evaluation_enablement.py `_Record`].
- `OperatorApproval.approved_by` is free text with `min_length=1` [OBSERVED: evaluation_enablement.py].
- The 006 `gates_pass` guard accepts any 64-hex string as the evaluation receipt SHA. It never sees the receipt [OBSERVED: backend/core/ops/edge_readiness.py `_guard_gates_pass`; scratch run: `"0"*64` passes].
- 008 `pin_readiness_docs` and its `operator_pin` guard call the same `verify_enablement_receipt` [OBSERVED: backend/core/ops/f5_cutover.py].
- No signing library is installed. `PyJWT` is pinned; `cryptography` is not in the backend venv [OBSERVED: backend/pyproject.toml, venv import 2026-10-29].

**Options**

1. **HMAC with a server key.** Cheap. But the verifier holds the signing key. Any place that verifies (CI, staging API, an operator laptop) can also forge. It does not say who approved.
2. **Asymmetric signature (Ed25519).** The operator signs `receipt_sha256` with a private key that never leaves their machine. Public keys sit in a committed allowlist, changed only by reviewed PR. Anyone can verify; only the key holder can sign. `approved_by` becomes a key id.
3. **Replay via `enablement_machine` from the chain artifacts.** Proves the chain is consistent and that no step was skipped. It does not prove authorship: the artifacts use the same unkeyed SHA.
4. **Bind to an immutable store.** A git commit SHA on protected `main` proves the receipt was reviewed and merged, not who approved it. An R2 ETag is a content hash (MD5 for single-part uploads), not a signature; R2 bucket locks give retention, not authorship [INFERRED from Cloudflare R2 behaviour; not checked live].

**Recommendation:** option 2 plus option 3. Verify by replay first (full model validation, rebuild the receipt from the chain), then check an Ed25519 signature over `receipt_sha256` against the committed allowlist. Effort M (S for replay, M for signing).

Key management:

- One key pair per approver. The private key stays offline with the operator (a hardware key or the OS keychain). It is never a repo, CI or Worker secret.
- The allowlist (`key_id`, public key, `valid_from`, `revoked_at`) is a committed file. Adding or revoking a key is a reviewed PR. CODEOWNERS should cover it (#111 is open).
- A verifier rejects a key revoked before the receipt's `approved_at`.
- A lost key is revoked and the receipt re-signed with a new key. Records are append-only, so re-signing adds a signature; it changes no metric.
- The signature covers the receipt SHA, which covers `source_commit_sha`, so a signed receipt cannot be moved to another commit.
- New dependency: `cryptography` (Ed25519). An alternative with no Python dependency is `ssh-keygen -Y sign/verify` with an `allowed_signers` file, but the container would then need OpenSSH at verify time [INFERRED].

## R2. Rollback (spec "Rollback", `[INFERRED]`)

**Evidence:** with `ENABLE_CLEF_PROVIDER=false` the adapter is inert: every call returns `CLEF_DISABLED` without a network call [OBSERVED: backend/core/config.py, backend/evidence/routes.py `_configured_decision_provider`]. A failed provider persists no receipt [OBSERVED: backend/intelligence/clef_resolution.py `_provider_failure_result`]. The 007 records are in-memory frozen models; these modules make no database writes [OBSERVED: evaluation_enablement.py, OPERATOR_NOTES.md].

**Recommendation:** the rollback claim holds. Mark it RESOLVED. No task.

## R3. The receipt does not reach the runtime (005 FR-010)

**Evidence:** nothing outside the 007 and 008 modules calls `staging_enabled` or `verify_enablement_receipt` [OBSERVED: grep of backend/ and scripts/, 2026-10-29]. The API enables a provider on flags alone [OBSERVED: evidence/routes.py]. Production refuses to start with a provider on (#132) [OBSERVED: backend/core/startup_policy.py].

**Recommendation:** researched in [005 research R1](../005-decision-intelligence/research.md). 007 supplies the verifier; 005 T080 wires it in.
