# CURRENT_STATE

**Authoritative as of:** 2026-11-03  
**Branch pin:** `main` on `Zero-State-LLC/Patch-Hive`  
**HEAD:** `6c234a6` (#240, release 0.3.0-alpha.7); everything through #256 is merged, including the frontend redesign and its ten follow-up slices (#215–#238), the commerce work (#209–#224) and the Project #8 Backlog remediation (#241–#256). Database migrations are at head `20261102_export_fair_use` on both (staging run [41587791401](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/41587791401), production run [41627413887](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/41627413887)); alpha.7 adds none. **Staging and production both run `6c234a6`**, deployed and smoke-tested 2026-11-03: staging API Worker `1b2244cc` and frontend `1001f50a`, production API `4b92ecd0` and frontend `4a6c6ace`. `/health/ready` reports 0.3.0-alpha.7 with `database: ok` on both, and the live smoke suite (#244, `npm run test:smoke`) passes 9/9 on both. Payments stay in test mode on both; production sets no feature flags.  
**Recent work (2026-10-28):** gap-analysis fixes for specs 001–005 and P0/P1 security (#82–#105); Cloudflare edge for staging and production (#83–#87, #107); short-lived tokens, refresh cookie and an enforced CSP (#99, #100, #113); prod catalog load, Products page, category fill and catalog tombstones (#112–#116). 2026-10-29: slices A1–A5 (#118, #119, #121–#123) and a second retirement (#120); spec research (#134); lifecycle and decision fixes (#135); slices B1–B5 (#136–#140) and C1–C5 (#142–#146).  
**Open PRs:** none.  
**Board:** [Project #8](https://github.com/orgs/Zero-State-LLC/projects/8), mirrored in [docs/KANBAN.md](docs/KANBAN.md).  
**Open owner decisions:** [docs/evidence/OPEN_DECISIONS_2026-10-30.md](docs/evidence/OPEN_DECISIONS_2026-10-30.md) (13 decisions with recommendations, plus [follow-up research](docs/evidence/OPEN_DECISIONS_2026-10-30_RESEARCH.md); supersedes [the 2026-10-28 note](docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md)). Decided and done 2026-10-30: legacy purchase route deleted (#150), routing target empty by default (#151), strict key revocation kept (#149), HP overlay precedence fixed (#152), prod workflows given a `production` environment (#160; moving the secrets is the owner's step T101b), two rig scores defined with the other four NOT_COMPUTABLE (#161), T035 jumper pages fetched free (#163), unsourced HP values triaged (#164), jumper-dependent power loaded as `power_configs` (#166), 26 more legacy HP values re-sourced (#167), Otool's jumper settings labelled from its maker manual (#170), the SMR and VCA Matrix settings and the A-155 width decided and loaded (#172; reviewed HP corrections may now run to 84 HP), `evidence.expire` scheduling deferred to 006 T101c after T101b, every remaining unsourced HP value checked against reachable maker sources (#174: 4 re-sourced, Dixie II corrected to 6 HP, 57 left; then retailer evidence for those 57, #180: 40 agree and read `retailer_observed`).  
**Next slices:** [docs/evidence/NEXT_SLICES_2026-10-28.md](docs/evidence/NEXT_SLICES_2026-10-28.md) (A1–A5 done; status updated 2026-10-29).  
**Decision research (2026-10-29):** one `research.md` per spec, 001–008, each with an "Implementation status (2026-10-29)" table in its `spec.md` and gap-closure tasks in its `tasks.md`. Receipt signing (007 R1) is built (#144); the approver key is an operator step (007 T082). The decisions awaiting the owner: the provider purchase machines (004 R1), the 221 unsourced v1 HP values (003 R7), deleting the legacy purchase route (004 R5, OQ-11), whether publishing comes back (002 OQ-6, T033), the rig score formulas (001 OQ-11) and GitHub environment protection for prod workflows (006 R2).  

**Alpha tag lineage:** `v0.3.0-alpha` (late alpha — **not** production); latest pre-release `v0.3.0-alpha.5` (2026-10-30)

### Recent merges (OBSERVED, 2026-10-30 to 11-02)

| PR | Result |
|----|--------|
| [#211](https://github.com/Zero-State-LLC/Patch-Hive/pull/211) | 004 T048b: Admin `POST /api/admin/commerce/events/{id}/resolve` re-fetches the Checkout Session and runs Machine B fulfillment once, with one audit record; fails closed otherwise |
| [#210](https://github.com/Zero-State-LLC/Patch-Hive/pull/210) | 004 T047: a referred user's first provider purchase writes one referral reward (duplicate and concurrent deliveries write none more) |
| [#209](https://github.com/Zero-State-LLC/Patch-Hive/pull/209) | 004 T046: Machine B credit checkout behind `ENABLE_CREDIT_CHECKOUT` (off), test keys only; webhook fulfillment credits once on `paid`; migration `20261102_credit_checkout` |
| [#208](https://github.com/Zero-State-LLC/Patch-Hive/pull/208) | 007 T010b: corpus photos must name maker and module; [run record](docs/evidence/CORPUS_PHOTO_SEARCH_2026-11-02.md): 300 paid searches spent, 2 usable images |
| [#207](https://github.com/Zero-State-LLC/Patch-Hive/pull/207) | 006 OQ-3: operator-task receipts for 2026-11-02; no task closed (evidence incomplete) |
| [#206](https://github.com/Zero-State-LLC/Patch-Hive/pull/206) | 007 T010b: `scripts/vision/find_corpus_photos.py` and approval `corpus-photos-2026-11` (300 context.dev searches) |
| [#205](https://github.com/Zero-State-LLC/Patch-Hive/pull/205) | CURRENT_STATE: 2026-11-02 migrations and deploys |
| [#204](https://github.com/Zero-State-LLC/Patch-Hive/pull/204) | 007 T082: approver public key `approver-2026-11` committed to the allowlist |
| [#203](https://github.com/Zero-State-LLC/Patch-Hive/pull/203) | 007 T084: `scripts/staging/run_007_evaluation.py` runs the evaluation and enablement chain (freeze, run, propose, approve, enable-staging, pin, sign, verify); a dry run can never be signed |
| [#202](https://github.com/Zero-State-LLC/Patch-Hive/pull/202) | An uploaded photo reaches the decision route: candidates carry the stored evidence record id (006 T060b blocker) |
| [#201](https://github.com/Zero-State-LLC/Patch-Hive/pull/201) | [Owner action guide](docs/evidence/OWNER_ACTIONS_2026-11-02.md): every owner-only item with exact steps |
| [#200](https://github.com/Zero-State-LLC/Patch-Hive/pull/200) | 003 OQ-2: maker quotes for eight hand-checked HP values (`module-catalog-hp-v7`), all equal to the stored values; Akemie's Castle unconfirmed |
| [#198](https://github.com/Zero-State-LLC/Patch-Hive/pull/198) | 003 OQ-9: a catalog apply needs the dry run's `inputs_hash` as well as `plan_hash`; retirements need evidence |
| [#197](https://github.com/Zero-State-LLC/Patch-Hive/pull/197) | 002 OQ-10, OQ-13: publication rows lock on transitions; reports rate-limited and de-duplicated |
| [#196](https://github.com/Zero-State-LLC/Patch-Hive/pull/196) | 003 OQ-3: paid catalog fetches need a committed approval (`fetch-approvals.json`, no entries yet) |
| [#195](https://github.com/Zero-State-LLC/Patch-Hive/pull/195) | Threat-model sections for the provider/evidence boundary (001) and public publishing surfaces (002) |
| [#194](https://github.com/Zero-State-LLC/Patch-Hive/pull/194) | 004 OQ-12: `DELETE /api/me` anonymizes the account and keeps the ledgers (migration `20261101_user_deleted_at`) |
| [#193](https://github.com/Zero-State-LLC/Patch-Hive/pull/193) | 001 OQ-10: a user can delete an evidence image; requested retention capped at 90 days |
| [#190](https://github.com/Zero-State-LLC/Patch-Hive/pull/190) | 006: T030 and T050b closed with evidence receipts; T055b and T040b wait on the R2 check |
| [#189](https://github.com/Zero-State-LLC/Patch-Hive/pull/189) | 005 T086: NVIDIA vision provider beside Clef (off by default, refused in production, receipt-gated) |
| [#188](https://github.com/Zero-State-LLC/Patch-Hive/pull/188) | [Jev decisions](docs/evidence/JEV_DECISIONS_2026-11-01.md) on all open questions; seven provisional |
| [#182](https://github.com/Zero-State-LLC/Patch-Hive/pull/182) | T010 transition tests for specs 001–004; 183–186: verified-purchase referrals, admin reject of unresolved payment events, the 005 receipt gate and signed readiness pins |
| [#160](https://github.com/Zero-State-LLC/Patch-Hive/pull/160) | `db-migrate`, `db-load` and `edge-secrets` jobs run in a `production` or `staging` environment (006 T101a); nothing changes until the owner moves the secrets (T101b, steps in `specs/006-cloudflare-edge-clef/DEPLOY_NOTES.md`) |
| [#161](https://github.com/Zero-State-LLC/Patch-Hive/pull/161) | `routing_flex_score` and `performance_density_index` defined (`canon-metrics.1.2.0`); NOT_COMPUTABLE whenever a module lacks `io_ports`, which today is almost every real rig |
| [#162](https://github.com/Zero-State-LLC/Patch-Hive/pull/162) | `/health` reports the release version from `backend/pyproject.toml`; `python -m evidence.expire` (dry run unless `--apply`) retires expired evidence images; not scheduled |
| [#163](https://github.com/Zero-State-LLC/Patch-Hive/pull/163) | T035: 42 jumper-dependent maker pages fetched free into `receipts/t035-jumper-power.json` (11 with per-jumper draws); no catalog value changed; T034 consumes it |
| [#164](https://github.com/Zero-State-LLC/Patch-Hive/pull/164) | T038 triage: 106 v1 HP values re-sourced against their own maker pages (`module-catalog-hp-v3`), 4 corrected (`maker-corrections-v3`), 88 marked `hp_source = legacy_unsourced` (migration `20261030_catalog_hp_source`); loaded to staging and prod |
| [#186](https://github.com/Zero-State-LLC/Patch-Hive/pull/186) | 008 T071: `pin_readiness_docs` requires the 007 receipt's approver signature and signs the `ReadinessPin` with the approver key under its own signing domain, so `pinned_by` is a key id; the `operator_pin` guard and `beta_eligible` verify both signatures. Not deployed (no runtime route) |
| [#185](https://github.com/Zero-State-LLC/Patch-Hive/pull/185) | 005 T080: outside development and test, any decision flag or provider needs a signed 007 receipt naming the provider and policy version (`DECISION_ENABLEMENT_RECEIPT_PATH`, `DECISION_ENABLEMENT_SIGNATURE_PATH`): startup refuses and the decision route answers 409 `ENABLEMENT_RECEIPT_REQUIRED`. Staging sets no decision flags, so nothing running changes. Not deployed |
| [#184](https://github.com/Zero-State-LLC/Patch-Hive/pull/184) | 004 T048 (reject half, OQ-5 recommendation): an Admin can reject an `unresolved` provider event with a reason (`rejected`, no grant, one `CanonicalAdminAuditEventRecord`; a conditional update so a reject happens once); admin readers list unresolved events. Resolve split to T048b after T046. Adds [commerce blocker research](docs/evidence/COMMERCE_BLOCKERS_RESEARCH_2026-11-01.md). Not deployed |
| [#183](https://github.com/Zero-State-LLC/Patch-Hive/pull/183) | 004 FR-033: `record_purchase` refuses an unverified purchase before writing, so a client-reported purchase cannot reward a referral. No deployed route records unverified purchases. Not deployed |
| [#182](https://github.com/Zero-State-LLC/Patch-Hive/pull/182) | T010 for specs 001–004: one table-driven transition test file per spec for every row the code implements; unimplemented rows recorded as drift in each T010 note (T010 stays open until T002) |
| [#181](https://github.com/Zero-State-LLC/Patch-Hive/pull/181) | Recorded #180 and its retailer-marker loads |
| [#180](https://github.com/Zero-State-LLC/Patch-Hive/pull/180) | FR-039 (owner decision 2026-11-01): one-off manual retailer lookups for the 57 `legacy_unsourced` HP rows (`module-catalog-hp-retailer-v1`, URL, verbatim quote and page hash each; hosts that answered 403 not used); 40 whose stored HP a retailer page states now read `hp_source = retailer_observed`, 6 disagree and 11 were not found, so 17 stay `legacy_unsourced`. HP itself unchanged. Loaded to staging and prod 2026-11-01 |
| [#178](https://github.com/Zero-State-LLC/Patch-Hive/pull/178) | Cockpit (black) and (golden) power (75 mA +12V, 4 mA -12V, 0 mA 5V) and depth (38 mm) filled from the maker's COCKPIT MK1 page (`module-power-depth-v15`; modulargrid-provenance-v1 had nulled them); loaded to staging and prod 2026-11-01 |
| [#176](https://github.com/Zero-State-LLC/Patch-Hive/pull/176) | Cockpit (golden) HP filled with 6 from the maker's COCKPIT MK1 page (`module-catalog-hp-v6`; modulargrid-provenance-v1 had nulled it); loaded to staging and prod 2026-10-31 |
| [#175](https://github.com/Zero-State-LLC/Patch-Hive/pull/175) | State record for #173, #174 and the HP v5 load |
| [#174](https://github.com/Zero-State-LLC/Patch-Hive/pull/174) | T039: all 61 marked HP values checked against maker pages, maker manuals and the maker's GitHub (plain GETs, no route around a block); `module-catalog-hp-v5` re-sources Cockpit (black), Metropolis, Mutamix and Dixie II, `maker-corrections-v6` corrects Dixie II 8 → 6 in both tables; 57 stay marked, each reason in tasks.md T039. Loaded to staging and prod |
| [#173](https://github.com/Zero-State-LLC/Patch-Hive/pull/173) | State record for #171, #172 and their loads |
| [#172](https://github.com/Zero-State-LLC/Patch-Hive/pull/172) | Owner decisions applied: `receipts/t034-owner-decisions.json` labels the SMR base setting "jumper not set to +12V" and stores the VCA Matrix's unit-less "80 max" as an unknown +12V draw (all 21 settings load); FR-038 lets reviewed HP corrections run to 84 HP and `maker-corrections-v5` sets the Doepfer A-155 4 → 50 in both tables; spec 006 T101c (daily `evidence.expire`) follows T101b. Loaded to staging and prod |
| [#171](https://github.com/Zero-State-LLC/Patch-Hive/pull/171) | State record for #168, #170 and the Otool load |
| [#170](https://github.com/Zero-State-LLC/Patch-Hive/pull/170) | T034: `receipts/t034-manual-labels.json` names a setting the product page leaves unlabelled, only from the maker's own manual; Dave Jones Otool's Internal 5v / External 5v settings loaded to staging and prod (19 settings for 11 modules). Research on the remaining decisions in `OPEN_DECISIONS_2026-10-30_RESEARCH.md` §5–7 |
| [#168](https://github.com/Zero-State-LLC/Patch-Hive/pull/168) | State record for #159, #166, #167 and the `9dbb5ba` redeploy |
| [#166](https://github.com/Zero-State-LLC/Patch-Hive/pull/166) | T034: `power_configs` table and `rack_modules.power_config_id` (migration `20261030_power_configs`); 17 per-jumper draws for 11 modules loaded from the T035 receipt and served at `/api/modules/{id}/power-configs`; settings whose unit or base the page leaves unstated were skipped for the owner |
| [#167](https://github.com/Zero-State-LLC/Patch-Hive/pull/167) | T039: 26 more legacy HP values confirmed on maker pages (`module-catalog-hp-v4`), Doepfer A-106-1 8→14 and A-138m 8→20 corrected (`maker-corrections-v4`); 62 values stay `legacy_unsourced` |
| [#159](https://github.com/Zero-State-LLC/Patch-Hive/pull/159), [#165](https://github.com/Zero-State-LLC/Patch-Hive/pull/165) | Release 0.3.0-alpha.5; state record for #160–#164 |
| [#147](https://github.com/Zero-State-LLC/Patch-Hive/pull/147), [#148](https://github.com/Zero-State-LLC/Patch-Hive/pull/148) | State refresh; decision brief for the 13 open owner decisions |
| [#111](https://github.com/Zero-State-LLC/Patch-Hive/pull/111) | CODEOWNERS names `@scrimshawlife-ctrl`; the `partner-agents` team no longer had repo access |
| [#149](https://github.com/Zero-State-LLC/Patch-Hive/pull/149) | Spec 007 research R1 describes the strict key revocation the verifier enforces |
| [#150](https://github.com/Zero-State-LLC/Patch-Hive/pull/150) | Legacy `POST /api/monetization/purchases` deleted (004 T043); referrals behind `ENABLE_REFERRALS`; the old `ENABLE_LEGACY_REFERRALS` key is accepted and ignored with a warning |
| [#151](https://github.com/Zero-State-LLC/Patch-Hive/pull/151) | `decision_routing_target` defaults to empty: failed decisions end UNRESOLVED until a review queue consumes ESCALATE |
| [#152](https://github.com/Zero-State-LLC/Patch-Hive/pull/152) | Maker-cited HP overlays fill before the unsourced v1 overlay |
| [#153](https://github.com/Zero-State-LLC/Patch-Hive/pull/153) | Reviewed HP corrections from maker pages: Acid Rain Junction 6→4, Doepfer A-101-3 10→30, A-137-2 10→14; loaded to staging and prod |
| [#154](https://github.com/Zero-State-LLC/Patch-Hive/pull/154) | The loader plans a `needs_reverify` clear only when the database would apply it, so a rerun plans nothing |

### Recent merges (OBSERVED, 2026-10-29)

| PR | Result |
|----|--------|
| [#134](https://github.com/Zero-State-LLC/Patch-Hive/pull/134) | Research for every open decision; specs 001–008 reconciled with the code; gap-closure tasks added |
| [#135](https://github.com/Zero-State-LLC/Patch-Hive/pull/135) | Catalog lifecycle: tombstoned rows refused, `needs_reverify` cleared once every flagged field is corrected (CHICANE cleared on staging and prod). Decisions: invalid packets escalate or stay unresolved; every provider goes through the guarded flow |
| [#136](https://github.com/Zero-State-LLC/Patch-Hive/pull/136) | Workflows: foreign pin-PR workflow removed, `actions: write` dropped, orphan R2 token revoked on failure |
| [#137](https://github.com/Zero-State-LLC/Patch-Hive/pull/137) | Rig: `allow_feedback` and `prefer_simple` honoured; the full IR is hashed |
| [#138](https://github.com/Zero-State-LLC/Patch-Hive/pull/138) | Book: unlisted by default, bounded gallery filter, wrapped cover disclaimer, manifest warnings |
| [#139](https://github.com/Zero-State-LLC/Patch-Hive/pull/139) | Commerce: append-only credit ledger (database trigger), live-mode gate, webhook secret rotation and race handling |
| [#140](https://github.com/Zero-State-LLC/Patch-Hive/pull/140) | Decision evaluation runs the candidate check; the walkthrough accepts staging only |
| [#141](https://github.com/Zero-State-LLC/Patch-Hive/pull/141) | Spec ticks for work shipped in #135 (003 T036/T037, 005 T081/T082) |
| [#142](https://github.com/Zero-State-LLC/Patch-Hive/pull/142) | Rig: the canon compiler runs on the generation path; one `RigMetricsPacket` per rig revision (scores `NOT_COMPUTABLE` until OQ-11) |
| [#143](https://github.com/Zero-State-LLC/Patch-Hive/pull/143) | Book: `validate_book` stage, plate page-count check, warnings in the stage receipt; publishing a draft refused until it is bound to a validated book |
| [#144](https://github.com/Zero-State-LLC/Patch-Hive/pull/144) | Evaluation receipts verified by replay and signed (Ed25519, committed allowlist, empty until the operator adds a key); readiness gates verify the receipt |
| [#145](https://github.com/Zero-State-LLC/Patch-Hive/pull/145) | Commerce: legacy balance route removed; every webhook event ends `processed`, `duplicate`, `unresolved` or `ignored` |
| [#146](https://github.com/Zero-State-LLC/Patch-Hive/pull/146) | Decisions: idempotency checked before the provider call (advisory lock, key bindings that replay their own outcome); `human_review` routing target |

### Recent merges (OBSERVED, 2026-10-28)

| PR | Result |
|----|--------|
| [#82](https://github.com/Zero-State-LLC/Patch-Hive/pull/82), [#98](https://github.com/Zero-State-LLC/Patch-Hive/pull/98) | P0 and P1 security fixes from the gap analysis: export idempotency per user, admin-only role grants, sign-in lockout and per-IP limits, Argon2 with rehash, one referral reward |
| [#83](https://github.com/Zero-State-LLC/Patch-Hive/pull/83)–[#87](https://github.com/Zero-State-LLC/Patch-Hive/pull/87), [#107](https://github.com/Zero-State-LLC/Patch-Hive/pull/107) | Edge: production and staging pairs on Cloudflare, container scheduling, secrets workflow (production secrets now reach the production Worker), https forwarding |
| [#88](https://github.com/Zero-State-LLC/Patch-Hive/pull/88), [#92](https://github.com/Zero-State-LLC/Patch-Hive/pull/92)–[#97](https://github.com/Zero-State-LLC/Patch-Hive/pull/97) | Spec 001: gated run lifecycle, append-only runs and patches, rack soft-delete, five categories, six engine rules, port resolution and validation |
| [#99](https://github.com/Zero-State-LLC/Patch-Hive/pull/99), [#100](https://github.com/Zero-State-LLC/Patch-Hive/pull/100), [#113](https://github.com/Zero-State-LLC/Patch-Hive/pull/113) | 15-minute in-memory access tokens, rotating refresh cookie, CSP enforced, sign-in open |
| [#101](https://github.com/Zero-State-LLC/Patch-Hive/pull/101), [#102](https://github.com/Zero-State-LLC/Patch-Hive/pull/102) | Spec 002: patch pages wrap or fail with a code, font floors, publication lifecycle |
| [#103](https://github.com/Zero-State-LLC/Patch-Hive/pull/103) | Spec 003: bounded downloads, identified receipts, apply bound to the reviewed `plan_hash` (case writes included) |
| [#104](https://github.com/Zero-State-LLC/Patch-Hive/pull/104), [#105](https://github.com/Zero-State-LLC/Patch-Hive/pull/105) | Spec 005: answers bounded to the request's candidates; a failed provider is UNRESOLVED or ESCALATE, never REJECT |
| [#112](https://github.com/Zero-State-LLC/Patch-Hive/pull/112) | Catalog loaded to prod (T027) |
| [#114](https://github.com/Zero-State-LLC/Patch-Hive/pull/114) | Products page reads the module catalog (was empty in production) |
| [#115](https://github.com/Zero-State-LLC/Patch-Hive/pull/115) | 183 missing categories filled from crawl tags (T028) |
| [#116](https://github.com/Zero-State-LLC/Patch-Hive/pull/116) | 263 misattributed or bogus rows tombstoned, 7 modules re-added under their makers (T029) |
| [#117](https://github.com/Zero-State-LLC/Patch-Hive/pull/117) | Docs, board mirror and the next-slices plan |
| [#118](https://github.com/Zero-State-LLC/Patch-Hive/pull/118) | A1: unknown module power counted per rail, not as 0 mA; one rounding rule |
| [#119](https://github.com/Zero-State-LLC/Patch-Hive/pull/119) | A2: the crawler refuses a homepage another brand owns (T030) |
| [#120](https://github.com/Zero-State-LLC/Patch-Hive/pull/120) | Second retirement: 185 more misattributed rows (ALM Busy Circuits copies and others) |
| [#121](https://github.com/Zero-State-LLC/Patch-Hive/pull/121) | A3: six crawled modules no overlay held |
| [#122](https://github.com/Zero-State-LLC/Patch-Hive/pull/122) | A4: racks warn when they hold a retired module |
| [#123](https://github.com/Zero-State-LLC/Patch-Hive/pull/123) | A5: signed-out page loads skip the refresh call |

## OBSERVED product posture

| Area | State |
|------|--------|
| Product identity | Deterministic Eurorack **rig + patch documentation** |
| Canonical domain | `backend/canon/` (+ design recipes, export fulfillment) |
| Design Engine flags | **Default off**; on in the staging Worker only (#213), walkthrough PASS on staging (#216, 008 T040b); production sets none |
| Alembic | Single head through `20261102_export_fair_use`; staging and prod migrated 2026-11-03 |
| Rig validation | Unknown draws are per rail (`POWER_RAIL_INCOMPLETE`, lower bounds); retired placements warn (`MODULE_TOMBSTONED`) on every rack read |
| Health | `/health` liveness; `/health/ready` includes DB |
| Local Compose staging | `docker-compose.staging.yml` + `scripts/staging/*` + `scripts/test/run.*` |
| Test automation | `scripts/test/run.sh\|ps1` · CI runs unit, API and mocked-API e2e; the acceptance suite runs locally (11 PASS) and is not yet in CI (`acceptance-tests.yml` was removed in 5b85f58) |
| Dual-path inventory | F0–F4 done; F5 list cutover done (008 T010/T020); the rig builder reads through canon (#243), and its writes and compatibility check stay on `/api/racks`; Z deferred |
| Named staging host | Cloudflare pair `staging.patch-hive.com` / `api-staging.patch-hive.com` (Neon `staging` branch), at `9c42bd6` since 2026-11-03 |
| Payments | Test-mode only; sales deferred (004 OQ-13). Deployed 2026-11-03 with every flag off: Machine B credit checkout behind `ENABLE_CREDIT_CHECKOUT` (off; refuses live keys) with webhook fulfillment (#209), referral rewards on a verified provider purchase (#183, #210), and Admin reject and resolve for unresolved events (#184, #211). Subscription events stay `unresolved` (`HANDLER_NOT_IMPLEMENTED`) until T049; refunds (OQ-2) in progress |
| Publishing | Drafts cannot be published (`PUBLICATION_BOOK_NOT_VALIDATED`) until the owner decides OQ-6 (002 T033) |
| Readiness gates | The approver public key `approver-2026-11` is committed (#204); a receipt verifies only once the operator signs the 007 chain (T083). On main, a decision provider outside development also needs that signed receipt (#185), and readiness pins are signed by the approver key (#186) |
| Module catalog (staging = prod) | 4,184 catalog rows and 4,154 modules, of which 448 each are tombstoned; 3,736 visible from 356 brands, 0 conflicts. 855 rows have no category. Sovage CHICANE corrected to 4 HP (#125) and unflagged (#135, loads of 2026-10-29). HP corrected for Acid Rain Junction, Doepfer A-101-3 and A-137-2 (#153, loads of 2026-10-30); A-101-3's module stays flagged because its +5V draw is unstated: doepfer.de gives +12V 50 mA, -12V 50 mA and 65 mm depth (already loaded from `module-power-depth-v10`), but neither the product page nor either manual states +5V. HP corrected for Make Noise DPO (28) and Morphagene (20), Bastl Knit Rider (16) and Intellijel MEMS Mic 1U (10) (#164); A-106-1 (14) and A-138m (20) corrected (#167), A-155 (50) corrected (#172), Dixie II (6) corrected (#174), loads of 2026-10-30; Cockpit (golden) HP and both Cockpit rows' power and depth filled from the maker page (#176, #178, loads of 2026-10-31 and 11-01); 17 HP values carry `hp_source = legacy_unsourced` and 40 carry `retailer_observed` (a retailer page states the stored value, #180) until a maker page confirms them (mostly ADDAC and Befaco, whose sites block automated reads; T039 open). 21 jumper settings for 11 modules are in `power_configs` (#166, #170, #172), every setting the T035 receipt recorded. The older duplicate row "QCD: Quad Clock Distributor" has none; they sit on "4ms QCD"). Sources: Phase 2 seed (ModularGrid leads, tagged `unknown`/`CATALOG_OBSERVED`) plus maker pages (`official_publication`). Maker-crawl page cache deleted 2026-10-28; committed crawl results intact |
| API access | Module and case writes admin-only (#79). Racks owner-scoped (#80): owner reads/writes, admin read roles read all, public racks readable by anyone, others 404. Catalog materialize and stateless layout recommendation stay public |
| Accounts | Sign-in open on staging and production (#113). No account yet created on production; a real sign-up is still to be tried |
| Production deploy | Frontend (`patch-hive.com`) and API (`api.patch-hive.com`) on Cloudflare, deployed manually with `wrangler deploy` from a checkout of main (no deploy workflow); API and frontend last deployed at `6c234a6` on 2026-11-03. CSP enforced; CORS limited to the exact origin. `/health` reports the release version (0.3.0-alpha.7) |
| CI | Repo is public so GitHub Actions runs on free minutes; with the repo private the Actions budget blocks every job |
| Production readiness | **Not ready** (beta-staging engineering) — [assessment](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md) · [matrix](docs/evidence/PRODUCTION_READINESS_MATRIX.md) · [delta](docs/evidence/PRODUCTION_READINESS_DELTA_2026-07-26.md) |

## Decision Intelligence specification campaign (2026-09-25)

**OBSERVED:** provider-neutral Decision Intelligence is now specified under `specs/005-decision-intelligence/`; implementation remains pending and Jev is not enabled. The constitution makes evidence non-canonical and forbids probabilistic direct-to-canon writes.

**Next implementation gate:** contracts + deterministic policy + fixture provider before any Jev adapter.

## Immediate continuation priorities

1. Owner steps, in order: [docs/evidence/OWNER_ACTIONS_2026-11-03.md](docs/evidence/OWNER_ACTIONS_2026-11-03.md) (after the 2026-11-03 Backlog remediation; it links the command blocks in [the 2026-11-02 guide](docs/evidence/OWNER_ACTIONS_2026-11-02.md)). Next up: protect the `production` environment (T101b), confirm specs 001–004, the R2 check, and photos for the 007 corpus (open web search found 2 usable images in 300 searches, #208; owner or maker-licensed photos are the remaining source). Startup migrations are opt-in (#110, merged); databases migrate only through `db-migrate.yml`.
2. Catalog: 17 HP values stay `legacy_unsourced` (T039, #180). 6 have a retailer page that disagrees: ADDAC200PI 2 vs 4, ADDAC200S black 2 vs 4, ADDAC501B 8 vs 4, Befaco Mixer 5 vs 4, Cwejman D-LFO 12 vs 14, Instruō dàil 4 vs 6 (that page bundles a 2 HP expander); each needs a maker source or an owner correction. 11 are on no retailer we may use: ADDAC001, 003, 005, 101 and 203, Befaco Dual Atenuverter, Doepfer A-101-4, Intellijel Quadra Expander and μAtt, Make Noise Mysteron and Strega. The 40 `retailer_observed` rows still lack maker confirmation (FR-027). Asking the makers for spec sheets remains the route to confirm them; cwejman.net now redirects to an unrelated site. `evidence.expire` gets a daily job once T101b is done (006 T101c; 0 evidence images today). T035 needed no paid pass (#163); Frap needs none either (D7).
3. Release: 0.3.0-alpha.7 is merged and deployed (2026-11-03). Release Please keeps the next release PR open; merge it right before a deploy that ships code, so the tag matches what runs.
4. Operator (step-by-step guide: [docs/evidence/OWNER_ACTIONS_2026-11-02.md](docs/evidence/OWNER_ACTIONS_2026-11-02.md)):
   - real sign-up on production;
   - verify seeded demo auth on staging (008 T030b);
   - VirusTotal reanalysis;
   - rotate the context.dev and OpenRouter keys;
   - add `PROJECT_TOKEN` (`RELEASE_PLEASE_TOKEN` exists, checked 2026-11-02);
   - decide repo visibility versus the Actions budget;
   - confirm specs 001–004 (R6).

**Local test automation:**
`cd backend && pytest tests -q` with a local Postgres 15 for the population tests (1,045 passed, 2 skipped on #125) · acceptance suite separately (11 passed; #78 lets it run in the same invocation)

## Authority boundary

**Do not:** deploy production, enable live Stripe, charge users, or activate hardware without separate operator authorization.

## Doc index

| Doc | Use |
|-----|-----|
| [docs/ROADMAP.md](docs/ROADMAP.md) | Capability roadmap |
| [docs/KANBAN.md](docs/KANBAN.md) | Board mirror (Project #8 is the source of truth) |
| [docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md](docs/evidence/OPEN_DESIGN_DECISIONS_2026-10-28.md) | Open owner decisions with research |
| [docs/CONTINUATION.md](docs/CONTINUATION.md) | Engineering backlog (dated 2026-07-21; see the board for current work) |
| [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md) | Gate framework |
| [docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md](docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md) | Latest readiness narrative |
| [docs/FEATURE_FLAGS.md](docs/FEATURE_FLAGS.md) | Flags |
| [brand/README.md](brand/README.md) | Brand kit |
| [.specify/memory/constitution.md](.specify/memory/constitution.md) | SpecKit constitution |
| [specs/005-decision-intelligence/spec.md](specs/005-decision-intelligence/spec.md) | Decision Intelligence requirements |

## Database (Neon, provisioned 2026-10-16)

OBSERVED:

- Provider: Neon, project `patchhive` (id `polished-night-86976142`), region `aws-us-west-2`, Postgres 15, database `patchhive`.
- Branches: `main` is **prod** (default); `staging` was branched from `main`.
- Compute: 0.25 CU fixed, scale-to-zero after 5 min.
- Hard project quota (the project suspends instead of overbilling): `compute_time_seconds` 180000 (about 50 CU-hours per month) and `logical_size_bytes` 1 GiB. The org is on the Neon Launch plan (usage-billed).
- Connection strings: GitHub Actions secrets `PATCHHIVE_DATABASE_URL_STAGING` and `PATCHHIVE_DATABASE_URL_PROD`. Never commit them.
- Migrations: run the manual workflow `.github/workflows/db-migrate.yml` (choose `staging` or `prod`). The agent box cannot reach Postgres port 5432 directly.
- Data load: manual workflow `.github/workflows/db-load.yml` (`env` staging or prod, `mode` dry-run by default or apply). Apply dumps the affected tables first; the dump stays on the runner (only its size and sha256 go to the job summary) and the uploaded receipt is counts only, because this repo's artifacts are public. The agent box cannot open port 5432, so the load runs in Actions. Run `db-migrate.yml` on the same ref first; the load refuses to start unless the database is at that checkout's alembic head. Operator yes is still required before apply.
