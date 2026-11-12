# Next

The current hand-off: latest review verdict and the next work order. Whoever finishes a slice or a review overwrites this file. Read it at the start of a session.

**Updated:** 2026-11-12. 0.3.0-alpha.21 (`e38a9ec`) is deployed to staging and production, so engine 1.4.0, the jack notes and the jack count are live. Health, smoke and the staging generate check passed.

The plan is [docs/evidence/NEXT_SLICES_2026-11-10.md](../evidence/NEXT_SLICES_2026-11-10.md), N1–N10.

## Waiting on the owner

Each item is gated: a merge you name, or a yes for a deploy, migration, dispatch or load.

1. **N7, #336:** a staging dispatch of `staging-walkthrough.yml` with `checks: generated-export`. That closes the beta exit gap for a customer's own run.
2. **N8, #398 (invite-only sign-up):** merge, run `db-migrate.yml` for staging and production (`20261110_beta_invites`), then deploy. Mint a code at `/admin/invites` before staging sign-up closes.
3. **N9, #399:** merge. The VoiceOver, Safari and PDF pass in `docs/evidence/ACCESSIBILITY_PASS_BETA.md` is yours.
4. **N10, #402:** merge, then `db-load.yml` dry runs on staging and production, and your yes on their hashes. It holds 38 hand-checked jack lists.
5. **N6, #371:** merge when you're ready. Its checks pass.
6. **Standing grant, #400:** your PR. Once merged, the gates above follow it. It also creates this file, so whichever of #400 and this PR merges second needs this file's content kept.
7. `enforce_admins` on `main` is still off. Restore it when merging is done:
   `gh api -X POST repos/Zero-State-LLC/Patch-Hive/branches/main/protection/enforce_admins`

## Verdicts

- **N8 security review:** a read-only trace of the invite commit found no vulnerabilities at the required confidence. Two sign-ups racing for one code weren't tested against Postgres.
- **N10 hand checks:** two samples of 25 lists, where only one reading called the document complete, found 20 and 18 complete. Only the 38 confirmed lists are proposed. The other 76 candidates stay out until checked.
- **Loaded v1 lists flagged by N10's new gates:** QPAS, AVS-S&R-1, Pittsburgh Modular Sequencer and ACL Variable Sync VCO group several jacks under one name. Correcting a declared list needs a correction manifest, because the loader never overwrites one.

## Next for the agent

- A correction for the four grouped v1 lists.
- Catalog: Infrasonic Warp Core's width (4 HP on file, 12 HP in its manual), and three 1U tiles in the Eurorack catalog.
- Reserve slice: spec 002 hardening, T038–T041.

## Missing from this repo

Your global instructions refer to a "Standing grant" section and to `FACTS.md`. Neither exists here yet, so the gates above follow your earlier instructions: merges you name, and an explicit yes for each deploy, migration, dispatch and load.
