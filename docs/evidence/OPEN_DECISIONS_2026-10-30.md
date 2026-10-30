# Open owner decisions (2026-10-30)

Research against `main` at `4d5bfe9` (#146), after #134–#146 merged and the migrations reached staging and prod. It supersedes the open items in [OPEN_DESIGN_DECISIONS_2026-10-28.md](OPEN_DESIGN_DECISIONS_2026-10-28.md); the per-spec background is in each `specs/NNN-*/research.md`. OBSERVED means read in the checkout or on GitHub; INFERRED means reasoned from it. Nothing here queried production data.

## Summary

| # | Decision | Recommendation | Effort | Owner must answer |
|---|---|---|---|---|
| 1 | Provider purchases (004 R1, T046–T051) | Build neither yet; build credit packs (Machine B) first once there is a launch date | 0 now; L later | Launch date; prices (OQ-1); credits-only or tiers at launch |
| 2 | Legacy `POST /api/monetization/purchases` (004 R5, OQ-11, T043) | Delete it and give referrals their own flag | S | Confirm no deployed env sets `ENABLE_LEGACY_REFERRALS=true`; are referrals a feature before purchases exist |
| 3 | Production payments (004 T051) | Defer until a purchase path exists | 0 | Date for real money; who owns tax, refunds and terms of sale |
| 4 | Publishing (002 OQ-6, T033) | Keep off; if it returns, bind a publication to an existing validated canon export first | 0 now; M later | Is a gallery on the roadmap |
| 5 | Preflight warnings (002 OQ-7) | Keep recording, not blocking | 0 | Do warnings affect print quality enough to gate acceptance |
| 6 | Prod workflow protection (006 R2, T101) | Merge #111, then a `production` environment: main only, you as reviewer, prod secrets moved into it | S + S | Reviewer; a second reviewer; gate staging too |
| 7 | `decision_routing_target = human_review` default (#146) | Default it to empty until something consumes ESCALATE | S | Is the confirmation UI meant to show ESCALATE records |
| 8 | Strict key revocation (#144) | Keep strict; update 007 research R1 to match | 0 | Rotation or loss: which is likelier; is re-signing acceptable |
| 9 | 221 unsourced v1 HP values (003 R7, T038/T039) | Triage, and make maker-sourced overlays outrank v1 | M | Triage yes/no; precedence; Akemie's Castle 18 or 38 HP |
| 10 | Paid fetches (003 T035, T031) | Approve T035 with a 50-credit cap; defer T031 | S | T035 cap; whether categories are worth ~1,100 credits |
| 11 | Six rig scores (001 OQ-11) | Define `routing_flex_score` and `performance_density_index`; keep four NOT_COMPUTABLE | S | Accept those formulas or supply others; fate of the four soft scores |
| 12 | Spec 001 R5, R6, R8 | Ratify R5 and R6 as built; R8 (OQ-10, OQ-13) still open | 0 | Retention period, overlay rules, threat model |
| 13 | Deploy #134–#146 | Staging first, smoke test, then prod; migrations are already applied | ~30 min | Deploy today or wait; move deploys into CI after T101 |

## A bug found during the research (not a decision)

HP overlays only fill an empty value (`data/synth-catalog/population.py:931`) and load in sorted order (`:242`), so the unsourced `module-catalog-hp-v1` fills before the maker-sourced `module-catalog-hp-v2`. Where they disagree, the maker value never lands. OBSERVED overlaps:

| Slug | v1 (unsourced) | v2 (maker page) |
|---|---|---|
| acid-rain-technology-junction | 6 | 4 (acidraintechnology.com) |
| alm-busy-circuits-akemie-s-castle | 18 | 38 (busycircuits.com) |
| doepfer-a-101-3 | 10 | 30 (doepfer.de) |
| doepfer-a-137-2 | 10 | 14 (doepfer.de) |
| doepfer-a-101-9 | 8 | 8 (agree) |

The two Doepfer rows are not among the 7 disagreements in 003 research R7. Each needs a hand check of the maker page before a `correct` entry (D4); research R7 lists Junction and Akemie's Castle among its 7 disagreements but doesn't say which value is right. Fixing the precedence belongs with decision 9.

## Commerce (spec 004)

### 1. Provider purchases

Nothing can be bought today. `checkout.session.completed` and `customer.subscription.*` are recorded `unresolved` with `HANDLER_NOT_IMPLEMENTED` (`backend/canon/webhook_events.py:54`), and no checkout, customer, subscription or payment code exists. Credits buy one thing, a PatchBook export at 3 credits (`backend/core/config.py:89`), and only an admin grant or a referral mints them. Tiers don't come from payment: `resolve_user_tier` returns the `design_engine_default_tier` setting (`backend/canon/entitlements.py:44-50`). Design Engine and export fulfillment are off by default (`config.py:118-119`). The only prices are in `STRIPE_INTEGRATION_PROMPT.md:14-16` and are unratified (OQ-1).

| Option | Effort | Risk | Unblocks |
|---|---|---|---|
| A. Machine B (credit packs) only, plus T047 and T048 | L + S + M | Medium: money and a ledger | Self-serve credits, referral reward on purchase |
| B. B, then C (subscriptions, T049, T050) | L + L + S | Higher: status, proration and tier rules (OQ-3, OQ-4, OQ-7, OQ-8) are open | The full tier ladder |
| C. C only | L | High; T049 depends on T046, so C needs B's plumbing anyway | Tiers |
| D. Neither for now | 0 | None | Nothing; admin grants stay the only source |

**Recommendation: D now, A first once there is a launch date.** INFERRED: there is no paying user base and the production product is pre-launch, so the need isn't evidenced yet. When it comes, B before C, because T049 depends on T046 and C carries the most open questions. Ratify prices first either way; T046 is blocked on OQ-1.

### 2. Legacy purchase route

`POST /api/monetization/purchases` (`backend/monetization/routes.py:17-33`) takes a client-sent `credits_delta` and returns 404 unless `enable_legacy_referrals` is set; the flag defaults false (`config.py:58`) and no compose, edge or infra file sets it. The same flag gates referral signup (`backend/community/auth_routes.py:47,76`) and the referral summaries (`backend/community/routes.py:37`, `backend/account/routes.py:57`). Nothing in `frontend/src` calls the purchase route; `Account.tsx:58-62` reads the referral summary and tolerates a 404. The only test is a negative one (`backend/tests/api/test_p1_security.py:186-197`).

| Option | Effort | Risk |
|---|---|---|
| A. Delete the route and `PurchaseCreate`; add a dedicated referral flag | S | Low; renaming the flag turns referrals off on any host using the old name, which is the safe direction |
| B. Delete the route, keep the flag name | S | Lowest; the "legacy" name stays misleading |
| C. Keep it admin-only | S | A self-reported purchase can still take the first-purchase referral slot (EC-3) |
| D. Leave it | 0 | Already off; mints nothing spendable |

**Recommendation: A, as T043 says.** It is dead code whose only live risk is EC-3. If decision 1 goes ahead, order matters: T047 depends on T043.

### 3. Production payments

`allow_production_payments` defaults false (`config.py:97`) and is pinned false in every staging compose file, `.env.example` and the Worker config. Live-mode events are refused outside production test mode (`backend/canon/exports.py:289`). T051 depends on T044, T047, T048 and T049, and needs an adversarial review and owner sign-off. INFERRED extras: ratified prices, tax and refund policy, a live Stripe account and webhook secret.

**Recommendation: defer entirely.** The fail-closed defaults are in place and tested, so waiting costs nothing.

## Publishing (spec 002)

### 4. Bring publishing back (OQ-6, T033)?

Since #143, `draft → published` always returns 409 `PUBLICATION_BOOK_NOT_VALIDATED`: `_bound_to_validated_book()` returns `False` (`backend/publishing/routes.py:303-308`). Nothing user-facing publishes anyway. The publishing router mounts only with `ENABLE_LEGACY_PUBLISHING=true` (default false), and the publish, gallery and publication pages live in `frontend/src/legacy/`, which `App.tsx` doesn't import.

| Option | Effort | Risk | Unblocks |
|---|---|---|---|
| 1. Keep it off | 0 | Low | Nothing, and nothing needs it |
| 2. T033: bind each publication export to a canon export whose pack passed `validate_book` | L | Medium: migration and public content | A published gallery |
| 3. Let a publication reference an existing validated canon export by id | M (INFERRED) | Low–medium | Publishing for books that already validated |
| 4. Exempt legacy exports from FR-048 | S | Reopens the bypass | Not advised |

**Recommendation: 1 now; 3 first when a gallery is scheduled.**

### 5. Should warnings block acceptance (OQ-7)?

Warnings are recorded in the manifest (#138) and in `validation/book.json` (#143), but don't block. **Recommendation: keep them non-blocking** until real warning data shows which ones matter; a later rule could block a named list of severe codes.

## Governance and defaults

### 6. Production workflow protection (006 R2, T101)

The repo's environments are `copilot` and `github-pages`, both unprotected; there is no `staging` or `production`. Workflows that can reach production: `db-migrate.yml` and `db-load.yml` (both dispatch, with prod database secrets), and `edge-secrets.yml` (dispatch, Cloudflare token). Branch protection requires a code owner review with `enforce_admins` on. CODEOWNERS names `@Zero-State-LLC/partner-agents`, which #111 says no longer has repo access. That explains today's "Waiting on code owner review" refusals, and why your own approvals didn't count.

| Option | Effort | Risk |
|---|---|---|
| 1. T101 as written: `production` environment, main-only branch rule, you as reviewer, prod secrets moved into it | S + S | Low; one extra click per prod run |
| 2. Same with a second reviewer | S + S | Needs a second person with access |
| 3. Main-only rule and moved secrets, no reviewer | S | Stops secret use from other branches; no confirmation step |
| 4. Leave it | 0 | Prod secrets reachable from any dispatched branch run |

**Recommendation: merge #111 first, then option 1.** Even with one person, the gate adds a deliberate confirmation and keeps the prod secrets away from branch workflows. Move to option 2 when a second person joins.

### 7. `human_review` routing default (#146)

`config.py:81` defaults `decision_routing_target` to `human_review`, so failed or escalated decisions end in ESCALATE (`resolution_machine.py:289-290`). Nothing consumes ESCALATE: its only transition is to ARCHIVED, and no queue, API, UI or worker lists those records. In practice it is UNRESOLVED with a different label.

**Recommendation: default it to empty (S)** until a consumer exists, or build a small admin list of ESCALATE records (M) and keep the default. Labelling something "routed to human review" when no human can see it overstates what happens.

### 8. Strict key revocation (#144)

`backend/intelligence/receipt_signing.py:264-267` refuses a revoked key from its `revoked_at` onward, whatever the receipt's `approved_at`. 007 research R1 had only refused keys revoked before `approved_at`. Strict closes a hole: `approved_at` is chosen by the signer, so a stolen key could otherwise backdate receipts forever. The cost is re-signing after every revocation, which adds a signature without changing the append-only records.

**Recommendation: keep strict and update 007 research R1 to match.** If routine rotation becomes common, add a revocation reason (`compromised` strict, `rotated` lenient), effort M.

## Catalog (spec 003)

### 9. The 221 unsourced v1 HP values (R7, T038/T039)

All 221 are fill-null HP entries on `module_catalog`, loaded through `UNSOURCED_HP_OVERLAYS` (`population.py:900`); 186 are `maker_or_retail` and 35 `unknown_non_modulargrid`. None appears in the 448 retired slugs. Research R7 found 45 agree with the maker crawl, 7 disagree and 169 are unmatched. New: 185 of the 221 also appear in the committed `hermes-research/hp-enrichment-batch*-results.filtered.json` with a `source_url` and the same HP (157 official pages, 28 retailers). These look like v1's own lineage, so they aren't independent confirmation, but the 157 official ones are free citations for a v3 manifest.

Flagging would block placement: an HP flag on `modules` makes `validate_rack_configuration` return `MODULE_HP_NEEDS_REVERIFY` and skip the module (`backend/racks/validation.py:80-100, 179-195`). The count of affected live racks needs one prod query against `rack_modules`.

| Option | Effort | Risk |
|---|---|---|
| 1. Keep as grandfathered | S | D2 stays unmet, invisibly |
| 2. Flag all 221 | M | Blocks 221 common modules (mostly Doepfer, Bastl, ADDAC) in racks, for no new information |
| 3. Triage (T039): re-source the official-page values with citations, hand-check the ~9 conflicts with `correct` entries, mark the rest `legacy_unsourced`, then a free maker-page lookup | M | Low |
| 4. Option 3 plus maker-sourced overlays outranking v1 | M + S | Low; fixes the bug above |

**Recommendation: 4.** No paid fetches are needed; the maker pages are free and the committed files already hold most values.

### 10. Paid fetches

The scrape ledger shows 1,116 context.dev credits spent so far, about 0.44 per call (`data/synth-catalog/receipts/scrape-ledger.json`).

- **T035** re-fetches about 45 jumper-dependent pages (42 live 4ms modules, 2 Dave Jones Design, Velectronic A-Envelope) for an estimated 20–50 credits. It feeds T034 (`power_configs`), which today leaves 41 4ms modules with an unknown rail.
- **T031** rebuilds the whole page cache for about 1,100 credits, mainly to classify 644 untagged rows.

**Recommendation: approve T035 with a 50-credit cap; defer T031.** Try a free pass at categories from maker tags and titles first, then pay per brand only for what remains.

## Rig (spec 001)

### 11. The six rig scores (OQ-11)

No source defines them (`specs/001-rig-intelligence/spec.md:433`; `docs/CANON.md:25-45` lists names only). `backend/canon/rig_metrics.py:53-58` writes `NOT_COMPUTABLE` for all six. The only real formula in older code is `routing_flex_score = ports / modules` (`backend/canon/runes.py:163`); the rest are constants (0.75, 0.7) or 0.0 defaults. `suggest_layouts` raises if `routing_flex_score` isn't a number (`runes.py:182-184`), so today's packets can't feed it. The rig has module type, HP, three power rails, `io_ports` and tags per module.

| Option | Effort | Risk |
|---|---|---|
| 1. Keep all six NOT_COMPUTABLE | 0 | `suggest_layouts` and Abraxas stay blocked |
| 2. Define `routing_flex_score` (port count per module, saturating) and `performance_density_index` (ports or controls per HP); keep four NOT_COMPUTABLE | S | Low; both are mechanical |
| 3. Define all six | M–L | Invented meaning for "chaos" and "learning" would look authoritative |
| 4. Drop the four soft scores from FR-027 | S + spec change | Changes FR-027, CANON.md and the TypeScript type |

**Recommendation: 2**, shipped under a new metrics version with the formula in `confidence_notes`. The other four need meanings only you can supply. Whether `io_ports` is complete enough to trust a port count is unchecked.

### 12. Spec 001 research R5–R8

- **R5 (readiness, OQ-09):** built as at least one `USER_CONFIRMED` module and one confirmed catalog id (`backend/canon/inventory.py`, `backend/patches/inventory_gate.py`). Ratify, and say whether "the rig has a case" should be added.
- **R6 (rack vs rig revision, OQ-01):** `Rack` is the mutable rig and `rig-rev-{hash}` the immutable snapshot (`runs/bridge.py`). Needs a one-word confirmation.
- **R7 (Abraxas feedback store, FR-028):** nothing exists; no answer needed until the bridge is planned.
- **R8:** OQ-10 (retention, overlay rules) and OQ-13 (threat model) need you.

## Deploy

### 13. Deploying #134–#146

No workflow deploys the application (`docs/OPERATIONS.md:129`). The API deploys with `cd edge/api && npm ci && npx wrangler deploy` (add `--env staging` for staging), which needs Docker running; the frontend with `cd frontend && npx wrangler deploy` (`frontend/wrangler.jsonc`). Startup migrations are off, so migrations must come first. They have: `db-migrate.yml` brought staging (run 40984019890) and prod (run 40986508036) to `20261029_decision_receipt_idempotency`, and a dry run on each planned no changes. The only new setting is `decision_routing_target` (decision 7). INFERRED: no new secret is needed; `edge/api/wrangler.jsonc` vars were not diffed.

**Recommendation: deploy staging first, smoke test, then prod.** After T101, a deploy workflow behind the `production` environment would make deploys auditable and remove the dependency on one laptop.
