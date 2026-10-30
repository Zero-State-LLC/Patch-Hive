# Open decisions: follow-up research (2026-10-30)

A second pass on [OPEN_DECISIONS_2026-10-30.md](OPEN_DECISIONS_2026-10-30.md), against `main` at `9b94d1e`. It gathers the evidence the first brief said the owner would need. Two read-only research passes: catalog and rig (decisions 9, 10, 11), and product and ops (decisions 1, 4, 6, and OQ-10 and OQ-13 from decision 12). OBSERVED means read in the checkout, on GitHub or on a public page; INFERRED means reasoned; PROPOSED means for owner sign-off. Nothing here queried production data. The only network reads were four free GETs to maker pages (all HTTP 200, no block) and public pricing and documentation pages.

## What changed since the first brief

| # | Decision | First brief | After this research |
|---|---|---|---|
| 1 | Provider purchases | Build neither yet; credit packs first at launch | Unchanged. PROPOSED starting prices: one-time packs of $5 for 25 credits and $15 for 100, USD, no subscriptions or "unlimited" until per-export cost is measured |
| 6 | Prod workflow protection (T101) | `production` environment, main only, owner as reviewer | Unchanged, with a gotcha: `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are shared by staging and prod runs of `edge-secrets.yml`, so moving them into `production` needs a separate staging token. Leave "prevent self-review" off while solo, or it deadlocks |
| 9 | 218 unsourced HP values | Triage | Unchanged, with numbers: 157 have an official-page citation, 28 retailer only, 33 none. 12 more disagreements with maker-sourced values need a hand check (list below) |
| 10 | T035 jumper pages | Approve with a 50-credit cap | **Run it free, no cap.** Sample 4ms and Dave Jones Design pages return the per-setting draws in plain HTML (about 45 GETs, 0 credits) |
| 11 | Rig scores | Define `routing_flex_score` and `performance_density_index` | Formulas refined (below), but **only 3 of about 3,600 live catalog modules carry `io_ports`**, so both scores would be NOT_COMPUTABLE for almost every real rig until a port-data pass exists |
| 12 | OQ-10 retention, OQ-13 threat model | Owner needed | PROPOSED drafts below. Found a gap: evidence-image expiry (`expire_image_assets` in `backend/evidence/retention.py`) has no caller, so uploaded images are never cleaned up |
| 4 | Publishing (OQ-6) | Keep off | Unchanged: no issue, doc or roadmap entry asks for a gallery |

The twelve further HP disagreements (v1 value vs a maker-sourced value; confirm each by hand, since slug matching can pair variants):

| Module | v1 | Maker-sourced |
|---|---|---|
| ALM Akemie's Castle | 18 | 38 (staging and prod already hold 38) |
| Befaco Hexmix VCA | 12 | 14 |
| Intellijel Quadrax | 12 | 14 |
| Intellijel Rubicon 2 | 14 | 20 |
| Erica Synths Fusion VCO | 16 | 24 |
| Doepfer A-110-1 | 8 | 10 |
| Joranalogue Generate 3 | 16 | 12 |
| Make Noise DPO | 30 | 28 |
| Make Noise Morphagene | 18 | 20 |
| Qu-Bit Chord V2 | 12 | 14 |
| Qu-Bit Data Bender | 12 | 14 |
| ADDAC200PI | 2 (official page cited) | 4 (maker crawl v1 only) |

## Catalog and rig (decisions 9, 10, 11)

### Decision 11: rig scores

**`io_ports` is almost empty in committed catalog data.** Across `seed-phase2-v1.json`, `seed-phase3-v1.json` and `overlays/catalog-additions-v1..v6.json` there are 4,043 unique modules (3,595 after the 448 retirements). Exactly 3 carry `io_ports`, all in the hand-curated `full_spec_modules` of `seed-phase2-v1.json`: Noise Engineering Basimilus Iteritas Alter (3 ports), Make Noise Maths (2), Instruo arbhar (2). That is about 0.08% of live rows. By brand share: Noise Engineering 1/71, Make Noise 1/62, Instruo 1/11, every other brand 0. No crawl or power/depth overlay has any port, jack, knob or control field. `modules.io_ports` (`backend/modules/models.py:51`) defaults to `[]`, so "no ports" and "unknown" look the same. The only richer port data is the 11 hand-written fixtures in `scripts/seed_golden_demo.py` (9 with ports, Doepfer A-110-1 and Befaco Even VCO empty).

The existing data also contradicts itself. The catalog's Maths has 2 ports, the demo fixture's Maths has 5, and the real module has far more jacks (INFERRED). A port count from this data undercounts.

**Prototype** (declared ports, demo fixtures; flex = 1 − e^(−x/k), x = ports per module):

| Rig | Modules | HP | Ports | Ports/module | Flex k=4 | Flex k=8 | Ports/HP |
|---|---|---|---|---|---|---|---|
| Small: Plaits, Ripples, Quad VCA | 3 | 32 | 15 | 5.00 | 0.713 | 0.465 | 0.469 |
| Medium: first 8 fixtures | 8 | 120 | 38 | 4.75 | 0.695 | 0.447 | 0.317 |
| Large: all 11 (2 have empty ports) | 11 | 144 | 40 | 3.64 | 0.597 | 0.366 | 0.278 |
| Catalog-only: the 3 real catalog modules | 3 | 48 | 7 | 2.33 | 0.442 | 0.253 | 0.146 |

- **Separation:** `performance_density_index` separates the rigs (0.47 down to 0.28). `routing_flex_score` barely does between small and medium (0.713 vs 0.695 at k=4), because it is a per-module average and real modules have 4–6 ports here. Sampled from the modules above; not a statistical claim.
- **k=4 saturates early.** Real modules probably have 6–12 jacks (INFERRED), which would push k=4 above 0.8 for almost every rig. k=8 leaves headroom.
- **The large rig is deflated by the two empty-port modules** (3.64, not about 4.7 on the other nine). Today's `runes.py:163` counts those as zero ports without saying so.

**Recommended formulas** (new metrics version, formula written into `confidence_notes`):
- `routing_flex_score = round(1 − exp(−(total_ports / module_count) / 8), 4)`.
- `performance_density_index = round(total_ports / total_hp, 4)`, unitless "ports per HP". Controls (knobs, switches) aren't stored anywhere, so port-only. Say so in the notes.
- **NOT_COMPUTABLE rule:** `routing_flex_score` is NOT_COMPUTABLE if any module has missing or empty `io_ports`, unless it is explicitly a blank or passive panel (category UTIL "Blank Panel"). `performance_density_index` is NOT_COMPUTABLE under the same rule or if any HP is null or 0. Never substitute zero.
- Put the covered fraction (modules with ports / modules) in `confidence_notes`.

**Consequence:** with the committed catalog, almost every real rig returns NOT_COMPUTABLE for both scores, so `suggest_layouts` stays blocked in practice. Option 2 is correct but only pays off after an `io_ports` data pass (nothing scheduled). INFERRED: a hand-built set of ports for the most common ~100 modules would be the cheapest route.

### Decision 10: T035 jumper pages

**The list is not enumerated in the repo.** `specs/003-catalog-dataset-pipeline/tasks.md:48` and `research.md:53` give the shape only. `hermes-research/maker-crawl-v2.json` holds 44 4ms rows (`p.php?p=…&c=5` URLs), 2 Dave Jones Design rows (`jonesvideo.com/prod_otool.html`, `prod_mvip.html`) and 1 Velectronic row (`/products/associative-quadruple-envelope`). The 42 "live" 4ms count presumably excludes retired and non-module rows such as the Row Power products (INFERRED). `provenance/maker-crawl-v2-jumper-fix-v1.json` already names Otool (+12V 80 mA) and A-Envelope (+5V 170 mA) as the cleared fields.

**Free fetch works.** I made 4 plain GETs (3 4ms and 1 Dave Jones Design), 2 s apart, no block or CAPTCHA, HTTP 200 each, per-setting text present in raw HTML (not JS-rendered):
- 4ms Spherical Wavetable Navigator (`p=820`, 49.6 KB): "+12V: 185mA with LED PWR jumper set to 12V; 107mA with LED PWR jumper set to 5V -12V: 30mA +5V: not used with LED PWR jumper set to 12V; 60mA with LED PWR jumper set to 5V".
- 4ms Mesa (`p=1112`, 17 KB): "+12V: 180mA max -12V: 36mA max +5V: not used". No jumper, so no T035 work.
- 4ms Sampler (`p=1062`, 22 KB): "+12V: 145mA -12V: 41mA +5V rail: not used". No jumper.
- Dave Jones Design Otool (`prod_otool.html`, 6.5 KB): "Power requirements: 80ma +12v 22ma -12v -or- 12ma +12v 70ma +5v 22ma -12v" plus "It has a jumper for internal or external 5 volt source."

Velectronic was not fetched (request budget). **The paid cap looks unnecessary.** A free run is about 45 GETs at 2 s spacing (about 2 minutes, 0 credits) plus a parser for "X mA with … jumper set to Y" phrases and a hand review of the roughly 6 odd phrasings (INFERRED). Note `tasks.md` T026 says 4ms needed a paid render pass; the pages are server-rendered now, or were all along. I did not check robots.txt or terms; do that before the run. Recommend replacing "approve T035 with a 50-credit cap" with "run T035 free; no cap".

### Decision 9: the 218 remaining unsourced v1 HP values

From `overlays/module-catalog-hp-v1.json` (221 entries) minus the 3 corrected in #153 (Junction, A-101-3, A-137-2; the fourth finding, Sovage CHICANE, was never in v1). Citations from `hermes-research/hp-enrichment-batch{1,1-retry,2,3}-results.filtered.json`; comparison values from `maker-crawl-v1/v2.json`, `module-catalog-hp-v2.json` and `catalog-additions-v1..v6.json`, matched by slug.

| Citation | Count | Agree with a maker value | Disagree | No other value |
|---|---|---|---|---|
| Official page | 157 | 29 | 1 | 127 |
| Retailer only | 28 | 6 | 0 | 22 |
| None | 33 | 17 | 11 | 5 |
| Total | 218 | 52 | 12 | 154 |

All 185 enrichment results carry the same HP as v1 (they are v1's own lineage, so not independent). Official domains: doepfer.de 41, addacsystem.com 26, bastl-instruments.com 26, befaco.org 14, makenoisemusic.com 14, intellijel.com 9, cwejmanmusic.com 7, ericasynths.lv 7, instruomodular.com 6, mutable-instruments.net 6, expert-sleepers.co.uk 1.

**No-citation remainder (33):** Mutable Instruments 7, Make Noise 5, Doepfer 4, Intellijel 3, ALM 2, Befaco 2, Erica 2, Joranalogue 2, Noise Engineering 2, Qu-Bit 2, Xaoc 2. Only 5 have no value anywhere: Befaco Rampage (18), Doepfer A-140 (8), Make Noise Strega (45), Mutable Instruments Ripples (8), Xaoc Zadar (10). Mutable Instruments is a discontinued brand with a public site, so those 7 are likely easy to cite.

**Further disagreements (12; v1 value first, then the maker-sourced value):**
- ALM Akemie's Castle: 18 vs 38 (crawl v2, hp-v2 and additions-v3 all say 38)
- Befaco Hexmix VCA: 12 vs 14
- Intellijel Quadrax: 12 vs 14
- Intellijel Rubicon 2: 14 vs 20
- Erica Synths Fusion VCO: 16 vs 24
- Doepfer A-110-1: 8 vs 10
- Joranalogue Generate 3: 16 vs 12
- Make Noise DPO: 30 vs 28
- Make Noise Morphagene: 18 vs 20
- Qu-Bit Chord V2: 12 vs 14
- Qu-Bit Data Bender: 12 vs 14
- ADDAC200PI: 2 (official-cited in enrichment) vs 4 (maker-crawl-v1 only)

Eleven have no citation and `catalog-additions-v1` says "verified against manufacturer pages" (`policy`), so they look wrong in v1 (INFERRED). ADDAC200PI is the only official-vs-crawl conflict; the crawl v1 row may be the other variant. All 12 need a hand check like the #152 four.

**v3 manifest effort (INFERRED):** the 157 official-cited values can be generated by script into a `correct`-style or confirm manifest (about S, one PR, plus a spot check of 10 pages). The 12 disagreements need hand review (about 1–2 hours of page reading). The 28 retailer-only and 33 no-citation: a free maker-page lookup like decision 10 would cover most; mark what remains `legacy_unsourced`. This supports option 3 or 4 without paid fetches.

## Product and ops (decisions 1, 4, 6, 12)

OBSERVED = read in the checkout, GitHub, or a public page (fetched 2026-10-29/30). INFERRED = reasoned. PROPOSED = for owner sign-off. Nothing here queried production data.

### 1. OQ-1 prices (decision 1)

**Candidates** (`STRIPE_INTEGRATION_PROMPT.md`): $4.99 = 25 credits per month, $14.99 = 100, $29.99 = unlimited; $0.20/credit with a $5 minimum. An export costs 3 credits (`backend/core/config.py:99`). OBSERVED.

**Comparables** (all public pages, not like-for-like):
- Etsy "Synth Documentation": a blank downloadable PDF patch sheet for one synth, $2.99 (etsy.com/market/synth_documentation, 2026-10-30).
- Splice Sounds: about 100 downloads for $12.99/mo (billed yearly), about 200 for $19.99/mo regular, i.e. roughly $0.10-0.13 per credit; unused credits roll over (splice.com/plans, 2026-10-29).
- PDFShift (HTML-to-PDF API, a cost floor, not a competitor): $9/mo for 500 credits, $0.04 per extra credit (pdfshift.io/pricing, 2026-10-29).
- Patch & Tweak, a modular book, EUR 75 (bjooks.com, found by search 2026-10-29). Not a direct comparable.
- No public pay-per-export tool for modular patch books was found. INFERRED: there is no price anchor for this exact product.

**What one export costs the user** (3 credits):

| Pack | Exports | Per export | Stripe fee (2.9% + 30c) | You keep | Per export kept |
|---|---|---|---|---|---|
| $4.99 / 25 cr | 8 (1 credit left over) | $0.60 | $0.44 (8.9%) | $4.55 | $0.57 (8 exports) |
| $14.99 / 100 cr | 33 | $0.45 | $0.73 (4.9%) | $14.26 | $0.43 |
| $29.99 unlimited | uncapped | $0.45 at 67 exports/mo, falling after | $1.17 (3.9%) | $28.82 | n/a |
| $5 minimum, $0.20/cr | 8 | $0.60 | $0.44 (8.9%) | $4.56 | $0.57 |

Stripe US standard pricing: 2.9% + 30c domestic cards, +1.5% international, +1% if currency conversion; refunds do not return the original fee; disputes $15. Add-ons: Billing 0.7% (pay as you go) for subscriptions; Stripe Tax from 0.5% per transaction where you are registered (no-code Checkout) or $0.50 (API), per its pricing page; Managed Payments (merchant of record) 3.5% on top (stripe.com/pricing, 2026-10-30). A single dispute costs 3 Core packs of fee income.

**Gaps in the candidates.**
- The spec text says credits are monthly, so the three prices are subscriptions. That drags in Billing, proration and tier rules (OQ-3, -4, -7, -8).
- "Unlimited" has no cost basis: per-export compute and storage have not been measured (INFERRED). The Studio tier loses to Pro for anyone under 67 exports a month and has uncapped cost above it.
- The 30c fixed fee makes anything under $5 inefficient, which is why the $5 minimum is sensible.

**PROPOSED starting structure.** Launch one-time credit packs only (no subscriptions), USD: $5 for 25 credits and $15 for 100 credits (about $0.60 and $0.45 per export). Drop "unlimited" and the subscription tiers until usage data exists. Keep the 3-credit export price, and consider one small free grant so a user can see a first book. INFERRED: against a $2.99 blank sheet, a finished book at $0.45-0.60 leaves room to raise prices; test before you cut them.

**Only the owner can decide:** currency (USD only vs local pricing; Adaptive Pricing adds a 2%+ conversion charge); tax and VAT (do nothing and accept liability, Stripe Tax from 0.5%, or Managed Payments at 3.5%; INFERRED: VAT on digital goods to EU buyers applies from the first sale, so a US-only launch or Managed Payments avoids it); refund policy (unused credits only, expiry, whether a failed export auto-refunds credits, whether a Stripe fee is eaten); whether credits expire; the terms of sale; and who is the seller of record.

### 2. OQ-10 retention and OQ-13 threat model (PROPOSED for owner sign-off)

**What they mean.** Spec 001 R8 leaves open (OQ-10) how long evidence, OCR output and user overlays are kept and who can see them, and (OQ-13) whether the provider evidence boundary needs an ADVERSARY threat model. Spec 001 says user overlays and rig photos "may be personal" (INFERRED). ADR 0001 makes runs, libraries, patches, receipts, manifests, ledger entries and audit events append-only; only overlays mutate.

**Retained today** (models and code):
- Evidence images: `image_assets` has `retention_days` (default 30; a client can send 1-365, `evidence/routes.py:130`), `retention_expires_at`, `deleted_at`. `expire_image_assets` soft-deletes and purges bytes. **Gap (OBSERVED): no non-test code calls it, so nothing runs it.** Expiry is only enforced at access time.
- Canon runs/patches/libraries/receipts/manifests, rig revisions: append-only, FKs `RESTRICT`.
- Canon exports (`canonical_exports`) and artifact bytes in object storage; ledger and admin audit events (append-only; ledger user FK `RESTRICT`).
- Webhook events: `stripe_event_records` keeps only `payload_hash`, status, reason code, not the payload.
- Decision receipts and keys: signed, append-only.
- Legacy `users`, `credits_ledger`, `exports`, `referrals` use `ondelete=CASCADE` on user deletion (a conflict with append-only ledgers; this is spec 001 OQ-02). Refresh tokens carry `expires_at` and `revoked_at`.

**PROPOSED retention table**

| Data | Keep | Why |
|---|---|---|
| Normalized evidence images | 30 days default, max 90 (cap the form at 90); user-initiated delete at any time | Photos may show homes, serials, people |
| OCR/provider output | Same as its image; derived rows keep hash and lineage but drop raw text at expiry | Untrusted text; privacy |
| Rig/run/patch/library/receipts/manifests | Life of the account, then anonymise (null user link) | Append-only; lineage |
| Canon exports + artifact bytes | 1 year after creation, then delete bytes, keep the row and hashes | Cost; the row proves what was sold |
| Credit ledger, Stripe event records, admin audit events | 7 years (INFERRED; confirm with an accountant) | Financial records; never deleted |
| Decision receipts and keys | Indefinite (small) | Verifies old signatures |
| User overlays (notes, favorites) | Until the user deletes them or the account closes | Mutable by design |
| Refresh tokens | Delete rows 30 days after expiry/revocation | Hygiene |
| Application logs | 30 days (INFERRED: not documented) | Minimise |

Account deletion: delete overlays and evidence; null `user_id` where the schema allows; keep ledger rows. Needs a migration to change `CASCADE` ledger FKs to `RESTRICT`/`SET NULL`. PROPOSED. Tasks: schedule `expire_image_assets` (a Worker cron or CI job), cap the form, add a deletion route.

**One-page threat model outline (PROPOSED)**
- **Assets:** user accounts and tokens; rig photos and OCR text; the credit ledger and Stripe state; signed decision receipts and the approver key; the catalog dataset; prod DB/R2/Cloudflare credentials; the Design Engine IP.
- **Actors:** anonymous visitor; authenticated abusive user; malicious uploader; hostile vision provider or poisoned provider output; replayed or forged webhook sender; compromised CI or contributor branch (the repo is public); stolen signing key; insider/admin error.
- **Entry points:** image upload; provider response parsing; `/api/canon/*` including exports and idempotency keys; Stripe webhook endpoint; auth/refresh; admin routes; dispatched workflows with prod secrets; edge Worker and R2.
- **Top risks, existing mitigations, gaps:**
  1. Malicious image/OCR text (injection, decompression bombs). Mitigated: byte/dimension/pixel limits, scanner adapter, re-encode, EXIF stripped, strict Pydantic, provider output cannot claim `USER_CONFIRMED` (docs/SECURITY.md). Gap: production scanner not selected ("Use a production malware-scanning implementation").
  2. Credit abuse or double spend. Mitigated: idempotency per user, append-only ledger, `ck_canonical_exports_cost`. Gap: legacy purchase route (decision 2).
  3. Webhook forgery/replay. Mitigated: HMAC constant-time, timestamp tolerance, unique event ids, livemode gate. Gap: handlers unimplemented (`HANDLER_NOT_IMPLEMENTED`).
  4. Prod secret exposure through CI. Mitigated: dispatch-only, masked logs, counts-only artifacts. Gap: no environment protection (section 3).
  5. Stolen signing key / backdated receipts. Mitigated: strict revocation (#144). Gap: key-custody runbook (007 T082).
  6. Photo privacy: retention not enforced (cleanup never runs); third-party provider use needs consent text (SECURITY.md says not activated).
  7. Tenant isolation: owner checks on exports and evidence; no automated cross-user test list found (INFERRED gap).
  8. Supply chain: pinned deps, `pip-audit`, `npm audit`, CodeQL, SBOM; one temporary react-router exception.
- Sign-off needed: who the in-scope adversaries are, whether the provider boundary gets a separate ADVERSARY section in spec 001, and the retention numbers above.

### 3. T101 production protection (decision 6)

**Confirmed (GitHub docs, "Managing environments for deployment", fetched 2026-10-30):** environments, environment secrets and protection rules (required reviewers, wait timer, deployment branches) are available in public repos on all current plans. The repo is public (`gh api`: `visibility: public`; org plan `team`). Today its environments are `copilot` and `github-pages`, both with no rules. Setup needs repo admin; there are two admin collaborators, so a second reviewer is possible.

**Steps (Settings UI):** repo Settings, Environments, New environment, name `production`, Configure. Then: tick Required reviewers and add yourself (up to 6; one approval is enough); leave **Prevent self-review** off if you are the only reviewer, because with it on, the person who dispatches a run cannot approve it, which deadlocks a solo operator (it works only with a second reviewer); untick "Allow administrators to bypass configured protection rules"; Deployment branches, Selected branches and tags, add rule Branch `main`; add environment secrets `PATCHHIVE_DATABASE_URL_PROD` and the production Cloudflare token; save. Then delete the same repo-level secrets, so only the environment holds them. Optionally create a `staging` environment (no reviewers) and move the staging secrets too.

**Workflow YAML (PROPOSED).** Add one line to the single job in each file:
- `db-migrate.yml` (job `migrate`): `environment: ${{ inputs.target == 'prod' && 'production' || 'staging' }}`
- `db-load.yml` (job `load`): `environment: ${{ inputs.env == 'prod' && 'production' || 'staging' }}`
- `edge-secrets.yml` (job `secrets`): `environment: ${{ inputs.env == 'production' && 'production' || 'staging' }}` (note its prod value is `production`, not `prod`).

`jobs.<id>.environment` accepts the `inputs` context. The input that selects prod: `target` (db-migrate), `env` (db-load, value `prod`), `env` (edge-secrets, value `production`).

**Secrets to move:** `PATCHHIVE_DATABASE_URL_PROD` (db-migrate, db-load, edge-secrets) and Cloudflare credentials. Repo secrets today: `CLOUDFLARE_API_TOKEN`, `PATCHHIVE_DATABASE_URL_PROD`, `PATCHHIVE_DATABASE_URL_STAGING`, `RELEASE_PLEASE_TOKEN`; variable `CLOUDFLARE_ACCOUNT_ID`.

**Gotchas.**
- `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are shared by staging and prod runs of `edge-secrets.yml`. If you move them into `production`, a staging run cannot read them. Either create a second scoped token for `staging` (recommended; it also stops one token reaching both) or keep a repo-level copy, which defeats the protection.
- An environment secret overrides a repo secret of the same name; a job without `environment:` cannot see environment secrets, so leftover repo-level prod secrets keep working until deleted. Delete them last, after one approved test run.
- Staging jobs will now have `environment: staging`; if that environment does not exist, GitHub creates it unprotected on first run.
- The `${{ secrets[...] }}` lookups by name keep working as long as the job's environment holds the name.
- Branch protection (code-owner review with `enforce_admins`, CODEOWNERS naming a team without access) is separate; fix #111/CODEOWNERS first. The main-only rule blocks dispatches from other branches, which is the point.
- Concurrency groups and the existing `permissions: contents: read` are unaffected.

### 4. OQ-6 publishing (decision 4)

**Demand evidence: none.** Only 2 issues exist in the repo (#95, #21) and neither concerns publishing. `docs/ROADMAP.md:44,193` lists publishing as legacy/off and a "marketplace and public publishing network" as a non-goal-level item; the README calls PatchHive "not a preset marketplace". `CURRENT_STATE.md` lists publishing only as awaiting this decision. The pages are quarantined in `frontend/src/legacy/` (not imported by `App.tsx`). No user demand is recorded anywhere I could read.

**Option 3 concretely needs** (INFERRED, effort M):
- Migration: a nullable `publication_exports.canonical_export_id` (FK to `canonical_exports.id`, `RESTRICT`), plus a stored "book validated" flag or hash on `canonical_exports`. Today the `validate_book` result is only a file in the pack (`validation/book.json`, `engine.py:63`), not a column.
- `backend/publishing/routes.py`: `POST /me/exports` accepts `canonical_export_id`, checks the caller owns it, status is fulfilled, and validation passed; `_bound_to_validated_book()` (line 303) checks that link instead of returning `False`. Keep `manifest_hash` equal to `pack_manifest_hash`.
- Public downloads (`/p/{slug}/download/{artifact_type}`) stream the canon artifact via scoped URLs; license and unlisted default stay.
- Frontend: re-route the quarantined publish pages, mount with `ENABLE_LEGACY_PUBLISHING` (rename the flag) and a moderation check.
- Tests for ownership, unvalidated refusal and takedown; a content-retention rule for published books (see section 2).
- Recommendation unchanged: leave it off until someone asks for a gallery.
