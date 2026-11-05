# Spec 003 T001 confirmation, 2026-11-04

**Who confirmed this.** An agent, under the owner's delegation. On 2026-11-04 the owner said "you can do all of this" about their open cards, so the agent ran the T001 sitting in their place. **The owner has not read spec 003 or this record.** This is not the owner reading it. The owner approves by merging the PR that adds it.

**Result.** 10 CONFIRMED, 18 DRIFT, 9 OPEN. No claim is wrong in a way that needs a human product decision before planning: the OPEN items hold back fetching, taxonomy and T039, not the plan. T001 is ticked.

**Method.** Each checklist claim in `docs/evidence/OWNER_ACTIONS_2026-11-02.md` (section "1. T001 spec confirmations"), and each other `[INFERRED]` line in spec.md, was checked against code, tests and earlier owner decisions on `main` at `007b437` (0.3.0-alpha.8). D1 to D8 override `[INFERRED]` text and were not reopened.

- **CONFIRMED:** code and spec agree.
- **DRIFT:** spec says X, code does Y. The DRIFT list says which is right and what covers the fix.
- **OPEN:** a product, legal or money call or a third-party permission. Not decided here. The OPEN list gives a recommended default.

**Line numbers** are spec.md today. The checklist is older: its line 426 is now 478, 242 to 280 is 289 to 334, 304 is 356, 419 to 436 is 469 to 481, and 215 is 267.

**Path key.** `population` = `data/synth-catalog/population.py`; `scrape` = `data/synth-catalog/catalog_scrape.py`; `hermes` = `scripts/hermes_hp_enrich_firecrawl.py`; `crawl` = `scripts/catalog_maker_crawl.py`; `routes` = `backend/modules/catalog_routes.py`. Tests: `t_transitions` = `backend/tests/unit/test_spec_003_transitions.py`; `t_population` = `backend/tests/test_catalog_population.py`; `t_router` = `backend/tests/test_catalog_scrape_router.py`; `t_scope` = `backend/tests/unit/test_003_source_scope.py`.

## Claims

| # | Claim (spec.md lines) | Status | Evidence |
|---|---|---|---|
| 1 | The batch lifecycle is a state machine, TARGETED to ADMITTED (289 to 354) | DRIFT | No state field or machine in code; scripts and `db-load.yml` run the steps. `t_transitions` encodes the row lifecycle only. OQ-9 chose minimum code over a machine. |
| 2 | BLOCKED: no credentials means no start (294, 310 to 312, 330; FR-002 at 68, 393) | DRIFT | Only `crawl:898-911` exits before sending. `hermes` has no exit; with no key the router records `skipped_no_key` per call (`scrape:480-482`). |
| 3 | RETRY_QUEUED: a mid-batch budget failure keeps the checkpoint and queues a retry (296, 315, 316, 479) | DRIFT | No such state. One-off run with a fake transport and no key: the target ends `not_found` / `NOT_COMPUTABLE`, noted "no HP on candidate official manufacturer URLs" though nothing was read, and `--resume` sends 0 requests for it (`hermes:196-253`, `:287-300`). |
| 4 | FILTERED: a filter step excludes incomplete rows, FR-014 (120, 235 to 255, 298, 317, 318, 411, 449) | DRIFT | No script writes `*.filtered.json`; the 4 committed files came from outside the repo scripts. The loader checks the source per overlay only (`population:994`, `:1167`). |
| 5 | OVERLAY: immutable, content-hashed files, FR-018 (84, 299, 319, 415, 451) | DRIFT | Files are versioned, and `inputs_hash` (`population:1971`) detects a change between dry run and apply. No per-file hash, and nothing stops an edit: `git log` shows 2 commits on `module-power-depth-v12.json` and 3 on `seed-phase2-v1.json`. |
| 6 | REJECTED: a declined or empty batch is a final state (302, 318, 322, 332) | DRIFT | No state and no record. A declined dry run is simply never applied. |
| 7 | An apply needs approval of a receipt binding the current overlay, FR-020 (321, 331, 420) | CONFIRMED | `population:2119-2131`, `scripts/catalog_actions_load.py:100-103`, `.github/workflows/db-load.yml`. Tests `t_population:228`, `:248`, `:294`; `t_transitions:236`. |
| 8 | RAW or earlier can never reach ADMITTED without a receipt (326, 327) | DRIFT | The Actions path holds. `scripts/apply_hp_enrichment.py:80` writes scrape results straight to `module_catalog` with no receipt, hash or archive. |
| 9 | FR-003: a paid fetch never starts without a recorded approval (329, 394, 457) | CONFIRMED | `scrape:571-588`, `:854`; `crawl:906-911`. All four callers pass the approvals file (`scrape:384`, `crawl:923`). Tests `t_router:246`, `:257`, `:284`, `:338`. The checklist's "empty" is stale: the file holds `corpus-photos-2026-11`, which names no catalog brand (`t_router:319`). |
| 10 | FR-003 as written, and SC-005, cover every fetch (310, 311, 394, 465) | DRIFT | Free fetches need no approval (`t_router:312`). OQ-3 gates paid fetches only. |
| 11 | FR-017: the filter emits a residual targets file (257 to 265, 414, 450) | DRIFT | `grep residual scripts/` finds nothing. Retry files exist only from manual batches. |
| 12 | SC-004 and FR-020's "protected environment": every admission has a lasting receipt and an operator approval (86, 464) | DRIFT | `gh api repos/Zero-State-LLC/Patch-Hive/environments` on 2026-11-04: `production` and `staging` have no protection rules, so an apply needs only `workflow_dispatch` and the two hashes. Receipts are artifacts kept 7 days (`db-load.yml:94`). |
| 13 | FR-031: rollback per run, by run ID and receipt (434) | DRIFT | Nothing restores by `run_id`. The pre-apply dump is deleted before upload (`db-load.yml:83`) and only its size and checksum remain. `catalog_value_archive` holds changed values, not inserts. |
| 14 | FR-032: scraper and model only propose (98, 442, 488) | CONFIRMED | Fetch rows are `EVIDENCE_ONLY` (`hermes:231`, `:247`). `build_plan` (`population:186`) reads seeds, overlays, provenance and the T034/T035 receipts; its one `hermes-research` path (`:837`) is an optional file that is not committed. A model value needs a verbatim page match (`crawl:469-471`). No test asserts the loader ignores results. Exception: row 8. |
| 15 | Cases go through the same dry run, receipt and approval (124, 267 to 275) | CONFIRMED | `population:1873`, `:1914`; `plan_hash` and `inputs_hash` cover the case writes and seed (`:1954`, `:1971`). Tests `t_population:279`, `:294`. |
| 16 | FR-029 as written: cases follow FR-014 to FR-028 (429) | DRIFT | Cases have one seed (`data/cases/seed-v1.json`) with no filter, conflict marking or overlay versions. |
| 17 | Wrong HP on a page is evidence only (471) | CONFIRMED | `extract_hp` takes the first in-band match (`hermes:61-72`), the row stays `EVIDENCE_ONLY` (`:231`), and the loader does not read it. Test `t_scope:218`. research.md R1 and R7 record such errors found in review. |
| 18 | Private source stays out of the repo; row refs only (386, 486) | CONFIRMED | A policy, not a test. Page cache ignored (`.gitignore:81`); crawl rows hold values, URLs and hashes, no page bodies (`hermes-research/maker-crawl-v2.json`); `scripts/check_no_modulargrid.py` runs in CI (`ci.yml:39`). |
| 19 | ADVERSARY reviews untrusted page content; FR-010 (76, 401, 480, 487) | DRIFT | Spec 003 has no threat model, and `backend/tests` has no catalog injection test. Mitigations exist: regex extraction (`hermes:61-72`), the verbatim check, transport limits (`backend/tests/test_catalog_transport_limits.py`). |
| 20 | Slug collision: slugs are brand plus name and globally unique, OQ-6 (478, 499) | CONFIRMED | `create_slug` (`population:47-48`); `module_catalog.slug` is unique (`backend/modules/catalog.py:35`); same slug with another brand or name is an `identity_mismatch` conflict (`population:933-937`). Parsed 2026-11-04: 4,052 committed seed and addition rows, 4,047 distinct slugs, 0 collisions; 289 names under two or more brands get separate slugs; no committed receipt carries that conflict. No committed test names this reason; a one-off run of `_schedule_catalog` confirmed it. Line 478 reworded in this PR. |
| 21 | The seed is a scrape-derived discovery lead, D1 (checklist; FR-033) | CONFIRMED | All `catalog_modules` carry `access_basis = unknown` and `CATALOG_OBSERVED`, with no descriptions. Test `t_scope:53`. |
| 22 | Sealed seed path: OQ-4 chose a separate SEEDED/SEALED state (356, 497, 529) | DRIFT | Line 356 still says it reuses OVERLAY, and 529 still asks. The loader reads the seed directly (`population:188`, `:209`) with no pinned hash, and the seed has been edited since it was first admitted (D1 strip). |
| 23 | Workflows: the three skills and CI reuse (281, 283) | CONFIRMED | `AGENTS.md` names the same skills as defaults. `ci.yml` has `backend` and `frontend`, plus `migrations`, `acceptance`, `backend-lint` and `frontend-e2e`. This plan adds no CI path. |
| 24 | Workflows: FORGE, a cloud agent, SCRIBE, ADVERSARY as owners (282) | DRIFT | `Zero-State-LLC/agent-context` `DECISIONS.md:45`: FORGE owns plan and tasks, cloud agents implement, no extra bots. SCRIBE and ADVERSARY are absent from its `AGENTS.md`, `DECISIONS.md`, `TEAM.md` and SDLC templates. |
| 25 | FR-005: the crawler uses search only to resolve a homepage (71) | CONFIRMED | `crawl:317-331`, called only at `:574` in `resolve_brand`. Test `backend/tests/test_maker_crawl.py:498-501`. |
| 26 | D5: the loader is the only writer of catalog rows (26, 109) | DRIFT | Other writers remain: `scripts/apply_hp_enrichment.py:80`, `scripts/apply_module_catalog_hp_overlay.py:69`, `scripts/apply_module_power_depth_overlay.py:89`, and the admin routes in `backend/integrations/router.py`. `clear_existing` deletes rows (`backend/integrations/synth_catalog_importer.py:145`, `modulargrid_importer.py:42`, `:106`), and a missing category or type defaults to `UTIL` (`synth_catalog_importer.py:97`, `:176`). |
| 27 | D7: Frap and Tiptop are not fetched through a paid route (28) | DRIFT | Tiptop holds (`crawl:561`, test `backend/tests/test_maker_crawl.py:418`). Frap is still an active adapter (`data/synth-catalog/maker-sources.json:527`, `crawl:556-558`), so a key and an approval covering it would send it to a paid backend (`scrape:451`). |
| 28 | Row lifecycle: `null` on a NOT NULL field flags the row (372) | DRIFT | Code refuses it as `not_nullable` (`population:530-531`). No test names that reason. T010 already notes this. |
| 29 | Maker permission basis for crawling (FR-004, D2) | OPEN | PR #254 is an open draft held for owner sign-off. |
| 30 | Proxy tier and what counts as a block (FR-008 at 399) | OPEN | Default is `auto` (`scrape:339`, `t_scope:290`); a bot-check page goes on to a paid backend (`scrape:437-440`). PR #254 proposes otherwise. |
| 31 | VIDEO vs UTIL for video modules | OPEN | 24 rows held in `docs/evidence/CATALOG_T031_OFFLINE_PASS_2026-11-03.md`, decision 1. `OWNER_ACTIONS_2026-11-03.md` says about 21. |
| 32 | Retire the power-supply rows | OPEN | 11 rows held, same file, decision 2. |
| 33 | Any paid fetch cap (T031 remainder) | OPEN | No `fetch-approvals.json` entry covers a catalog brand, so no paid catalog fetch can run. |
| 34 | OQ-1: the 17 `legacy_unsourced` HP values (494) | OPEN | Jev chose `ask_makers` at 0.49, provisional, owner to confirm. T039 stays open. |
| 35 | OQ-2: Akemie's Castle, 18 or 38 HP (495) | OPEN | The product page states no width. Spec records 18 in `module_catalog` and 38 in `modules` on staging. Correcting needs a maker quote (FR-038) or an owner decision. |
| 36 | OQ-4's "a lawyer must confirm": may the scraped brand and module names stay? | OPEN | Legal brief question 6 in `OWNER_ACTIONS_2026-11-02.md`. Its answer sets the seed state's wording. |
| 37 | No bulk-publication surface exists, so FR-015's gate has nothing to guard (81, 99) | OPEN | `GET /api/modules/catalog` has no auth dependency and takes `limit` up to 500 (`routes:31-52`, `:118-120`), and it returns lead rows (`t_scope:61`). All rows can be paged out. Whether that is bulk publication under FR-033 and `docs/EXTERNAL_SOURCE_POLICY.md:162` is a legal call. |

Every `[INFERRED]` line in spec.md falls under a row above, except lines 3, 7, 22 and 501, which are notes about T001 itself. Line 279 heads rows 23 and 24.

## DRIFT

Which side is right, and what covers the fix. T090 means text amended or code changed under that task. Nothing in this PR changes code.

- **Row 1, batch machine.** Code is right (OQ-9). T090 marks the table as a description of the process; T010 keeps it out of the transition tests.
- **Row 2, credentials.** Code is right: the router runs free fetches first by design (T023). T090 amends FR-002 to "paid backends need keys".
- **Row 3, budget stop.** Spec is right, and the current `not_found` reads as a searched-and-absent result (FR-013). T090: record the refusal and let `--resume` retry it.
- **Row 4, filter.** Spec is right on packet completeness. T090.
- **Row 5, overlays.** Spec is right. T090: a check that applied files do not change.
- **Row 6, REJECTED.** Code is right on having no state (OQ-9). T090 amends the text.
- **Row 8, bypass.** Spec is right. T090, with row 26.
- **Row 10, FR-003 and SC-005 text.** Code is right (OQ-3). T090 narrows both to paid fetches. Whether free reads may run is row 29.
- **Row 11, residual file.** Spec is right. T090.
- **Row 12, approval and receipts.** Spec is right. The environment rule is 006 T101b, an owner-only setting that is still open, and T090 cannot close it. T090 covers a lasting receipt.
- **Row 13, rollback.** Spec is right. T090. Read with D3: a rollback retires a run's inserted rows and restores archived values; it deletes nothing.
- **Row 16, FR-029 range.** Code matches OQ-13's answer. T090 narrows FR-029 to the admission FRs.
- **Row 19, threat model.** Spec is right on the review. T090 adds a scoped threat-model section and an injection test, as 001 OQ-13 chose for spec 001.
- **Row 22, seed state.** OQ-4 is right. The decision record calls this spec text only, so T090 adds the row. D1 says the seed is not sealed, so the name should be `SEEDED`. A test follows once the wording settles (row 36).
- **Row 24, owners.** The team rule is right. T090 drops SCRIBE and ADVERSARY and names who reviews the threat model.
- **Row 26, D5.** D5 is right. T090 removes the other writers. If one turns out to be in use, that goes back to the owner.
- **Row 27, Frap.** D7 is right. T090 marks Frap refused in `maker-sources.json`.
- **Row 28, `null` action.** Code is right: `modules.hp` cannot be nulled (research R1). T090 amends line 372; T010 adds the missing test, and one for row 20's `identity_mismatch`.

## OPEN

Recommended defaults only. None is decided here.

- **Row 29, maker permission basis.** Recommended: PR #254's option C (facts from official pages under written conditions with an opt-out; ask first for anything more). Until signed, no page or feed reads.
- **Row 30, proxy tier.** Recommended: PR #254's `basic` default, other tiers only under an approval that names them, and a bot check counts as a refusal.
- **Row 31, VIDEO vs UTIL.** Recommended: a VIDEO category, or leave the rows empty until video is wanted in the catalog. They stay empty meanwhile.
- **Row 32, power-supply rows.** Recommended: retire them in a new retirements manifest citing maker pages, after row 29. They stay live and uncategorized meanwhile.
- **Row 33, paid cap.** Recommended: no entry and no paid run. If the T031 remainder is wanted, size it from a dry run, then add an entry.
- **Row 34, OQ-1.** Recommended: confirm `ask_makers`; with no reply in about 4 weeks, `accept_marked_and_close` (`OWNER_ACTIONS_2026-11-02.md` 2.5).
- **Row 35, Akemie's Castle.** Recommended: no correction until ALM's spec sheet; include it in the maker email.
- **Row 36, scraped names.** Recommended: keep D1 as it stands until counsel answers.
- **Row 37, paged catalog API.** Recommended: add it to legal question 6, change nothing meanwhile, and build no export. If it counts as bulk, T090 limits anonymous access to lead rows.

## Stale text left in place

The task allowed only the line 478 wording fix in spec.md. T090 should clear these:

- spec.md 3 (`Status: DRAFT`, must confirm before planning) and `specs/README.md:15` ("draft").
- spec.md 43, 122, 137, 453 ("sealed", against D1); 177, 183 (retailer second, against D2).
- spec.md 508 (221 values, decided by T038); 510 and T040 in tasks.md ("no active entries").
- spec.md 529 to 531 (seed path, verification ritual, slug dedupe, answered by OQ-4, OQ-5, OQ-6).

## Not verified

- **Databases.** No staging or production access. Row 35's values are as recorded in spec.md.
- **Edge.** Whether the Worker limits row 37's route was not checked.
- **Maker sites.** Not fetched, as instructed.
- **Spec labels and status table.** `[OBSERVED]` labels were not re-read against their source docs. Status-table rows were checked only where cited. `population.py` is unchanged since the table's baseline `3688037`, and `crawl` gained two lines.
- **`checklists/requirements.md`.** Four generic items, not ticked here. Three hold; "state machine complete" waits on row 22.
- **Tests.** Every test cited above passed locally on Python 3.11 at this commit, the Postgres-backed ones against a local Postgres. Of `t_population`, only the 6 tests selected for rows 7 and 15 ran locally. CI on `main` at `007b437` (run 41961450776) ran the whole suite: 2149 passed, 5 skipped; its log does not name the skips.
