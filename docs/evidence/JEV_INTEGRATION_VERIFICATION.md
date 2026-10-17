# Jev integration contract verification

Verified: 2026-09-25

Status: VERIFIED_PUBLIC_CONTRACT / LIVE_CREDENTIAL_CALL_NOT_RUN

## Verified public contract

PatchHive's Jev adapter targets the documented TypeSafe System One HTTP interface:

- evaluation route: POST /v1/systemone;
- authentication: Bearer credential;
- request body: model, state, questions;
- question primitives: choice, score, noul;
- multiple named questions may be evaluated in one request;
- GET /v1/models is available for authenticated model discovery;
- an Idempotency-Key header is documented and should be used for controlled calls.

The existing PatchHive adapter's endpoint shape and three primitive mappings are therefore aligned with the current public interface.

## Model-version rule

`jev-latest` is a moving alias. It is acceptable for development discovery, but it MUST NOT be used to generate a retained baseline, calibration result, threshold decision, or release receipt.

T061d/T062 evaluation MUST:

1. discover/verify the available model identifier;
2. select a pinned Jev release;
3. record that exact identifier in the evaluation receipt;
4. keep corpus SHA and policy version fixed during comparison.

Changing the model invalidates comparison against an earlier retained Jev measurement unless a new evaluation receipt is generated.

## Idempotency rule

Controlled provider calls SHOULD send the DecisionRequest idempotency identity through the provider's documented Idempotency-Key header in addition to PatchHive's local request identity. This is an integration-hardening item before T070.

## Evidence boundary

Public documentation verification proves protocol compatibility only. It does not prove:

- account authorization;
- live response compatibility for the configured credential;
- latency/cost for PatchHive workloads;
- calibration on PatchHive's corpus;
- production readiness.

Those remain empirical gates.

## Preflight command\n\nRun only with an authorized credential and an exact pinned model identifier:\n\n```bash\nTYPESAFE_API_KEY=... JEV_MODEL=<pinned-model> python scripts/jev_staging_preflight.py\n```\n\nThe script refuses moving aliases, sends only synthetic state, sends the documented idempotency header, never enables the feature flag, and emits a hashable receipt without the credential or provider payload.\n\n## T070 preflight

Before controlled staging enablement:

- [ ] representative corpus admitted and frozen;
- [ ] pinned Jev model selected;
- [ ] live credential call succeeds against the documented contract;
- [ ] response validates into provider-neutral DecisionPacket;
- [ ] timeout/error path fails closed;
- [ ] idempotency behavior checked;
- [ ] latency and cost recorded;
- [ ] baseline/Jev receipt retained;
- [ ] operator threshold approval recorded;
- [ ] feature remains disabled in production.


## 2026-09-26 controlled protocol preflight

A credentialed synthetic-state preflight succeeded against pinned model `jev-1.13.0`.

- HTTP status: 200
- Answer shape: valid
- Latency: 210.791 ms
- Canonical authority: false
- Decision Intelligence feature enabled: false
- Receipt: `docs/evidence/receipts/T070-JEV-PREFLIGHT-2026-09-26.json`
- Workflow run: `36222430963`
- Source SHA: `5b14034c204c93e56da8230efbe37b39790c9fd4`

Interpretation: **PROTOCOL_COMPATIBILITY_ONLY**. This confirms the authorized credential, pinned model, endpoint contract, and response shape work together. It does **not** complete T061, T062, or production T070 enablement. Production thresholds remain **NOT_COMPUTABLE** until the governed reviewed corpus and retained evaluation receipt exist.
