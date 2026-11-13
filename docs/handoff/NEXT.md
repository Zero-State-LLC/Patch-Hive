# Next

The current hand-off: the latest review verdict and the next work order. Whoever finishes a slice or a review overwrites this file. Read it at the start of a session.

**Updated:** 2026-11-13 UTC. Staging and production both run 0.3.0-alpha.22 (`098126b`), and only staging requires an invite to sign up. #371 merged after the tag and goes out with the next release (#408).

The plan is [docs/evidence/NEXT_SLICES_2026-11-10.md](../evidence/NEXT_SLICES_2026-11-10.md), N1–N10. All ten are merged.

## Waiting on the owner

Each item is gated: a merge you name, or a yes for a deploy, migration, dispatch or load.

1. **Mint invites on staging.** Staging sign-up is closed now. Mint codes at `/admin/invites` for the beta's testers. Each code works once and adds its test credits to the new account.
2. **N9:** the VoiceOver, Safari and PDF pass in `docs/evidence/ACCESSIBILITY_PASS_BETA.md` is yours. The beta's accessibility exit criterion stays open until it's logged.
3. **#408 (release 0.3.0-alpha.23, carrying #371):** merge right before the next deploy.
4. **Merging:** main requires a code owner's approval and the repository has auto-merge turned off, so every merge is an admin bypass and needs your words each time. `enforce_admins` on `main` is still off. Restore it when merging is done:
   `gh api -X POST repos/Zero-State-LLC/Patch-Hive/branches/main/protection/enforce_admins`

## Verdicts

- **Alpha.22 on production (2026-11-13, on your yes):**
  - Migration run [43393727403](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43393727403).
  - API `178c19eb` and frontend `d608e2ac`. The bundle points only at the production API.
  - Health reports 0.3.0-alpha.22 with `database: ok`, and smoke passes 10/10 (run [43394115279](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43394115279)).
  - Sign-up stays open (`invite_required: false`).
  - The public API still serves all 3,379 Modules, with the 224 + 38 loaded jack lists exactly as committed.
  - Rollback: API `160de78a` and frontend `cc4b0ec6`. The invites table is unused there and can stay.
- **Alpha.22 on staging (2026-11-13):**
  - Migration run [43391485007](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43391485007).
  - Smoke passes 10/10 (run [43392083297](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43392083297)).
  - The generate check (run [43392196504](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43392196504)) and the generated-export check (run [43392310766](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43392310766)) pass.
  - API Worker `749ed7ac` and frontend `a831fdf1`. The bundle points only at the staging API.
  - Every check was dispatched from the tag `v0.3.0-alpha.22`.
  - The export check read 4 PDF pages, 2 patch pages and 2 distinct Operation texts.
  - The refusal was checked with an already-taken username, so no account could have been made either way.
- **Merges of 2026-11-13:**
  - #398 (`a2a044e`), #399 (`318ed6e`), #405 (`b5bf4db`), #404 (`098126b`), #407 (`1e28742`) and #371 (`8694b49`).
  - Each had every required check passing on its head and no open review threads.
  - #371 was updated over #398 first: one conflict in `frontend/src/lib/routeTitles.ts`, resolved by adding the invites row.
- **N10 loads:** on staging (run [43363219819](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43363219819)) and on production on your yes (run [43364697251](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/43364697251)), 38 lists filled with 0 conflicts. Each public API serves all 38 and the earlier 224 exactly as committed.
- **N8 security review:**
  - A read-only trace of the invite commit found no vulnerabilities at the required confidence.
  - Two sign-ups racing for one code weren't tested against Postgres.
  - A real redemption on staging (credits granted once) waits on a minted code.
- **N10 hand checks:**
  - Two samples of 25 lists, where only one reading called the document complete, found 20 and 18 complete.
  - Only the 38 confirmed lists were loaded. The other 76 candidates stay out until checked.

## Next for the agent

- After you mint a code: redeem it once on staging and confirm the credits land once and a second use is refused.
- **The four grouped v1 lists** (QPAS, AVS-S&R-1, Pittsburgh Modular Sequencer, ACL Variable Sync VCO) group several jacks under one name. Spec 003 FR-041 bars the loader from overwriting a declared list, so a fix needs an amendment that allows a reviewed correction first. That amendment is the owner's call.
- Catalog: Infrasonic Warp Core's width (4 HP on file, 12 HP in its manual), and three 1U tiles in the Eurorack catalog.
- Hand-check the next sample of the 76 unchecked jack-list candidates.
