# Next

The current hand-off: the latest review verdict and the next work order. Whoever finishes a slice or a review overwrites this file. Read it at the start of a session.

**Updated:** 2026-11-13 UTC. Staging and production run 0.3.0-alpha.21 (`e38a9ec`). Since then #336 (N7), #402 (N10), #398 (N8), #399 (N9) and #405 (spec 002 T038–T041) merged. N10's 38 jack lists are loaded on both databases; nothing else since alpha.21 is deployed.

The plan is [docs/evidence/NEXT_SLICES_2026-11-10.md](../evidence/NEXT_SLICES_2026-11-10.md), N1–N10.

## Waiting on the owner

Each item is gated: a merge you name, or a yes for a deploy, migration, dispatch or load.

1. **N6, #371:** you named the merge on 2026-11-13. Merging #398 first left one conflict in `frontend/src/lib/routeTitles.ts`. The fix keeps #371's title-and-description rows and adds `/admin/invites` with the page's own subtitle. Lint, types and 400 unit tests pass locally on the updated head `ab31a2f`. It merges once its CI passes.
2. **Release 0.3.0-alpha.22 (#404):** Release Please has refreshed it to list #398, #402, #405 and #336, and #371 joins once merged. Merge it right before the deploy, so the tag matches what runs.
3. **N8 deploy:** run `db-migrate.yml` with `20261110_beta_invites`, then deploy alpha.22, on staging first and then on production. Staging sign-up closes as soon as the staging Worker runs alpha.22 (`ENABLE_INVITE_ONLY_SIGNUP` is set only there), so mint a code at `/admin/invites` right after. Production gets the table, but its sign-up stays open. Production's migration and deploy each need your yes.
4. **N9:** the VoiceOver, Safari and PDF pass in `docs/evidence/ACCESSIBILITY_PASS_BETA.md` is yours. The beta's accessibility exit criterion stays open until it's logged.
5. **Merging:** main requires a code owner's approval and the repository has auto-merge turned off, so every merge is an admin bypass and needs your words each time. `enforce_admins` on `main` is still off. Restore it when merging is done:
   `gh api -X POST repos/Zero-State-LLC/Patch-Hive/branches/main/protection/enforce_admins`

## Verdicts

- **Merges of 2026-11-13:** #398 (`a2a044e`), #399 (`318ed6e`) and #405 (`b5bf4db`), each with every required check passing on its head and no open review threads.
- **N7:** the staging check that exports a generated run passed on the PR's head (run [43328058772](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43328058772)): 4 pages, 2 patch pages, 2 distinct Operation texts, no failures. Beta exit criterion 2 has its check. It hasn't been dispatched from `main`.
- **N10 loads:** on staging (run [43363219819](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43363219819)) and on production on your yes (run [43364697251](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43364697251)), 38 lists filled with 0 conflicts. Each public API serves all 38 and the earlier 224 exactly as committed.
- **N8 security review:** a read-only trace of the invite commit found no vulnerabilities at the required confidence. Two sign-ups racing for one code weren't tested against Postgres.
- **N10 hand checks:** two samples of 25 lists, where only one reading called the document complete, found 20 and 18 complete. Only the 38 confirmed lists were loaded. The other 76 candidates stay out until checked.

## Next for the agent

- After the staging deploy: health, the smoke suite, the staging generate check and N7's export check, then a sign-up on staging without a code (refused) and with a minted code (credits granted once).
- **The four grouped v1 lists** (QPAS, AVS-S&R-1, Pittsburgh Modular Sequencer, ACL Variable Sync VCO) group several jacks under one name. Spec 003 FR-041 bars the loader from overwriting a declared list, so a fix needs an amendment that allows a reviewed correction first. That amendment is the owner's call.
- Catalog: Infrasonic Warp Core's width (4 HP on file, 12 HP in its manual), and three 1U tiles in the Eurorack catalog.
- Hand-check the next sample of the 76 unchecked jack-list candidates.
