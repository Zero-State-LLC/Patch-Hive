# Next slices (2026-11-10)

Planned after #391. Staging and production both run `88efb73` (0.3.0-alpha.20), with 224 Module jack lists loaded on both. The next milestone is the closed staging beta. Each slice is one PR. They use the prefix N because A, B and C already have two meanings in this repo's history.

Of the 53 open spec tasks, 5 can be finished without the owner, and 43 wait on something only the owner or a third party can supply, such as Rig photos, an offline signature or counsel. So these slices come mostly from what a person would hit today, and from the beta exit list.

**Owner's calls, 2026-11-10:**

- When several jacks could take a cable and none matches by name, a Patch Book keeps the role name.
- The closed beta has invite-only sign-up on staging, and each invite carries test credits.

## Slices

### N1. Records match reality

- **Why:** later work gets planned from records that are wrong.
- **Scope:** this list; `CURRENT_STATE.md` and `docs/ROADMAP.md`; spec 001's OQ-11 count; Project #8 and `docs/KANBAN.md`.
- **Done when:** `check_spec_dag.py` passes and a re-read of the board shows the corrected cards.
- **Size:** small.

### N2. Engine 1.4.0: stop guessing a jack

- **Why:** on about 15 of 34 oscillators the FM cable lands on the first CV input (2hp Pluck "Damp CV"), and on 15 of 20 VCAs the CV cable does the same. Nothing marks these as guesses.
- **Scope:**
  - `patches/validation.py` `_pick` tries an exact name, then keywords, then a sole candidate of the right type. With several candidates and no name match, the cable keeps its role name.
  - Keyword rules for the roles that have none, and "v/o" for pitch. Numbered roles match on their number, so a mixer still gets Input 1 and Input 2.
  - `patch_engine_version` to 1.4.0, and `docs/PATCH_ENGINE.md`, including its out-of-date claims that port names are all generic.
- **Done when:** tests pass on real name forms from the lists, and the PR shows how many of the 224 lists change.
- **Size:** medium. Needs a deploy.

### N3. A Patch Book says why a jack is generic

- **Why:** the note says the real names aren't on file, even when they are. 30 of the 178 lists a patch rule can reach hit this, and N2 makes it more common.
- **Scope:** split `page_notes` in `export/patchbook/design/engine.py` into three cases: no list on file, several jacks could take this cable, and no jack of that kind on the list.
- **Done when:** each case has a test, and a rebuilt book prints the right note.
- **Size:** small. Needs a deploy.

### N4. Show how much of a Rig has jack names

- **Why:** only 226 of 3,379 public Modules declare jacks, so most Rigs are partly generic and nothing says so. Port coverage and per-cable `port_status` are stored but unread.
- **Scope:** "Jack names on file for 3 of 12 Modules" in the Patch Book and on the Rig page. Rig scores aren't computed over the subset, because that would change decision 11.
- **Done when:** a mixed Rig shows the right count in both places.
- **Size:** medium. Needs a deploy.

### N5. Categories for Modules that already have jack lists

- **Why:** 20 Modules with lists have no category, so no patch rule can use them. Four drums filed as VCO get pitch cables.
- **Scope:** an overlay read from the 2026-11-09 crawl, at no spend, using existing categories. Anything needing a new category waits for the owner.
- **Done when:** dry runs on both databases, the owner's yes on hashes, then the load and a read of the public API.
- **Size:** small.

### N6. Finish #371

- **Why:** per-page head tags, a link preview, the favicon set and admin loading states are done but unmerged.
- **Scope:** update the branch and rerun the two checks that failed on infrastructure.
- **Done when:** checks are green and the owner names the merge.
- **Size:** small.

### N7. Finish #336

- **Why:** the walkthrough only exports the seeded run, so a customer's own run has never been exported in a check.
- **Scope:** rebase, recheck against engine 1.4.0, and settle what fails the check, including names the PDF standard fonts can't print.
- **Done when:** the dispatch passes on staging at the deployed commit, on the owner's yes.
- **Size:** small.

### N8. The beta door

- **Why:** anyone can sign up on staging, and new accounts have no credits, so export answers 402.
- **Scope:** an invite table and migration; sign-up needs a valid unused code when the flag is on; redemption grants test credits once through the existing ledger; an admin way to mint codes; a sign-up field. The flag is set on staging only.
- **Done when:** tests cover a missing, wrong and used code, one grant per code, and flag-off behaving as today.
- **Size:** medium. Migration and deploy each need the owner's yes.

### N9. Accessibility protocol matches the product

- **Why:** the pre-pass still names the Modules and Cases screens #367 deleted, and omits photo and reading.
- **Scope:** update the protocol's screens and doc, and prepare the log for the owner's VoiceOver, Safari and PDF pass (decision 22).
- **Done when:** the pre-pass is green in CI. The exit criterion stays open until the manual pass is logged.
- **Size:** small.

### N10. More jack lists from the readings already paid for

- **Why:** up to 91 more Modules have two readings that gave identical lists, where one reading called its list full. That count is before the other gates.
- **Scope:** after N2, because a partial list is safer once the engine stops guessing. A gate option in `scripts/read_module_jacks.py`, an FR-041 amendment, a hand check of at least 25, and `overlays/module-jacks-v2.json`.
- **Done when:** dry runs, the owner's yes on hashes, the load, and a read of the public API.
- **Size:** medium.

## Left out

- Spec 002 hardening, T038–T041: first reserve if a slice drops out. Publishing stays off through beta (decision 34).
- 003 T092's schema gaps, a rule for roles a complete list rules out, a Unicode PDF font, a provenance column for jack lists, 006 T101c's expiry job and a script for the T055b check.
- The evaluation and signing chain, and 009 T060b and T080. These wait on the owner's Rig photos, signature and counsel.
