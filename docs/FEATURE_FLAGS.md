# Feature flags

All flags are environment variables parsed case-insensitively by backend settings.

| Flag | Default | Purpose |
|---|---:|---|
| `ENABLE_LEGACY_SOCIAL` | `false` | Compatibility feed/comment/vote endpoints only (login/register/profile stay always-on under `/api/community`) |
| `ENABLE_LEGACY_PUBLISHING` | `false` | Compatibility public publication endpoints |
| `ENABLE_LEGACY_LEADERBOARDS` | `false` | Compatibility leaderboard endpoints |
| `ENABLE_LEGACY_REFERRALS` | `false` | Gates `/api/me/referrals`, community referral summary, referral signup capture, and monetization purchase-for-referral recording |
| `ENABLE_LEGACY_PATCHBOOK_DEBIT` | `false` | When `false`, `POST /api/export/runs/{id}/patchbook` returns **410** (use `/api/canon/exports`) |
| `STRIPE_TEST_MODE` | `true` | Reject livemode webhook events in the canonical Stripe adapter and `/api/canon/webhooks/stripe` |
| `ALLOW_PRODUCTION_PAYMENTS` | `false` | Kill switch. When false, production webhook intake returns 403. Startup fails closed if production sets this false while `STRIPE_TEST_MODE=false`, or sets this true without reviewed secrets. |
| `STRIPE_WEBHOOK_SECRET` | empty | Stripe signing secret for `/api/canon/webhooks/stripe` |
| `DOWNLOAD_TOKEN_SECRET` | empty | HMAC secret for scoped export download tokens (when empty, a key derived from `SECRET_KEY` for downloads only, never `SECRET_KEY` itself) |
| `ENABLE_PATCHBOOK_DESIGN_ENGINE` | `false` | Style recipes, resolve-before-debit seal, Studio surface |
| `ENABLE_CANON_EXPORT_FULFILLMENT` | `false` | Worker/path that composes PDF pack after debit (closes queued-forever gap) |
| `ENABLE_INLINE_EXPORT_FULFILLMENT` | `false` | After debit commit, fulfill synchronously on request thread (tests/dev) |
| `ENABLE_PATCHBOOK_PUBLICATION_PROFILE` | `false` | Multi-page publication + artistic dual-artifact packs |
| `REQUIRE_SEALED_GENERATED_PATCHES` | `false` | Path A only — fail if no `GeneratedPatchRecord` (post dual-write cutover) |
| `DESIGN_ENGINE_DEFAULT_TIER` | `core` | Server-side presentation tier until entitlements exist (not client-spoofable) |
| `EXPORT_FULFILL_MAX_ATTEMPTS` | `5` | Max fulfillment claims before compensate |
| `EXPORT_STORE_ROOT` | `./exports` | Root for `design_packs/{export_id}` packs |
| `PREVIEW_RATE_LIMIT_PER_MINUTE` | `30` | Free Style Studio preview requests per user per minute |

Auth endpoints (`POST /api/community/auth/login`, registration, profile) are part of the default MVP surface and do **not** require `ENABLE_LEGACY_SOCIAL`.

### Canonical payment/export HTTP surface

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/canon/credits/balance` | Canonical ledger balance for the authenticated user |
| `GET` | `/api/canon/credits/summary` | Balance + recent ledger rows (account dashboard) |
| `GET` | `/api/canon/exports` | Owner-scoped canonical export history |
| `POST` | `/api/canon/exports` | Atomic debit + export record (`request_export`) with idempotency key; optional `style_recipe` **or** `style_recipe_id` |
| `GET` | `/api/canon/exports/{id}` | Owner-scoped export status |
| `POST` | `/api/canon/exports/preview` | Free Design Engine preview (no debit); rate-limited |
| `GET/POST` | `/api/canon/style-recipes` | Owner style recipe library |
| `GET/PATCH/DELETE` | `/api/canon/style-recipes/{id}` | Owner recipe CRUD |
| `POST` | `/api/canon/exports/{id}/download-token` | Issue short-lived principal-scoped token |
| `POST` | `/api/canon/exports/{id}/download` | Verify token scope for a completed/queued export |
| `GET` | `/api/canon/exports/{id}/artifacts/{name}` | Stream `pdf` / `zip` / `companion` / `manifest` (token query + auth) |
| `POST` | `/api/canon/webhooks/stripe` | Replay-safe Stripe-style webhook intake |

See also: `docs/design/PATCHBOOK_STAGING_ENABLEMENT.md`

### Client preference (P1 — PR #49 done for MVP UI)

| Client surface | Preferred path | Residual legacy |
|---|---|---|
| Rig workspace credits + patch-book debit | `canonApi` → `/api/canon/credits/balance`, `POST /api/canon/exports` | `exportApi.patchbookExport` deprecated; **not used by active UI** |
| Account credits + export list | `accountApi` → `/api/canon/credits/summary`, `GET /api/canon/exports` | `/api/me/credits`, `/api/me/exports` still on server |
| PDF/SVG file bytes | still `/api/export/...` GETs | Artifact delivery only — **no new debits** |
| Acceptance debit tests | **`POST /api/canon/exports`** | Legacy path only if `ENABLE_LEGACY_PATCHBOOK_DEBIT=true` |
| RigDetail / Racks run list | **`canonApi.listRuns` → GET `/api/canon/runs?rig_id=`** | Legacy `GET /api/runs?rack_id=` remains |

### DEPRECATIONS

| Endpoint / client | Status | Notes |
|---|---|---|
| `exportApi.patchbookExport` | **Removed from MVP client** | Lived under active `api.ts`; deleted — use `canonApi.createExport` |
| `POST /api/export/runs/{id}/patchbook` | **Disabled by default** | `ENABLE_LEGACY_PATCHBOOK_DEBIT=false` → 410; opt-in only for compatibility tests |
| Unrouted FE pages (Feed/Publish/…) | **Quarantined** | `frontend/src/legacy/` — not linked in `App.tsx` |
| `publishingApi` / `communityApi` / `leaderboardsApi` | **Legacy clients** | `frontend/src/legacy/apiClients.ts` only |

Legacy `/api/export` PatchBook **POST** routes remain during transition but must not be used by the active UI. Production payments stay disabled unless a separate reviewed change sets `ALLOW_PRODUCTION_PAYMENTS=true` with real secrets.

Historical flags may be enabled only in isolated compatibility tests or explicitly reviewed non-production environments. The frontend does not expose corresponding navigation.
