# Implementation plan — 006 Cloudflare Edge + Clef

## Architecture

Pages (Vite) → API hostname (Tunnel or Containers) → FastAPI  
Hyperdrive → Neon staging  
Workers AI Clef → ClefProvider adapter → Spec 005 DecisionPolicy → confirmation UI

## Phases

### WP-00 Spec tree
Create feature directory and index entry. No bulk moves.

### WP-01 Frontend edge
Cloudflare Pages project. Build: `cd frontend && npm ci && npm run build`. Output: `frontend/dist`. Attach custom domain. Set `VITE_API_BASE_URL`.

### WP-02 API surface
Publish hostname. Restrict CORS to exact origin. Confirm `ALLOW_PRODUCTION_PAYMENTS=false`. Verify `/health/ready`.

### WP-03 Data plane
Hyperdrive binding to Neon staging connection string. No schema change.

### WP-04 Clef adapter
Implement ClefProvider. Map System One response to DecisionPacket. Feature flag default off. Fail-closed. No type leakage.

### WP-05 State machines
Implement the three machines defined in tasks.md as pure transition tables.

### WP-06 Evaluation
Extend harness with labeled corpus. Pin receipt SHA. Operator sets thresholds.

### WP-07 Gates
Re-run STAGING_HOST_PLAN. Update DOMAIN_CUTOVER_CHECKLIST with receipts. Only then BETA_READY.

## Risks

- CORS origin mismatch blocks frontend.
- Tunnel/Containers choice affects latency and ops surface; operator must lock.
- Clef vision cost/latency; flag stays off until evaluation.
- Frontend hosting moved from Pages to Workers in PR #55; FR-001 and T030 still name Pages and need an operator decision.

## Constitution check

| Principle | How this feature complies |
| --- | --- |
| 4 Probabilistic systems propose | Clef never leaves CLASSIFYING; disposition is the Spec 005 policy. |
| 7 Providers are replaceable adapters | Clef types stay inside `intelligence/clef_provider.py`. |
| 9 Fail closed | Timeout, malformed, unavailable, and disabled all map to explicit errors with no receipt. |
| Authority boundary | `canon_write_permitted` only in CONFIRMED via the existing confirmation path. |

Gap: the constitution's chain also asks for journeys, workflows, contracts, security, and rollback. This feature records them only in DEPLOY_NOTES.md.
