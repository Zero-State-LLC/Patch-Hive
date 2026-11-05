# Spec 002 T001 confirmation, 2026-11-04

**Who confirmed this.** An agent (Claude), under the owner's delegation. On 2026-11-04 the owner said "you can do all of this" about their open cards, so the agent ran this sitting in their place. The owner has not read the spec. This record is an agent's check, not the owner's reading. The owner approves by merging the PR that carries it.

**Result.** T001 is ticked: 16 CONFIRMED, 13 DRIFT, 7 OPEN. No claim is wrong in a way that needs a human product decision before planning. Each OPEN item has a default that keeps publishing off and changes nothing, and [plan.md](plan.md) follows those defaults. Merging does not answer the OPEN items. They stay the owner's, with counsel where noted.

**Method.** Each 002 claim in section 1 of [the owner action guide](../../docs/evidence/OWNER_ACTIONS_2026-11-02.md), and every other `[INFERRED]` line in [spec.md](spec.md), was checked against the code and tests on `main` at 007b437 (0.3.0-alpha.8) and [the recorded decisions](../../docs/evidence/JEV_DECISIONS_2026-11-01.md). Numbers in the claim column are spec.md lines. `spec.md` is unchanged, because the 002 checklist asks for no corrections. Line 3 of spec.md is a status header, not a claim.

**Tests.** 117 tests passed locally (Python 3.11, SQLite): transitions, report limits and locks, publishing API, `validate_book`, SVG goldens, page fit, publication dual, cover, feature flags and account deletion. A "probe" below is a throwaway test run against the same app and not committed; it is cited where no committed test covers the behaviour.

**Not verified.** Postgres row locks under real concurrency (`FOR UPDATE` is a no-op on SQLite). Nothing was run on staging or production. The full backend suite was left to CI.

**Short names.** `routes` is `backend/publishing/routes.py`. `engine` is `backend/export/patchbook/design/engine.py`. `spine` is `backend/export/patchbook/design/content_spine.py`. `T` is `backend/tests/unit/test_spec_002_transitions.py`. `A` is `backend/tests/api/test_publishing_api.py`. `L` is `backend/tests/unit/test_spec_002_report_limits_and_locks.py`.

## Checklist claims

| # | Claim | Status | Evidence |
|---|---|---|---|
| 1 | With the flag off, every publishing request fails closed and changes no state (138, 244, SC-006 at 499) | CONFIRMED | `backend/main.py:202-205` mounts the router only with the flag on; off by default at `backend/core/config.py:62`. Tests: `test_event_with_the_flag_off_is_404_without_change` (`T:222`), `test_create_with_the_flag_off_is_404_and_writes_nothing` (`T:237`), `test_historical_features_are_disabled_by_default` (`backend/tests/unit/test_canon_feature_flags.py:6`). Probe: all nine publication paths answer 404. For the two `/me/exports` paths see D1. |
| 2 | A publish needs an export bound to a validated book, and today always refuses (139, 260, 332; OQ-6 `keep_off`) | CONFIRMED | `routes:296-298`; `_bound_to_validated_book` returns false at `routes:312-317`. Tests: `test_publish_of_a_draft_is_refused_without_a_validated_book` (`T:270`), `test_publication_lifecycle_follows_the_spec` (`A:366`). The table's success row cannot run through the API today. |
| 3 | Draft or hidden publications are invisible to non-owners; the gallery shows only `published` and `public` (151, 255) | CONFIRMED | Read `routes:349-355`, download `routes:401-407`, gallery `routes:428-432`. Tests: draft read `A:385`, removed read `A:185`, unlisted gallery `A:168`. No committed test covers a hidden read, or draft and hidden rows in the gallery. Probe: read and download answer 404 for draft, hidden and removed, and the gallery lists only the published public row. T010 should add these. |
| 4a | Through the owner, admin and report routes, a removed publication refuses every transition, and `draft` to `hidden` or `removed` is illegal (173, 345-347) | CONFIRMED | `routes:284-285`, `routes:294-295`, `routes:496-497`, `routes:575-576`, `routes:610-611`. Tests: rows `T:58-67` through `test_illegal_transition_is_rejected_without_change` (`T:206`); `test_a_removed_publication_cannot_be_edited` (`A:328`). |
| 4b | The same claim, for account deletion | DRIFT | D2. |
| 5 | Reports on draft, hidden or removed publications are rejected (353, 511) | CONFIRMED | `routes:495-497`. Tests: `T:63`, `T:68`, `T:69`, `A:408`. The rejection is a 404 (see D5). |
| 6 | No model or decision-layer component may change status or moderate (261, 354, 422) | CONFIRMED | The only writers of `Publication.status` are `routes:249,299,586,621` and `backend/account/deletion.py:133`. `backend/intelligence/` does not import `publishing`, and `backend/publishing/` does not import `intelligence` (`routes:19-29`). Repo grep only: no test or ast-grep rule enforces this. |
| 7 | Page and book compile machines: states, deterministic remediation order, "no accepted pages means the book fails" (379-476) | DRIFT | Not implemented, so not confirmed behaviour. D3. |
| 8a | Multi-page profiles are out of scope (89; OQ-11) | CONFIRMED | Off by default at `backend/core/config.py:174`; refused at `backend/export/patchbook/design/constraints.py:87-94`. Plate mode fails by design: `test_plate_family_publication_fails_page_count_until_plates_are_drawn` (`backend/tests/unit/test_patchbook_publication_dual.py:118`). |
| 8b | The Style Studio and Design Engine are out of scope (90) | DRIFT | D4. |
| 8c | Patch generation is out of scope, and the compiler never creates patches (91, 92, 235) | CONFIRMED | `design/` writes to the database only in `dual_write.py:78,92,118`, which runs at generate time (`backend/patches/routes.py:308`). No code under `backend/` outside tests mentions decomposition, so nothing creates decomposed patches. Recommending it is not built either (D3). No test asserts this. |
| 9a | When the admin acts first, the owner's later status request is refused; the row lock serializes them (510; #197) | CONFIRMED | Locks at `routes:272-278`, `routes:566-572`, `routes:601-607`; check at `routes:292-293`. Test: `test_owner_patch_sees_admin_hide_made_after_the_row_was_loaded` (`L:32`). Real lock order was not run (see "Not verified"). |
| 9b | When the owner's hide commits first, the admin still wins (510) | DRIFT | D6. |

## Other claims, in groups

| # | Claim | Status | Evidence |
|---|---|---|---|
| G1 | Compilation uses only confirmed facts; a missing fact is an explicit error, never a placeholder (43, 215, 508) | DRIFT | D7. |
| G2 | Compilation never changes source artifacts (49) | CONFIRMED | `compose_design_export_pack` (`engine:286`) writes only under the pack root; database writes are as in row 8c. No test asserts that source rows stay unchanged. |
| G3 | Paid debit, ledger, Stripe, download tokens and fulfillment are out of scope (87) | CONFIRMED | `backend/publishing/` imports no `canon` or `monetization` code (`routes:19-29`). Those stay under `/api/canon` (`backend/main.py:187`). |
| G4 | An owner cannot unhide what moderation hid (160, 334, 352; OQ-2) | CONFIRMED | `routes:292-293`. Tests: `T:71`, `test_owner_cannot_lift_moderation` (`A:288`). |
| G5 | A report leaves status unchanged (170, 341) | CONFIRMED | `routes:513-521` writes only a report row. Test: `T:53`. |
| G6 | If the flag turns off while publications exist, reads stop and stored state is unchanged (509) | CONFIRMED | Same mount as row 1; `T:222` asserts rows are unchanged. The flag is read at startup (`backend/main.py:202`), so the change takes a restart. |
| G7 | Workflows: skills, implementer, reuse of CI (298-302) | CONFIRMED | Skills match `AGENTS.md`, "Skills". Jobs `backend` and `frontend` exist (`ci.yml:17,139`) beside `migrations`, `acceptance`, `backend-lint` and `frontend-e2e`; this work adds no CI path. FORGE owns plan and tasks in agent-context `templates/sdlc/README.md`. |
| G8 | The threat model covers the public surfaces (OQ-15 at 541; 275-294) | CONFIRMED | Written in #195 and still describes the code, except as in D12. Its suggested tasks are not in `tasks.md`; plan.md orders them. A related finding from this sitting went to the owner directly, outside this public repo. |
| G9 | Any (state, event) pair a table does not list is rejected (312) | DRIFT | D9. |
| G10 | A PageFitReport `warning` is not a pass (402, 419) | DRIFT | D10. |
| G11 | SC-007: every illegal transition in the three tables has a test (500) | DRIFT | D11. |
| G12 | With the flag off, every route is 404 (56, 525) | DRIFT | D1. |
| G13 | FR-038 note: anything outside the table answers 409 `INVALID_TRANSITION` (250) | DRIFT | D5. |
| G14 | The "Workflows" line names SCRIBE (301) | DRIFT | D8. |
| G15 | Statements in spec.md that later work overtook | DRIFT | D12. |
| G16 | Publishing works once the flag is on (20, 131, FR-030 at 242) | DRIFT | D13. |
| O1 | Should publishing come back (OQ-6, T033)? | OPEN | Below. |
| O2 | Licence terms and `allow_remix` (OQ-12) | OPEN | Below. |
| O3 | Retention of reports and audit logs (OQ-13) | OPEN | Below. |
| O4 | Crossing, ambiguity and visual-diff thresholds (OQ-9) | OPEN | Below. |
| O5 | Publication profile against the one-page law (OQ-11) | OPEN | Below. |
| O6 | Build the compile machines, or replace their tables | OPEN | Below. |
| O7 | Truncated source text (OQ-14) | OPEN | Below. |

## DRIFT

Each item says what the spec says, what the code does, which is right, and which task covers it.

- **D1. Flag-off routes.** Lines 56 and 525 say every route is 404. Nine of eleven are. `POST /api/me/exports` answers 405 and `GET /api/me/exports` answers 200, because the account router owns that path (`backend/account/routes.py:76`, mounted at `backend/main.py:193`, before publishing at `:205`). So `list_exports` (`routes:210`) never runs, by route order, and `docs/PUBLISHING_API.md:39` describes it. No publishing handler runs and no state changes, so the failure is closed. Right: the code; the text needs correcting. T090 corrects it; T010 adds both paths to the flag-off test.
- **D2. Account deletion.** FR-038 (250) says status changes only through the table, and line 347 makes `draft` to `removed` illegal. Closing an account sets each of the user's publications to `removed` from any state, with reason `ACCOUNT_DELETED` and no `moderation_audit_id` (`backend/account/deletion.py:132-138`; test `backend/tests/api/test_account_deletion.py:215-217`; probe on a draft). Right: the code, per 004 OQ-12 `A_anonymize_keep`. T090 adds an `account_deleted` row; T010 encodes it.
- **D3. Compile machines not implemented.** No state, event or guard from lines 371-490 exists: no hits under `backend/` for `spec_built`, `remediating`, `collecting`, `assembled`, `COMPILE_PATCH_PAGE`, `PatchPageSpec` or `PageFitReport`. What exists instead: `validate_book` (`engine:106`, called at `:535`) writes one receipt, kept on failure (`:552-554`), and checksums are read back (`:592-598`), tested in `backend/tests/unit/test_patchbook_validate_book.py`. One patch that does not fit fails the whole export (`engine:1074`, `backend/export/patchbook/design/diagram_svg.py:208`, `backend/tests/unit/test_patchbook_page_fit.py:67`). The only remediation is dropping the optional title block (same file, `:75`), so no remediation order exists. "No accepted pages" has no direct form: zero patches fail `EXPORT_NO_PATCHES` (`spine:193`, no test found) or 404 on the legacy route (`backend/export/routes.py:183,290`). Right: the tables remain the target and the code does not meet them. T010 cannot encode them; T090 covers them, subject to O6.
- **D4. Design Engine scope.** Line 90 puts the Design Engine out of scope. Lines 28-53 and T030, T031, T035 and T036 place the compilation FRs in `backend/export/patchbook/design/`. Right: the table and tasks. Line 90 should name only the Style Studio and style recipes (`docs/FEATURE_FLAGS.md:16`, spec 008). T090.
- **D5. FR-038 note.** Line 250 says owner, admin and report actions outside the table answer 409 `INVALID_TRANSITION`. Reports answer 404 (`routes:496-497`, `T:63`). A removed row answers 409 `PUBLICATION_UNDER_MODERATION` (`routes:285`), and an unbound publish 409 `PUBLICATION_BOOK_NOT_VALIDATED` (`routes:298`). Right: the code; the 404 keeps a non-public row indistinguishable from a missing one (threat model P1). T090.
- **D6. Admin acting second.** Line 510 says the admin wins. If the owner's hide commits first, admin hide answers 409 `INVALID_TRANSITION`, records no hold, and the owner can unhide (`routes:575-576`, `T:70`; probe). The table (335) allows `admin_hide` only from `published`, so the spec disagrees with itself. Right: line 510; an admin who acts second should still end with a hold. T090 adds the row; T010 changes `T:70`. No effect while publishing is off.
- **D7. Placeholders.** FR-014 and line 508 require an explicit error for a missing fact. Path B fills in placeholders: `spine:243-261`, `:294-297`, `:394`, `:522-525`. Probe: a connection with no ports seals with the step `Connect 1 UNKNOWN → 2 UNKNOWN`, intent `NOT_COMPUTABLE` and report `valid` true. Path A was not probed. Right: the spec (constitution principle 3). T090.
- **D8. SCRIBE.** Line 301 names SCRIBE. Outside the spec and plan files of 001 to 005 it appears nowhere in this repo, nor in agent-context `TEAM.md`, `templates/sdlc/README.md` or `HANDOFF.md`. `AGENTS.md` says to name only what exists. Right: `AGENTS.md`. T090 removes it here; the other specs need the same fix.
- **D9. Owner no-ops.** Line 312 rejects unlisted pairs. Setting `published` on a published row, or `hidden` on a hidden one, answers 200 and changes nothing (`routes:326-327`; noted at `T:72-75`; probe). Right: the code. T090 lists both in the table; T010 tests them.
- **D10. Warnings.** Lines 402 and 419 say a `warning` is not a pass. OQ-7 `non_blocking_recorded` (0.88) says warnings pass and are recorded, as built (`engine:464-467`, `:549`, `:571`; `test_preflight_warnings_are_recorded_in_the_manifest`, `backend/tests/unit/test_patchbook_publication_dual.py:66`). Right: the decision and the code. FR-019 still holds, since nothing passes silently. T090.
- **D11. SC-007.** Only the publication table has illegal-transition tests (`T:57-75`). T010 stays open for the other two until O6 is settled.
- **D12. Overtaken text, no behaviour at stake.** T090 corrects each:
  - 192: the cover disclaimer is no longer 8 pt (T035). The colophon's still is (`engine:977`), as line 33 says.
  - 347: "until OQ-3 is resolved"; it is resolved (520-521).
  - 524: "flag-off 404 untested"; tested 2026-11-03.
  - 527, 529, 534, 536: "Still open (owner)" under OQ-6, OQ-7, OQ-10 and OQ-11, which were decided, some built.
  - 281, 283, 289: the threat model says the report route has no limit or dedupe; #197 built both. Its line numbers (277-285) predate #197.
  - `docs/PUBLISHING_API.md:65`: create is shown returning `published`; it returns `draft` (`routes:249`).
- **D13. No migration.** No Alembic migration creates `publications`, `publication_exports` or `publication_reports` (no hits under `backend/alembic`; `backend/account/deletion.py:120` says so), and `allow_create_all` is off (`backend/core/config.py:40`). Tests build tables from the models (`backend/tests/conftest.py:61`). So the flag on against a migrated database would fail at the first query (inferred, not run). Right: the spec's intent; T033 must add the migration if publishing returns. T090 records the gap.

## OPEN

Not decided here. Each has a recommended default, which [plan.md](plan.md) follows.

- **O1. Should publishing come back (OQ-6, T033)?** Product call; the decision record says a lawyer must confirm. Default: keep it off. `_bound_to_validated_book` stays false and T033 stays open.
- **O2. Licence terms and `allow_remix` (OQ-12).** Legal. Jev's provisional pick is `owner_picks_license` (0.39); the owner action guide (2.2) recommends `no_public_sharing` until counsel answers. Default: defer, with no schema change. The hard-coded CC BY-NC 4.0 (`routes:121,170`) reaches nobody while publishing is off.
- **O3. Retention of reports and audit logs (OQ-13).** Legal. Default: leave undecided and keep what is built (rate limit, dedupe for signed-in reporters). Take it to counsel with the legal brief.
- **O4. Thresholds (OQ-9).** The decision is to measure, and the owner approves the numbers. Default: crossing, ambiguity and visual-diff thresholds stay `NOT_COMPUTABLE` (SC-004) until measured on the fixtures and approved.
- **O5. Publication profile against the one-page law (OQ-11).** Product call. Default: keep the flag off and plates undrawn, failing by design (`keep_off_deferred`).
- **O6. Build the compile machines, or replace their tables with what `validate_book` checks?** Product and money. Today one patch that does not fit fails the whole paid export, which is compensated. The spec would drop only that patch and ship the rest, so a customer could pay for a book missing a patch. Default: build nothing now; the tables stay the target; a misfit keeps failing the whole export with compensation. T090 cannot close until this is answered.
- **O7. Truncated source text (OQ-14).** The decision says the operator supplies it. The sources named in spec.md are in this repo; `docs/PATCH_BOOK_GENERATOR.md` was read in full and is not cut off. The extracts the drafting model saw are not retained, so what they lacked cannot be checked. Comparing the spec against that document finds these not in the spec: invariant 8 on decorative art, the content budget numbers (section 7), layout area targets (section 6), typeface rules (section 9) and tagged PDF (section 10). Default: accept the spec, supply nothing, and carry those items at T090.
