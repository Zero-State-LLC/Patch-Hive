# Open questions decided by Jev, 2026-11-01

The owner delegated every open question to Jev ("research all open questions and have jev make decisions", 2026-11-01). Four research passes listed each question across specs 001–008 and the 2026-10-30 decision note. Each pass checked whether code or a recorded decision already answers the question, and gave 2–4 researched options for the rest. Jev (`jev ask`, a choice question per item, model `jev-1.14.0`) then picked one option per open question. It weighed the project rules: fail closed, evidence never canonical without a person, payments in test mode, determinism, smallest sufficient change, privacy by default.

How to read this:

- A decision with confidence below 0.5 is **provisional**: the owner should confirm it before it drives irreversible work.
- Anything touching legal exposure stays subject to a lawyer's confirmation; Jev's pick sets direction, not legal advice.
- Decisions that need an action only the owner can take (GitHub environment settings, emailing makers, supplying source text, a production deploy) are recorded here and left for the owner.

The raw research, options and Jev answers are in [jev-decisions-2026-11-01.json](jev-decisions-2026-11-01.json).

## 001-rig-intelligence

| Question | Decision | Option chosen |
|---|---|---|
| OQ-01: How does the persisted Rack/rack_id relate to Rig and RigRevision? | already answered | A Rack is the mutable rig; a rig revision is the immutable snapshot (id rig-rev-{content_hash[:32]}) that a run binds to. Implemented (FR-026). Decisions doc item 12 asks only for a one-word owner confirmation. |
| OQ-02: runs.rack_id CASCADE vs append-only runs: which wins, and what is the retention policy? | already answered | Append-only wins. Racks are soft-deleted; runs.rack_id and patches.rack_id are RESTRICT (T022, #93). Account-level deletion policy for legacy CASCADE tables is a separate piece of OQ-10. |
| OQ-03: Which category set is canonical (5 vs 9) and are subtypes separate? | already answered | Five canonical categories only (Voice, Clock-Rhythm, Generative, Texture-FX, Utility); no Study padding (T023, #94, FR-012). |
| OQ-04: Can generic port names be used in canonical patches? | already answered | Generic jacks are resolved to declared ones; unmapped ones are marked unresolved; contradictions fail the run with a validation report (T025, #97). |
| OQ-05: How is the seed chosen when omitted and how is it recorded? | already answered | Default is settings.default_generation_seed = 42 when the request omits seed; the seed is stored on every patch (generation_seed) and in the IR and its hash (T033, FR-024). |
| OQ-06: What is CHANGELOG F3 and what are the NOT_COMPUTABLE dual-write targets? | already answered | Resolved 2026-10-27: F3 is the legacy-to-canon generate dual-write; a NOT_COMPUTABLE attempt writes no run/record/library, only the inventory revision. |
| OQ-07: Full run status set and the state when generation yields zero patches? | already answered | queued, running, succeeded, failed, validation_failed, all terminal; zero patches from a computable rack ends succeeded (UI says no rule fits, T034). |
| OQ-08: Which validation findings block SUCCEEDED vs only flag? | already answered | Blocking findings (contradictions) fail the run as validation_failed with report; non-blocking (e.g. FEEDBACK_LOOP flag, MODULE_TOMBSTONED warning) are flagged. Resolved 2026-10-28 (#97). |
| OQ-09: What are the readiness conditions? | already answered | Built: at least one USER_CONFIRMED module and one confirmed catalog module id. Research R5 recommends recording this as the answer. Residual optional owner choice: also require a case (nothing in the engine needs one); decisions doc item 12 asks to ratify. |
| OQ-10: What are the retention, privacy and access rules for evidence (rig photos, OCR output) and user overlays? | `minimal_images_only` (confidence 0.29) (provisional: low confidence, owner to confirm; a lawyer must confirm) | Fix only the evidence gap: keep the 30-day default, cap at 90 (or leave 365), schedule expire_image_assets, add user-initiated image delete. Leave overlays, ledger and account deletion undefined for now. Smallest build; leaves account-deletion and GDPR-style erasure open. |
| OQ-11: Computation rules for the six rig scores? | already answered | Owner decided 2026-10-30 (option 2): routing_flex_score = round(1-exp(-(total_ports/module_count)/8),4) and performance_density_index = round(total_ports/total_hp,4); other four stay NOT_COMPUTABLE. Implemented in canon/rig_scores.py (T035). Caveat: only ~3 catalog modules carry io_ports, so most real rigs stay NOT_COMPUTABLE until a port-data pass. |
| OQ-12: Do read handlers commit/mutate state? | already answered | No. backend/runs/routes.py has no commit; get_db only closes the session. Reads write nothing (T021, #92, FR-020) with a test. |
| OQ-13: Does the provider evidence boundary need an ADVERSARY threat model in spec 001? | `scoped_adversary_section` (confidence 0.97) | Add an ADVERSARY section to spec 001 limited to the provider/evidence boundary (malicious uploader, hostile or poisoned provider output, OCR injection, decompression bombs), listing mitigations and gaps (production scanner not selected). Focused; matches the spec's Workflows gap. |

## 002-patch-book-publishing

| Question | Decision | Option chosen |
|---|---|---|
| OQ-1: Does POST /me/publications publish immediately or create a draft? | already answered | Creates a draft; owner publishes via PATCH (#101). |
| OQ-2: Can an owner unhide a publication an admin hid? | already answered | No. Admin hide sets moderation_audit_id; owner status change then gets 409 PUBLICATION_UNDER_MODERATION. |
| OQ-3: Can an admin remove a draft? | already answered | No. Admin remove accepts only published/hidden; draft gets 409 INVALID_TRANSITION. |
| OQ-4: Which fields are mutable after publish given 'immutable records'? | already answered | FR-037 fields stay editable in draft/published/hidden; a removed publication refuses any PATCH (#130). |
| OQ-5: Which response code do publishing endpoints return when the flag is off? | already answered | 404: router not mounted when ENABLE_LEGACY_PUBLISHING is false (flag-off 404 untested per T010). |
| OQ-6: Must a publication export bind to a validated PatchBookManifest? | `keep_off` (confidence 0.8) (a lawyer must confirm) | Leave _bound_to_validated_book()=False; publish always 409 PUBLICATION_BOOK_NOT_VALIDATED (current state, T032 done). Cost 0; no gallery. Repo recommendation now. |
| OQ-7: Does a PageFitReport/preflight warning ever allow acceptance? | `non_blocking_recorded` (confidence 0.88) | Warnings pass but are recorded in manifest and validation/book.json (already built, T036). No code change. |
| OQ-8: Is a book with zero accepted patch pages valid? | already answered | No. Design Engine fails EXPORT_NO_PATCHES; legacy route returns 404. |
| OQ-9: What are the cable-crossing, ambiguity and visual-diff thresholds? | `measured_thresholds` (confidence 0.89) | Implement crossing count and label-box overlap checks, set thresholds from measurement over existing fixtures (e.g. max crossings per page, zero label overlaps) and a pixel-diff tolerance. Needs owner to approve numbers; effort M. |
| OQ-10: How are concurrent owner and admin transitions ordered? | `row_lock` (confidence 0.66) | SELECT ... FOR UPDATE on the publication row in owner and admin handlers; admin then wins by ordering, and the owner path re-checks moderation_audit_id after the lock. Effort S, no migration; needs Postgres (no-op on SQLite). |
| OQ-11: How does ENABLE_PATCHBOOK_PUBLICATION_PROFILE reconcile with the one-page law? | `keep_off_deferred` (confidence 0.77) | Leave flag off, plates undrawn, validation failing by design (T031). Decision postponed; zero cost. |
| OQ-12: What is the legal effect and enforcement of the CC BY-NC 4.0 default license and allow_remix? (A lawyer must confirm.) | `owner_picks_license` (confidence 0.39) (provisional: low confidence, owner to confirm; a lawyer must confirm) | Add a license choice (e.g. CC BY-NC, CC BY-NC-ND, all-rights-reserved) mapped from allow_remix (remix=false -> ND). Medium effort; schema change; clearer intent. |
| OQ-13: What are report rate limits, anonymous-report rules and retention for reports/audit logs? | `limit_and_require_dedupe` (confidence 0.34) (provisional: low confidence, owner to confirm; a lawyer must confirm) | Keep anonymous reports but add per-IP/per-user rate limit and dedupe per (publication, reporter); retention still undecided. Effort S-M. |
| OQ-14: What do the truncated source extracts contain that the spec lacks? | `operator_supplies` (confidence 0.83) | Operator supplies the missing source text; spec is revised against it. Only path that truly answers it. |
| OQ-15: Should an ADVERSARY threat model cover the public read, download and report surfaces? | `threat_model_now` (confidence 0.43) (provisional: low confidence, owner to confirm) | Write a one-page threat model for /p/{slug}, download, gallery and report (enumeration of slugs, unlisted leakage, report spam, hotlinked downloads, malicious uploaded content). Effort S; doc only. |

## 003-catalog-dataset-pipeline

| Question | Decision | Option chosen |
|---|---|---|
| OQ-1: What should happen to the 57 legacy HP values that no maker page confirms (now 40 retailer_observed, 17 still legacy_unsourced), so UNSOURCED_HP_OVERLAYS can be retired? | `ask_makers` (confidence 0.49) (provisional: low confidence, owner to confirm) | Email ADDAC, Befaco, Instruo, Cwejman, Make Noise, Intellijel, Doepfer for spec sheets; keep the rows marked until a maker source arrives, then re-source via a new hp overlay. Slow, no data risk, T039 stays open indefinitely. |
| OQ-2: Which value is correct for the nine maker-vs-v1 HP disagreements nobody has hand-checked: Akemie's Castle (18 vs 38), Befaco Hexmix VCA (12 vs 14), Intellijel Quadrax (12 vs 14), Rubicon 2 (14 vs 20), Erica Fusion VCO (16 vs 24), Doepfer A-110-1 (8 vs 10), Joranalogue Generate 3 (16 vs 12), Qu-Bit Chord V2 and Data Bender (12 vs 14)? | `hand_check_then_correct` (confidence 0.92) | Read each maker page or manual (free, robots respected), then add `correct` entries (FR-038) for any wrong stored value, with a quote. Slowest (1-2 h) but resolves each properly. |
| OQ-3: How is a paid-fetch budget approval recorded and enforced so the crawler cannot start or resume without it (FR-003)? | `approvals_file` (confidence 0.92) | Commit `data/synth-catalog/receipts/fetch-approvals.json` (cap in credits and fetches, brands, expiry, approver). The crawler refuses any non-dry-run paid fetch without a matching unexpired entry and checks the ledger against it. Small code change, auditable in git. |
| OQ-4: Does the sealed Synth Catalog Research seed enter the lifecycle at OVERLAY, or at its own entry state? | `separate_seed_state` (confidence 0.68) (a lawyer must confirm) | Add SEEDED/SEALED state with its own guard (seed files immutable, hash pinned) and no FETCHING/FILTERED upstream. More precise, adds a state to implement and test. |
| OQ-5: Does the '3 consecutive scrubbed runs' verification apply to every admission? | `replace_with_plan_hash` (confidence 0.86) | Declare the existing dry-run, plan_hash-bound apply (plus a rerun-changes-nothing check) the verification ritual; mark the 3-run text as research-campaign history. No code. |
| OQ-6: Should catalog dedupe change from slug to (brand, slug) to avoid cross-brand collisions? | already answered | No change needed. The slug is built from brand plus name, and module_catalog.slug is globally unique; a second row whose normalized brand+name matches but whose brand or name differs is reported as an `identity_mismatch` conflict, not merged. The committed dry-run receipts show no such conflict. The spec's INFERRED slug-collision edge case is the only text to update (FR-021 wording). |
| OQ-7: What are the catalog coverage targets (roadmap targets were NOT_COMPUTABLE)? | `keep_not_computable` (confidence 1.0) | Report raw counts only and keep percentages NOT_COMPUTABLE until a universe is chosen. Matches SC-007 and the roadmap wording; no new claim risk. |
| OQ-8: Does the operator confirm the remaining [INFERRED] claims in spec 003 so T001/T002 (plan.md) can close? | `one_sitting` (confidence 0.94) | Walk the remaining INFERRED items in one owner session (R6 recommendation), then write plan.md from the confirmed spec and tick T001/T002. |
| OQ-9: Should the batch lifecycle (TARGETED to ADMITTED) be implemented as a code state machine, or should the spec be amended to describe the scripts as they are? | `enforce_inputs_hash` (confidence 0.77) | Minimum code: make apply compare the dry-run's inputs_hash as well as plan_hash and require evidence on retirements. Closes the two real gaps without a full machine. |
| OQ-10: Is retailer scraping permitted? | already answered | RESOLVED by D2: no automated retailer crawling; retailer values only from one-off manual lookups (FR-006, FR-039). |
| OQ-11: Which document wins on ModularGrid-derived data and what access basis do scraped rows carry? | already answered | RESOLVED by D1/D2: the seed is a discovery lead (access_basis = unknown), maker-page rows carry official_publication (FR-033). Thomann coverage likewise: manual lookups only. |
| OQ-12: What file conventions do overlays, provenance manifests and receipts follow? | already answered | RESOLVED 2026-10-29: versioned files under overlays/, provenance/, receipts/; an applied version is never rewritten (FR-018, FR-036). |
| OQ-13: How does the case seed pipeline behave and how many brands exist? | already answered | RESOLVED 2026-10-29: case seed imports via case_catalog_populator.import_records (insert-if-absent, fill-null; plan hash covers it, #103). Observed 703 registry manufacturers and 355 brands with live rows. |

## 005-decision-intelligence

| Question | Decision | Option chosen |
|---|---|---|
| OQ-1: Should an unsupported packet schema REJECT? | already answered | No. Treated as a provider failure: ESCALATE when a routing target exists, else UNRESOLVED, reason codes kept (T081, #135). |
| OQ-2: Does the Jev path have to use the guarded machine? | already answered | Yes. Every provider goes through the guarded flow with settings.decision_policy_version (T082, #135). |
| OQ-3: Is false_canonicalization_count = 0 measured? | already answered | It was hardcoded; T084 replaced it with the structural resolution-machine replay count and the candidate check now runs in evaluation. |
| OQ-4: Should a review queue for ESCALATE records be built so decision_routing_target can be set to human_review, or should ESCALATE stay unrouted? | `keep_empty_until_provider_on` (confidence 0.74) | Leave the default empty (current). Failed or escalated decisions end UNRESOLVED with ESCALATE_NO_ROUTING_TARGET. No work; acceptable while no provider is enabled in any environment. |
| OQ-5: Which thresholds does the operator approve as the enablement gate (T061)? | `baseline_equal` (confidence 1.0) | Use the coded rule: each threshold equals the measured baseline metric, false-canonicalization max 0. No invented numbers; the assisted run must at least not regress. |

## 006-cloudflare-edge-clef

| Question | Decision | Option chosen |
|---|---|---|
| OQ-1: How is the GitHub `production` environment protected for db-migrate, db-load and edge-secrets (T101b)? | `owner_reviewer_main_only` (confidence 0.36) (provisional: low confidence, owner to confirm) | production environment: owner as required reviewer, deployment branch main only, admin bypass off, prevent-self-review OFF while solo, prod secrets moved into it. One extra approval click per prod run; stops branch workflows reaching prod secrets. (Matches DEPLOY_NOTES and decision 6 rec.) |
| OQ-2: Do staging runs get their own gated `staging` environment and a separate staging-scoped Cloudflare token when the prod token moves into `production`? | `separate_staging_token` (confidence 0.97) | Issue a second, staging-scoped Cloudflare token; put prod token in `production` and staging token in `staging` (account id as variable in each). Recommended in the repo; also stops one token reaching both. Needs one more token to rotate. |
| OQ-3: Should the operator-owned tasks T030, T040b, T050b and T055b be closed now that staging and production are live? | `record_receipts_and_close` (confidence 0.6) | Add a short evidence receipt per task (health/ready output, migration run ids, R2 persistence check) and tick them. Honest closure; some work. |
| OQ-4: Does gates_pass verify the evaluation receipt itself (R1)? | already answered | Yes, T100 done: evaluation_receipt and signature are checked against the committed allowlist. |
| OQ-5: When is evidence expiry scheduled (T101c)? | already answered | Decided 2026-10-30: a daily evidence-expire.yml job after T101b, not now (0 image_assets rows; expiry still enforced at read time). Not built. |
| OQ-6: Pages/Hyperdrive wording, foreign pin-PR workflow, actions: write, orphan R2 token, production provider before BETA_READY, who creates the environment? | already answered | All resolved: acceptance summary amended (R6); T102, T103, T104 done; startup refuses production providers (#132); a repo admin creates the environment in settings. |

## decisions-2026-10-30

| Question | Decision | Option chosen |
|---|---|---|
| D13: Do #183-#186 (and release PR #169) get deployed to staging and production now, and should deploys move into CI? | `staging_then_prod_manual` (confidence 0.81) | wrangler deploy to staging, smoke test, then production from a main checkout (build the frontend per target). Matches decision 13 rec; depends on one laptop and Docker. |

## 004-commerce

| Question | Decision | Option chosen |
|---|---|---|
| OQ-1: Are tier prices ($4.99/$14.99/$29.99), monthly credits (25/100/unlimited), the one-time rule ($0.20/credit, $5 min) and currency/tax ratified? | `A_ratify_as_is` (confidence 0.29) (provisional: low confidence, owner to confirm; a lawyer must confirm) | Keep $4.99/$14.99/$29.99, 25/100/unlimited, $0.20/credit, $5 min, USD only. Fastest; but CORE has no discount vs credit packs, STUDIO unlimited is open-ended cost, and Stripe fees are ~9% on CORE/min pack. Matches 'ratify' recommendation in spec. |
| OQ-2: What is the refund/chargeback/dispute flow, and can a balance go negative? | `A_reverse_unspent` (confidence 0.96) (a lawyer must confirm) | On provider refund reverse only unspent credits, record remainder unresolved for operator, never negative, never revoke referral reward. Matches spec recommendation; simple, may leave small loss. |
| OQ-3: Does a subscription payment count as the referral 'first paid purchase', and is it recorded as Purchase, Grant or both? | `A_both` (confidence 0.96) | First paid invoice records a provider-verified Purchase via record_purchase(payment_verified=True) and the period credits are a separate Grant. Matches spec recommendation; referral rewards work for subscribers. |
| OQ-4: Which provider subscription statuses must be distinguished and what entitlement does each give? | `A_stripe_mapping` (confidence 0.98) | Per research table: active/trialing -> paid tier; past_due -> keep tier during retries, no new grant; unpaid/incomplete/incomplete_expired/canceled/paused -> FREE; grant only on invoice.paid. Matches spec recommendation and Stripe guidance. |
| OQ-5: What operator action resolves or rejects an Unresolved commerce event, who may do it, and what audit record results? | `A_refetch_session` (confidence 0.85) | Implement resolve by retrieving the Checkout Session by stored object id and running idempotent fulfillment; audit record; unresolved if not retrievable. Matches research recommendation. |
| OQ-6: Does signup fail, succeed or warn when the referral code does not resolve? | already answered | RESOLVED 2026-10-29: with referrals on, unresolved code fails signup with 400 Invalid referral code; with referrals off, code ignored. |
| OQ-7: How do upgrades/downgrades/proration affect stored tier and per-period grant? | `A_next_period_no_proration` (confidence 0.98) | Store tier from the provider price on every update; new tier credits granted at next period; no proration. Matches spec recommendation; simplest, mid-period upgrade gets no extra credits. |
| OQ-8: What does 'unlimited' mean for STUDIO? | `A_flag_with_fair_use` (confidence 1.0) | Explicit entitlement flag with owner-set fair-use cap (e.g. monthly export ceiling). Matches spec recommendation; bounded cost. |
| OQ-9: Which features does each tier gate beyond credits? | `A_templates_only` (confidence 0.79) | Gate only Design Engine template families (already coded) plus credits. No new work; tiers differ little beyond credits. |
| OQ-10: What does docs/SECURITY.md require for payment secrets, webhooks and personal data? | already answered | RESOLVED 2026-10-29: append-only credit entries; constant-time HMAC, timestamp tolerance, unique event ids, replay-conflict detection, livemode gate; STRIPE_TEST_MODE=true and ALLOW_PRODUCTION_PAYMENTS=false until activation review. |
| OQ-11: Is the legacy /purchases endpoint retired, restricted or kept? | already answered | Retired: owner chose option A; route, PurchaseCreate and monetization router deleted; referrals use enable_referrals (T043 done 2026-10-30). |
| OQ-12: How does account deletion interact with the append-only ledger and referral rows? | `A_anonymize_keep` (confidence 1.0) (a lawyer must confirm) | Anonymize the user (strip PII), keep ledger and referral rows. Matches spec recommendation; preserves financial records, needs an anonymization routine and account-deletion route. Lawyer to confirm retention periods. |
| OQ-13: What legal terms, refund policy and consumer-protection obligations apply to selling credits and subscriptions? (LAWYER MUST CONFIRM ALL OPTIONS; this is not legal advice.) | `D_defer_sales` (confidence 0.95) (a lawyer must confirm) | Launch with admin grants only (no sales) until counsel drafts terms. Zero legal exposure now; delays revenue. Matches OPEN_DECISIONS 'D now'. |

## 007-evaluation-staging-enablement

| Question | Decision | Option chosen |
|---|---|---|
| OQ-007-1: Rollback by ENABLE_CLEF_PROVIDER=false: does it hold? | already answered | RESOLVED: adapter inert with flag off (CLEF_DISABLED, no network call); failed provider persists no receipt. |
| OQ-007-2: How is an approval bound to a person? | already answered | Built: Ed25519 signature over receipt_sha256 against a committed approver allowlist with strict revocation, plus chain replay (T080, T081 done); approved_by is a key id. Only operator tasks remain: generate the key pair offline and commit the public key (T082), sign the receipt (T083). The spec text still says 'open'; stale. |

## 008-dual-path-f5-design-receipts

| Question | Decision | Option chosen |
|---|---|---|
| OQ-008-1: Rollback by reverting the two list pages: does it hold? | already answered | RESOLVED: alias routes predate this feature (R3). |
| OQ-008-2: Must the walkthrough run against staging only? | already answered | Yes: allowlist of exactly 'staging'. T070 done 2026-10-29; flags_test_mode_failures fails with SERVER_ENVIRONMENT_NOT_STAGING and expected_environment is Literal['staging']. Spec status table row SC-001 'Partial' is stale. |

## What follows

**Engineering work these decisions unblock (PRs to follow):**

- 003 OQ-9: apply compares the dry run's `inputs_hash` as well as the plan hash, and a retirement must carry evidence.
- 003 OQ-3: a committed paid-fetch approvals file that the crawler checks before any paid fetch.
- 003 OQ-2: hand-check the nine maker-vs-v1 HP disagreements against maker pages, then add reviewed corrections.
- 002 OQ-10: lock the publication row so concurrent owner and admin actions serialize.
- 002 OQ-13: rate-limit and de-duplicate publication reports.
- 001 OQ-13 and 002 OQ-15: threat-model sections for the evidence boundary and the public publishing surfaces.
- 001 OQ-10: user-initiated image deletion; the expiry job waits for 006 T101b and T101c.
- 006 OQ-3: record evidence receipts for T030, T040b, T050b and T055b, and close them.
- 004 OQ-12: account deletion that anonymizes the user and keeps the ledger and referral rows (a lawyer must confirm retention).
- Spec text only: 003 OQ-4 (sealed seed gets its own state), OQ-5 (plan-hash apply is the verification ritual) and OQ-7 (coverage stays raw counts); 005 OQ-4 (routing target stays empty) and OQ-5 (thresholds equal the baseline); 002 OQ-6, OQ-7 and OQ-11 (unchanged).

**How the commerce decisions fit together.** 004 OQ-13 chose to defer sales until counsel drafts terms. Machines B and C (T046, T049) and resolve (T048b) are therefore not built now, even though OQ-2, 3, 4, 5, 7 and 8 fix how they will work. (Correction 2026-11-06: they were built on 2026-11-02 behind flags that stay off, and sales are still deferred.) The prices in OQ-1 were ratified only provisionally (confidence 0.29) and stay unused until sales start. (Owner decision 32, 2026-11-04: not ratified.)

**Only the owner can do these:**

- 006 OQ-1 and OQ-2: protect the `production` environment and use a separate staging Cloudflare token (T101b).
- 003 OQ-1: email the makers for spec sheets on the 17 unsourced widths.
- 003 OQ-8 and 002 OQ-14: confirm the specs' inferred claims, and supply the truncated source text.
- D13: the production deploy of #183–#186.
- 004 OQ-13 and every legal item: counsel.
