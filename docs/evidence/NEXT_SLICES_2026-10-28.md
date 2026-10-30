# Next slices (2026-10-28)

**Status 2026-10-29:** A1 (#118), A2 (#119), A3 (#121), A4 (#122) and A5 (#123) are done and deployed. Also done: a second retirement (#120), C2 (seed scripts deleted, #124) and C1 (reviewed corrections, #125, in review). C3–C6 wait on the owner; see [research.md](../../specs/003-catalog-dataset-pipeline/research.md).

Planned after #116. Staging and production both run main (`c59b2db`) and hold the same catalog: 3,916 visible modules from 364 brands. Each slice is one PR (or one operator task) and is on [Project #8](https://github.com/orgs/Zero-State-LLC/projects/8). Order is the recommended order within each group.

## A. Engineering, no decision needed

### A1. Unknown power per rail in rack budgets

- **Why:** a NULL draw counts as 0 mA, so an over-budget rack can pass (decision note §1). This is the largest correctness gap left in rig validation.
- **Scope:**
  - `racks/validation.py` and `cases/compatibility.py`: a rail with any unknown draw is `incomplete` ("≥ X mA + N unknown"), and a NULL +5V counts as unknown.
  - `RackBuilder.tsx`: per-rail counts, and the known -12V is kept when +12V is NULL.
  - One rounding rule shared by the overlay script and the loader.
- **Done when:** tests cover each rail; an existing over-budget fixture fails; a staging rack shows per-rail unknowns.
- **Size:** medium (backend and frontend).

### A2. Refuse shared homepages at crawl time (003 T030)

- **Why:** #116 added the guard to overlay builds only. The crawler can still give a brand another maker's site, and an operator would see it only after a build.
- **Scope:** `catalog_maker_crawl.py` resolution checks a resolved host against brands already resolved to it and records a conflict in the dry-run receipt instead of crawling.
- **Done when:** tests reproduce the seven known cases (Mental Noise, three Noise Engineering aliases, EAR, d:Machinery, Winter Plankton) from the committed v1 resolution data, with no fetches.
- **Size:** small.

### A3. Seven new crawl rows (catalog-additions-v6, power v14)

- **Why:** 2hp Mix, Bastl Aikido, three Bastl Citadel modules and Tubbutec USB bridge A were crawled but are in no overlay. The card's v5/v13 names were used by #116; the Doepfer case row stays excluded.
- **Done when:** loads through the usual path: replay, staging dry run, apply, prod dry run, apply on the owner's yes.
- **Size:** small.

### A4. Rack warning for tombstoned placements

- **Why:** tombstoned modules are hidden from browse, but a rack that already holds one gets no warning. No prod rack does today; one could once users build racks.
- **Scope:** rack validation adds a `MODULE_TOMBSTONED` warning naming the reason and the live twin when the manifest has one.
- **Size:** small.

### A5. Signed-out refresh noise

- **Why:** every signed-out page load calls `/auth/refresh` and logs a 401 in the console.
- **Scope:** only refresh when a session marker says one may exist (for example a non-HttpOnly `ph_has_session` hint set on login and cleared on logout).
- **Size:** small.

## B. Operator (yours)

1. **Real sign-up on production.** Create an account on patch-hive.com, sign in and out, and sign out everywhere. I can't create accounts on production.
2. **008 T030b:** verify seeded demo auth on the staging host.
3. **Repo visibility versus the Actions budget.** Public now so CI runs. Going private again needs a budget or a spending limit on the org first, otherwise every check fails in seconds.
4. **Housekeeping:**
   - VirusTotal reanalysis and the nine vendor false-positive reports;
   - rotate the context.dev and OpenRouter keys;
   - add `PROJECT_TOKEN`, so new PRs reach this board (none of #82–#116 did);
   - add `RELEASE_PLEASE_TOKEN`.
5. **Review open PRs:**
   - #110 (opt-in container startup migrations);
   - #111 (CODEOWNERS);
   - #109 (release 0.3.0-alpha.4);
   - #106 (zod bump).

## C. Owner decisions, then engineering

| Slice | Decision | Recommendation |
|---|---|---|
| C1. HP correction action (Sovage CHICANE 14 → 4) | Manifests may carry corrected values (decision note §3) | Yes: a `correct` action that archives the old value and updates under `only_if_value` |
| C2. Delete `seed_catalog_from_synth.py` (both copies) | Decision note §4; the registry no longer needs it (#114) | Delete, and drop its unit test |
| C3. Frap listing adapter (003 T026) | A paid cap for context.dev renders | Free dry run first, then 20–60 renders |
| C4. Rebuild the crawl cache and classify 644 untagged rows (003 T031) | A paid cap; only worth it with C3 or another re-parse | Pair with C3 so one re-crawl serves both |
| C5. Jumper-dependent power (`power_configs`) | Decision note §1 | After A1 |
| C6. Spec confirmations (001–004 T001) | Operator confirms each spec | One sitting per spec; unblocks each plan.md |

## D. Later

- Decision Intelligence provider in staging (005 T061/T062/T070, 007): thresholds from the baseline need approval first.
- Hyperdrive binding to the Neon staging branch (006 T050, T060b).
- Beta checklist items on the board (backup/restore drill, accessibility protocol, Playwright against staging).
