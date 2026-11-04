# Domain cutover checklist (operator-owned)

> **Update 2026-11-03:** the domains are live. `patch-hive.com` and `api.patch-hive.com` (production) and `staging.patch-hive.com` and `api-staging.patch-hive.com` (staging) are Cloudflare Workers custom domains, with exact-origin CORS and an enforced CSP. The template below is kept for the record; the walkthrough-SHA pin (spec 008 T050b) is still open.

**Status:** template only — **no domain was configured by the agent**  
**Why:** DNS/registrar access and a public edge are required; they are not available from the local Docker-only environment without your credentials.

## What the agent cannot do without you

| Need | Why |
|------|-----|
| Registrar login / API token | Change DNS records |
| Exact hostname (e.g. `app.example.com`) | You purchased it; not in repo secrets |
| Public IP or tunnel | Local Docker binds `localhost` only |
| TLS certs | Let’s Encrypt / Cloudflare / host SSL |

## Two realistic paths when you are ready

### Path 1 — Public VPS + your domain (recommended for real staging)

1. VPS with Docker; open 80/443  
2. Point DNS:
   - `A`/`AAAA` for `app.<domain>` → VPS IP  
   - `A`/`AAAA` for `api.<domain>` → VPS IP  
   or single host + reverse proxy paths  
3. Reverse proxy (Caddy/Nginx/Traefik) → containers  
4. Set env:
   - `STAGING_CORS_ORIGINS=https://app.<domain>`  
   - `STAGING_PUBLIC_API_URL=https://api.<domain>`  
   - strong `STAGING_SECRET_KEY` / DB password  
5. TLS via proxy (auto cert)  
6. Re-run gates in [STAGING_HOST_PLAN.md](STAGING_HOST_PLAN.md)

### Path 2 — Local Docker + Cloudflare Tunnel / ngrok (no VPS)

1. Keep `docker-compose.staging.yml` as today  
2. Install tunnel agent; map `https://app.<domain>` → `http://localhost:5173`  
3. Map `https://api.<domain>` → `http://localhost:8000`  
4. Update CORS + `VITE_API_URL` / `STAGING_PUBLIC_API_URL` to public HTTPS URLs  
5. DNS CNAMEs to tunnel hostnames (Cloudflare dashboard)

## Minimum data to give the agent later

Reply with:

1. **Domain** (e.g. `patchhive.example`)  
2. **DNS host** (Cloudflare / Namecheap / Route53 / …)  
3. **Path** (VPS IP **or** “tunnel on this Mac”)  
4. Desired hostnames (`app.` / `api.` or apex)  

Then we can write concrete DNS records + compose/proxy config. We still will not log into your registrar unless you provide an approved API token/MCP integration.

## Until then

Use **local Docker staging**:

- App: http://localhost:5173  
- API: http://localhost:8000  

## Spec 008 walkthrough pin (T050)

Domain cutover stays blocked until the Design Engine staging walkthrough
receipt is pinned here.

- [x] walkthrough_source_sha: 6c234a6535d1f4a58924243254ca4b607be2f461 (v0.3.0-alpha.7, run 41768209990, 2026-11-04)
- [x] walkthrough_receipt_sha256: b2c295027be8eb8d805d88e9bde33700c576795d66f4c7ff8b1b2f1b838a819c
- [ ] No unresolved P0 integrity regressions at that SHA
- [ ] Production payments remain disabled (`ALLOW_PRODUCTION_PAYMENTS=false`)

The pin validator (`core.ops.f5_cutover.pin_readiness_docs`) requires this file
and `PRODUCTION_READINESS_MATRIX.md` to contain the receipt's exact
`source_commit_sha`. See `specs/008-dual-path-f5-design-receipts/OPERATOR_NOTES.md`.
