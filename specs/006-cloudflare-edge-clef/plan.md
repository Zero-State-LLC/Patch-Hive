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
- GitHub connector currently lacks Contents write; reconnect required before commit.
