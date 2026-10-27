# 006 Tasks — DAG compliant + state machines

## Upstream
- Depends on Spec 005 (DecisionProvider + DecisionPolicy + DecisionPacket).
- State machines are the State Transition step of the Spec Kit chain.

## Decision / Evidence Resolution state machine
States: PENDING → CLASSIFYING → PACKET_EMITTED → POLICY_APPLIED → {AUTO_PROPOSE | USER_REVIEW | UNRESOLVED | ESCALATE | REJECT} → CONFIRMED | DEFERRED | ARCHIVED

| From | Event | Guard | To | Notes |
|------|-------|-------|----|-------|
| PENDING | submit_evidence | valid evidence hash + bounded candidates | CLASSIFYING | idempotent on request id |
| CLASSIFYING | provider_success | DecisionPacket schema valid | PACKET_EMITTED | fail-closed otherwise |
| CLASSIFYING | provider_fail / timeout | — | REJECT | no confirmation possible |
| PACKET_EMITTED | apply_policy | policy version pinned | POLICY_APPLIED | disposition is deterministic |
| POLICY_APPLIED | disposition=AUTO_PROPOSE | — | AUTO_PROPOSE | proposal only, no canon write |
| POLICY_APPLIED | disposition=USER_REVIEW | — | USER_REVIEW | surfaces exact candidate + evidence identity |
| POLICY_APPLIED | disposition=UNRESOLVED | — | UNRESOLVED | preserved, no fabricated facts |
| POLICY_APPLIED | disposition=ESCALATE | routing target exists | ESCALATE | bounded, logged |
| POLICY_APPLIED | disposition=REJECT | — | REJECT | fail-closed |
| AUTO_PROPOSE / USER_REVIEW | user_confirm | existing confirmation path | CONFIRMED | only path to canon mutation |
| USER_REVIEW / UNRESOLVED | user_defer | — | DEFERRED | append-only receipt |
| any terminal | archive | — | ARCHIVED | immutable |

Clef never leaves CLASSIFYING. Disposition and canon remain policy- and confirmation-owned.

## ClefProvider adapter state machine
States: IDLE → INVOKING → {SUCCESS | TIMEOUT | MALFORMED | UNAVAILABLE} → IDLE

| From | Event | Guard | To |
|------|-------|-------|----|
| IDLE | invoke | feature flag on + request valid | INVOKING |
| INVOKING | response_ok | maps to DecisionPacket | SUCCESS |
| INVOKING | timeout / malformed / unavailable | — | respective fail state |
| SUCCESS / fail states | reset | — | IDLE |

Only SUCCESS emits a DecisionPacket. Fail states produce none. No Clef types escape the adapter.

## Edge deployment readiness state machine
States: UNCONFIGURED → PAGES_ATTACHED → API_HOSTNAME_LIVE → HYPERDRIVE_BOUND → CLEF_FLAGGED → GATES_PASSED → BETA_READY

| From | Event | Guard | To |
|------|-------|-------|----|
| UNCONFIGURED | pages_deployed | build output + custom domain | PAGES_ATTACHED |
| PAGES_ATTACHED | api_published | CORS exact origin + health ok | API_HOSTNAME_LIVE |
| API_HOSTNAME_LIVE | hyperdrive_bound | Neon staging string | HYPERDRIVE_BOUND |
| HYPERDRIVE_BOUND | clef_adapter_wired | flag default off | CLEF_FLAGGED |
| CLEF_FLAGGED | gates_pass | STAGING_HOST_PLAN + evaluation receipt | GATES_PASSED |
| GATES_PASSED | operator_approve | checklist receipts | BETA_READY |

Live payments, D1, and production-readiness claims stay forbidden until BETA_READY.

## Tasks (topological order)

Status reflects `main` at e0fb6a1 (see `DEPLOY_NOTES.md`). Where a task mixes repository code with
an operator action, the code half is sub-task `a` and the operator half is `b`, so a code task never
shows done while it waits on an operator dependency. `scripts/check_spec_dag.py` checks this file.

- [x] T001 Create feature tree `specs/006-cloudflare-edge-clef/` and add index line to `specs/README.md`.
  - depends_on: []

- [x] T010 Implement Decision / Evidence Resolution state machine.
  - depends_on: [T001]
  - acceptance: every path ends terminal or ARCHIVED; no canon write before CONFIRMED.

- [x] T020 Implement ClefProvider adapter state machine.
  - depends_on: [T001]
  - acceptance: only SUCCESS emits DecisionPacket; no type leakage; flag default off.

- [ ] T030 Create Cloudflare Pages project for Vite frontend. DEFERRED, operator. PR #55 ships the SPA on Cloudflare Workers and records this task as PARTIAL.
  - depends_on: [T001]
  - acceptance: build succeeds, custom domain attached, VITE_API_BASE_URL set.

- [ ] T050 Provision the Neon staging database for the API container. Re-scoped 2026-10-26: Hyperdrive serves Worker-runtime clients only, so the FastAPI container connects to Neon's pooled endpoint directly.
  - depends_on: [T001]
  - [x] T050a Pass `DATABASE_URL` and `SECRET_KEY` from Worker secrets into the container, and answer 503 without starting it when either is unset (code).
    - depends_on: [T001]
  - [ ] T050b Create the Neon staging branch and set its pooled connection string (`sslmode=require`) as the `edge/api` `DATABASE_URL` secret; the container's first start runs `alembic upgrade head` (operator).
    - depends_on: [T050a]

- [ ] T055 Keep evidence uploads, exports and design packs in durable object storage (R2), not on the container's disk. Container disks are wiped when the instance sleeps, restarts or redeploys, and `backend/evidence/routes.py`, `backend/export/`, `backend/publishing/routes.py` and `backend/canon/fulfillment.py` write under `export_dir` / `export_store_root` and record local paths in Postgres.
  - depends_on: [T001]
  - acceptance: an uploaded evidence image, an export and a design pack all survive a container restart; no database record points at a missing file.
  - [ ] T055a Move the `export_dir` / `export_store_root` reads and writes onto R2 (code).
    - depends_on: [T001]
  - [ ] T055b Create the R2 bucket and bucket-scoped credentials, and set them as `edge/api` secrets (operator).
    - depends_on: [T055a]

- [ ] T040 Publish API hostname and restrict CORS. Operator chose Cloudflare Containers at `api.patch-hive.com` (2026-10-26).
  - depends_on: [T030]
  - acceptance: exact origin, ALLOW_PRODUCTION_PAYMENTS=false, /health/ready ok.
  - [x] T040a Add the `edge/api` Containers Worker serving FastAPI (`backend/Dockerfile`) at `api.patch-hive.com`, with exact-origin CORS and fail-closed payment flags in its config (code).
    - depends_on: [T001]
    - acceptance: `wrangler deploy --dry-run` builds the image; locally the image serves `/health` 200 and CORS allows only `https://patch-hive.com`.
  - [ ] T040b Set the `edge/api` secrets, deploy it, and record `GET /health/ready` through the edge (operator).
    - depends_on: [T040a, T050b, T055b]

- [ ] T060 Wire ClefProvider into evidence-resolution path behind Spec 005 policy.
  - depends_on: [T020, T050]
  - acceptance: disposition policy-owned; idempotent receipts.
  - [x] T060a Wire ClefProvider into the evidence-resolution path against the existing database layer (code).
    - depends_on: [T010, T020]
    - acceptance: disposition policy-owned; idempotent receipts; no persistence change.
  - [ ] T060b Verify the wired path on the Neon-backed staging API (operator).
    - depends_on: [T050, T060a]

- [x] T070 Implement Edge Deployment readiness state machine and gate checks.
  - depends_on: [T060a]
  - acceptance: only GATES_PASSED → BETA_READY after operator approval.

- [x] T080 Extend evaluation harness; pin receipt SHA.
  - depends_on: [T060a]

- [x] T090 Integration tests for decision and deployment machines.
  - depends_on: [T010, T070]
