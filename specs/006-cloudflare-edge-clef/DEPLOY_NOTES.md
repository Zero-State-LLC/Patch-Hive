# Spec 006 Deploy Notes (Cloudflare Edge + Clef)

Status: code for T010, T020, T060, T070, T080, T090 is implemented and tested in-repo.
T030, T040 and T050 are DEFERRED operator actions. Nothing in this repository touches
Cloudflare, and no real hostnames, account ids, or secrets are recorded here.

## Operator-locked decisions

These are owned by the operator and are intentionally NOT set in code or config:

- API hostname(s) for the edge frontend and the API origin.
- Tunnel vs Containers for exposing the FastAPI origin behind Cloudflare.
- Cloudflare account id and the Workers AI API token used by Clef.
- The exact frontend origin used for CORS.

Until the operator records them, `config_gate_checks(..., expected_frontend_origin=None)`
reports `CORS_EXACT_ORIGIN` as failed with `OPERATOR_LOCKED`, so the readiness machine
cannot reach GATES_PASSED from config alone.

## Deferred tasks

| Task | Action | Status | Repo scaffolding |
| --- | --- | --- | --- |
| T030 | Cloudflare Pages project for the Vite frontend | DEFERRED, operator | `VITE_API_BASE_URL` documented in `.env.example` (read by `frontend/src/lib/api.ts`) |
| T040 | Publish API hostname and restrict CORS to the exact origin | DEFERRED, operator-locked | `CORS_ORIGINS` exact-origin gate in `backend/core/ops/edge_readiness.py` |
| T050 | Bind Hyperdrive to the Neon staging branch | DEFERRED, operator | none; existing `DATABASE_URL` path is unchanged |

T060 lists T050 as a dependency. The T060 code path is implemented and tested against the
existing database layer; it does not require Hyperdrive and does not change persistence.

### T030 checklist (operator)

1. Create the Pages project from `frontend/` (build `npm run build`, output `dist`).
2. Set `VITE_API_BASE_URL` to the operator-locked API hostname plus `/api`.
3. Attach the operator-locked custom domain.
4. Record the build receipt (commit SHA, Pages deployment id) as a checklist receipt.

### T040 checklist (operator)

1. Choose Tunnel or Containers for the FastAPI origin (operator-locked).
2. Publish the API hostname (operator-locked).
3. Set `CORS_ORIGINS` to exactly the Pages origin (no wildcard, no path).
4. Confirm `ALLOW_PRODUCTION_PAYMENTS=false` and `STRIPE_TEST_MODE=true`.
5. Confirm `GET /health/ready` is OK through the edge and record the receipt.

### T050 checklist (operator)

1. Create a Hyperdrive config pointing at the Neon staging branch.
2. Keep the connection string in the Cloudflare secret store only; never in git.
3. Run existing Alembic migrations against staging; no D1 and no new schema.
4. Record the binding receipt.

## Clef provider configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `ENABLE_DECISION_INTELLIGENCE` | `false` | Spec 005 master flag; route returns 409 when off |
| `DECISION_PROVIDER` | `disabled` | `disabled`, `jev`, or `clef` |
| `ENABLE_CLEF_PROVIDER` | `false` | Clef feature flag; DEFAULT OFF |
| `CLEF_MODEL` | `clef` | `clef` or `clef-flash` |
| `CLOUDFLARE_ACCOUNT_ID` | empty | operator secret |
| `CLOUDFLARE_AI_API_TOKEN` | empty | operator secret |
| `CLEF_BASE_URL` | `https://api.cloudflare.com/client/v4` | Workers AI REST base |
| `CLEF_TIMEOUT_SECONDS` | `10` | bounded request timeout |

Fail-closed behavior:

- With `DECISION_PROVIDER=clef` and `ENABLE_CLEF_PROVIDER=false`, the adapter is constructed
  inert. Every call fails with `CLEF_DISABLED` (HTTP 409) before any network call or image load.
- Timeouts map to `CLEF_TIMEOUT` (HTTP 504). Transport and HTTP errors map to
  `CLEF_UNAVAILABLE` (HTTP 502). Schema or candidate violations map to `CLEF_MALFORMED` (502).
- In the Spec 006 guarded flow, a provider failure moves the resolution machine to REJECT and
  writes NO decision receipt. The Spec 005 `resolve_module_identity` path is unchanged.
- Disposition is always computed by the Spec 005 `DecisionPolicy`; Clef only supplies a
  `DecisionPacket`. Clef request and response types stay inside `intelligence/clef_provider.py`.
- Canonical inventory is never written by this path. `canon_write_permitted` is true only in
  CONFIRMED, which requires the existing user confirmation path.

## Edge readiness machine

`backend/core/ops/edge_readiness.py` models the deployment states in order and only allows
GATES_PASSED -> BETA_READY with explicit operator approval and checklist receipts. Invariants
re-checked at the gate and at approval:

- `ALLOW_PRODUCTION_PAYMENTS=false` (no live payments; `live_payments_permitted` is always false)
- no D1 binding and no D1 schema migration (`d1_permitted` is always false)
- Clef flag default off, and enabled only with credentials present
- a pinned Clef evaluation receipt SHA-256 (from `intelligence/clef_evaluation.py`)

## Evaluation harness (T080)

`intelligence/clef_evaluation.py` loads a labeled JSONL corpus that must contain both text and
vision cases, computes overall and per-modality metrics, and builds a pinned receipt
(`patchhive.clef-eval-receipt.v1`) whose SHA-256 is verified with `verify_pinned_receipt`.
Receipts are never auto-approved: the best status is `THRESHOLDS_MET_PENDING_OPERATOR`.
Operator thresholds are explicit; `false_canonicalization_max` is fixed at 0.
`intelligence/clef_telemetry.py` separates PROVIDER_FAILURE from LOW_CONFIDENCE and carries no
evidence, labels, images, or payloads.

A live Clef evaluation run against Workers AI is an operator action and is not performed in CI.
