# Next

The current hand-off: latest review verdict and the next work order. Whoever finishes a slice or a review overwrites this file. Read it at the start of a session.

**Updated:** 2026-11-13 UTC. Staging and production run 0.3.0-alpha.21 (`e38a9ec`). Since then #336 (N7) and #402 (N10) merged, and N10's 38 jack lists are loaded on staging only.

The plan is [docs/evidence/NEXT_SLICES_2026-11-10.md](../evidence/NEXT_SLICES_2026-11-10.md), N1–N10.

## Waiting on the owner

Each item is gated: a merge you name, or a yes for a deploy, migration, dispatch or load.

1. **N10 production load:** your yes to run `db-load.yml` on prod in apply mode with `plan_hash` `35bbeeb171a8c538041c9a00734bb4b05667e97159ba96e0c4ba4c4804ba6b91` and `inputs_hash` `1c0ec6f1e50f819403d1c371033a965e5603977889c717158a6ae362a43b524a`. It fills 38 empty jack lists and changes nothing else. The staging load with the same hashes is in [CATALOG_MODULE_JACKS_V2_2026-11-12.md](../evidence/CATALOG_MODULE_JACKS_V2_2026-11-12.md). Rollback is the same workflow with the load's run ID.
2. **N8, #398 (invite-only sign-up):** merge, run `db-migrate.yml` for staging and production (`20261110_beta_invites`), then deploy. Mint a code at `/admin/invites` before staging sign-up closes.
3. **N9, #399:** merge. The VoiceOver, Safari and PDF pass in `docs/evidence/ACCESSIBILITY_PASS_BETA.md` is yours.
4. **N6, #371:** merge when you're ready. Its checks pass.
5. **#405 (spec 002 T038–T041, publishing hardening):** merge when you're ready. Publishing stays off through the beta (decision 34).
6. **#404 (release 0.3.0-alpha.22):** merge right before the next deploy, so the tag matches what runs. Since alpha.21 the only code change outside tests is an optional `on_pack` hook in the staging walkthrough helper, which only staging scripts call (#336), so the API behaves the same.
7. **Merging:** main requires a code owner's approval and the repository has auto-merge turned off, so every merge is an admin bypass and needs your words each time. `enforce_admins` on `main` is still off. Restore it when merging is done:
   `gh api -X POST repos/Zero-State-LLC/Patch-Hive/branches/main/protection/enforce_admins`

## Verdicts

- **N7:** the staging check that exports a generated run passed on the PR's head (run [43328058772](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43328058772)): 4 pages, 2 patch pages, 2 distinct Operation texts, no failures. Beta exit criterion 2 has its check. It hasn't been dispatched from `main`.
- **N10 staging load:** 38 lists filled, 0 conflicts, and the public API serves all 38 and the earlier 224 exactly as committed.
- **N8 security review:** a read-only trace of the invite commit found no vulnerabilities at the required confidence. Two sign-ups racing for one code weren't tested against Postgres.
- **N10 hand checks:** two samples of 25 lists, where only one reading called the document complete, found 20 and 18 complete. Only the 38 confirmed lists were loaded. The other 76 candidates stay out until checked.

## Next for the agent

- **The four grouped v1 lists** (QPAS, AVS-S&R-1, Pittsburgh Modular Sequencer, ACL Variable Sync VCO) group several jacks under one name. Spec 003 FR-041 bars the loader from overwriting a declared list, so a fix needs an amendment that allows a reviewed correction first. That amendment is the owner's call.
- Catalog: Infrasonic Warp Core's width (4 HP on file, 12 HP in its manual), and three 1U tiles in the Eurorack catalog.
- Hand-check the next sample of the 76 unchecked jack-list candidates.
