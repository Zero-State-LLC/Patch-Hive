# 009: Photo to Patch Book

Status: ready for agent. Written in the to-spec template from the owner's answers of 2026-11-07 ([decisions 57 to 60](../../docs/evidence/OWNER_DECISIONS_2026-11-04.md#photo-first-product-2026-11-07)), with the test seams agreed with the owner. Merging this spec is the owner's T001 confirmation (decision 23). It supersedes decision 35 and [ADR-006](../../docs/adr/ADR-006-public-product-database.md); [ADR-007](../../docs/adr/ADR-007-photo-first-product.md) records why. Vocabulary follows [GLOSSARY.md](../../GLOSSARY.md).

## Problem Statement

I own a Eurorack Rig and want a Patch Book for it. Today PatchHive asks me to choose a Case from its catalog, create a Rig, then place every Module by hand on HP rows before it will generate anything. It works like a module database and rack planner: its main navigation is Modules, Products and Cases. My photos only fill in a list of Modules, and each one still waits for me to place it by hand. The one thing I have in front of me, the Rig itself, is the last thing PatchHive asks about.

The deployed product can't do the job at all yet. Production runs with every feature flag off, so it reads no photo and fulfils no export. Staging fulfils exports, but reads no photo either.

## Solution

I photograph my whole Rig, or take one photo per row for a big Case, and upload it. PatchHive reads every Module and where it sits, and shows the reading on my photo: a numbered box per Module, with its name and its row and HP. I fix what it got wrong by searching the catalog. I correct a position when one is off, and leave out anything that isn't mine. When I confirm, the reading becomes my Rig. I can generate Patches straight away, and export the Patch Book for credits.

The catalog stops being something to browse. It stays as the reference a reading matches against, and as the search I use to fix a misread Module. The Modules, Products and Cases pages leave the main path. The manual editor stays, but only as "correct the layout" inside this journey, and as the way to enter a Rig by hand where photo reading isn't available.

## User Stories

1. As a visitor, I want the home page to say that PatchHive turns a photo of my Rig into a Patch Book, so that I know what the site is for in one glance.
2. As a visitor, I want the main action on the home page to be "Photograph your Rig", so that the photo is where I start.
3. As a visitor, I want to see an example reading and an example book page before I sign up, so that I know what I'll get.
4. As a visitor, I want to be asked to sign in before I upload a photo, so that my photo belongs to my account and isn't public.
5. As a Rig owner, I want to start a new Rig by uploading a photo, without choosing a Case first, so that I don't need to know my Case's model.
6. As a Rig owner, I want short guidance before I take the photo (whole Rig, straight on, even light, one photo per row for a big Case), so that the reading has a fair chance.
7. As a Rig owner on a phone, I want the upload to open my camera, so that I can photograph the Rig where it stands.
8. As a Rig owner with a large Case, I want to add more than one photo and say which rows each covers, so that every row gets read.
9. As a Rig owner, I want to see that my photo is being read, so that I don't leave thinking it failed.
10. As a Rig owner, I want each Module PatchHive found marked on my photo with a number, so that I can match the list to the Rig.
11. As a Rig owner, I want each reading to show the Module's name, its row and its HP span, so that I can check it against the Rig.
12. As a Rig owner, I want to see how sure PatchHive is about each Module, in words rather than numbers, so that I know which ones to check.
13. As a Rig owner, I want the Modules PatchHive is unsure of listed first, so that I spend my time where it's needed.
14. As a Rig owner, I want to choose between the few closest matches for a Module PatchHive isn't sure of, so that a fix takes one tap.
15. As a Rig owner, I want to search the catalog to replace a misread Module, so that I can fix any mistake.
16. As a Rig owner, I want to mark a box as "not a Module" (a Blank Panel, a cable, a hand), so that it never becomes part of my Rig.
17. As a Rig owner, I want Blank Panels shown as empty HP rather than as Modules, so that my Rig is right.
18. As a Rig owner, I want to add a Module PatchHive missed, at a position I choose, so that the Rig is complete.
19. As a Rig owner, I want to leave a Module out of my Rig, so that a borrowed or broken one doesn't shape my Patches.
20. As a Rig owner with a DIY or unlisted Module, I want it shown as unknown rather than guessed, so that PatchHive never invents what it can't see.
21. As a Rig owner, I want to correct a Module's row or HP position when the reading is off, so that the Rig's layout matches the hardware.
22. As a Rig owner, I want to be told when two Modules would overlap or a row overflows, so that I fix the layout before confirming.
23. As a Rig owner, I want to name my Case from the catalog if I want to, so that row widths and power come from the real Case.
24. As a Rig owner without a known Case, I want row widths taken from what the photo shows, so that I'm not blocked on a Case I can't name.
25. As a Rig owner, I want to confirm the whole reading in one step, so that my Rig exists as soon as I agree with it.
26. As a Rig owner, I want nothing from a reading to become part of my Rig until I confirm it, so that my Rig only holds what I agreed to.
27. As a Rig owner, I want to generate Patches straight after confirming, with no separate placing step, so that the photo really is the whole input.
28. As a Rig owner, I want a clear reason when Patches can't be generated, such as no confirmed Module or an unknown jack, so that I know what to fix.
29. As a Rig owner, I want to export the Patch Book from the same screen, priced in credits before I commit, so that the journey ends where it started.
30. As a Rig owner, I want a new photo of a changed Rig to make a new Rig revision, so that my earlier Patches and books stay as they were.
31. As a Rig owner, I want to retake a photo that came out badly before anything is confirmed, so that one bad photo doesn't cost me the Rig.
32. As a Rig owner, I want to know my photo is kept for 30 days by default and then deleted, so that I know what happens to it.
33. As a Rig owner, I want to delete a photo myself, so that I control my images.
34. As a Rig owner, I want the reading screen to work with a keyboard and a screen reader, listing each Module with its row and HP in text, so that I don't need to see the photo.
35. As a Rig owner, where photo reading isn't open yet, I want to be told so plainly and offered manual entry, so that I can still get a Patch Book.
36. As a Rig owner entering a Rig by hand, I want to search the catalog and place Modules on rows, so that the fallback still leads to a book.
37. As a Rig owner, I want "My Rigs" in the navigation to open my Rigs, newest first, so that I can return to a Rig and its books.
38. As a Rig owner, I want the navigation to hold only the journey (my Rigs, Patches, my account), so that the site doesn't read as a module database.
39. As a visitor following an old link to the Modules, Products or Cases pages, I want to land on the home page rather than an error, so that old links still lead somewhere useful.
40. As an operator, I want the catalog's admin tools to stay, so that I can keep the reference that readings match against correct.
41. As an operator, I want every reading stored as evidence, with the provider, its version and the photo's hash, so that any Rig revision can be traced to what was read.
42. As an operator, I want photo reading to stay off in production until the evaluation is signed and counsel has answered, so that no one's photo reaches a provider before that.
43. As an operator, I want a staging walkthrough that starts from a photo and ends with an exported book, so that the deployed journey is tested, not a seeded Rig.
44. As an operator, I want readings to fail closed when the provider is off, slow or wrong, so that a failure never turns into a guessed Rig.

## Implementation Decisions

### The journey and its screens

- The home page's primary action is "Photograph your Rig". It leads to sign-in for a visitor and to the photo step for a signed-in Rig owner. Below it, the home page shows one fixed example: a Rig Photo with its Reading, and one page of the Patch Book made from it. Both come from fixtures, not from anyone's account.
- The primary navigation is My Rigs, Patches and Account, plus Admin for an Admin. My Rigs lists the owner's Rigs, newest first. Modules, Products and Cases leave the navigation, and their routes redirect to the home page (decision 58). The admin catalog tools stay.
- The journey has four screens: Photo, Reading, Rig, Book.
  - **Photo.** One or more photos, each with the rows it covers, after short guidance: the whole Rig, straight on, in even light, one photo per row for a big Case. On a phone the file input opens the camera.
  - **Reading.** The photo with numbered boxes beside a list of the same Sightings. This is where every correction happens.
  - **Rig.** Generate, the generated Patches, and their runs.
  - **Book.** Style choice and export, as today.
- The existing placement editor becomes the reading screen's "Correct the layout" view. It is also the manual-entry path where photo reading is unavailable. Choosing a Case is optional in both.

### Rigs start from a photo

- A Rig can be created with no Case. Today a Rig's Case is required at every layer: the stored reference can't be empty, and creating or validating a Rig needs it. So this needs a migration that makes the reference optional, and validation, the Rig revision's content and the patch view's drawing must each handle a Rig with no Case. That migration moves the head named in the two acceptance tests and in the production deploy script.
- Starting a Rig from a photo creates the Rig and stores the photo as evidence in one request. The current upload route needs an existing Rig, which needs a Case, and this replaces that order.
- Each photo is evidence under the Rig, with the retention, expiry and deletion rules that photos already have: 30 days by default, 90 at most (decision 26), deleted with the account. Photos are never public.
- Photos need a signed-in owner.

### A Reading and its Sightings

- A photo's **Reading** is evidence, never canon. It has a status (`reading`, `read` or `failed`, then `confirmed` or `superseded`), the provider and its version, the photo's hash and the decision policy version, and a list of **Sightings**.
- A Sighting is one thing seen in the photo:
  - `box`: the bounds in the photo, normalised from 0 to 1.
  - `kind`: one of `module`, `blank_panel`, `unknown` or `not_eurorack`.
  - `row_index`: counted from the top, 0-based.
  - `start_hp` and `hp`: estimated from the photo. Once the identity is confirmed, `hp` comes from the catalog.
  - `candidates`: at most five catalog Modules, each with a score. This is spec 005's bounded candidate identity, applied per Sighting.
  - `disposition`: set by the deterministic DecisionPolicy (spec 005), never by the provider.
- A `blank_panel` is shown as empty HP and can never become inventory. An `unknown` Sighting is never filled with a guessed identity (constitution 3).
- The provider is NVIDIA's vision model through the Clef adapter (spec 006). It returns every Sighting in a photo in one structured answer. A malformed answer, a timeout or a disabled provider ends the Reading `failed` with a reason code, and stores no Sightings.
- A photo that covers rows *i* to *j* counts its Sightings' `row_index` in the Rig's rows, starting at *i*.
- The Reading screen refreshes until the Reading is `read` or `failed`. A `failed` Reading shows its reason in words, with Retry.
- **Retry** reads the same stored photo again as a new Reading, and the failed one becomes `superseded`. It is refused when the photo has expired or been deleted, and the owner retakes instead: a Reading never outlives its photo.
- A **Retake** is a new photo that names the Reading it replaces, which becomes `superseded`. A new photo that names none is another photo of the Rig, so two photos of one row never cancel each other.
- Dispositions are shown in words: "Sure", "Check this" or "Couldn't tell". The list puts "Couldn't tell" first, then "Check this", then "Sure", and orders each group by row and HP.
- A recorded provider answer replays a Reading with no network. Tests use it, and so does the staging walkthrough until spec 007 enables the live provider there.

### Confirming a Reading

- Confirming applies to the whole Rig, across every current Reading of it, and needs each of those Readings to be `read`. A `superseded` Reading isn't current. It submits the final list for the rows those Readings cover: each kept Sighting with its chosen catalog Module and position, any Module added by hand, the Sightings left out, and an optional Case.
- Placements on rows no current Reading covers stay as they are: a photo of one row says nothing about the others. The overlap and Case checks run across the whole resulting Rig.
- It creates a new, immutable Rig revision (ADR 0001) authored as a photo confirmation, and that revision's placements are the confirmed positions.
- Confirmed positions count as placement (decision 59, superseding decision 35). Readiness for generation no longer waits for manual placement, and "still to place" lists only confirmed Modules that have no position.
- Confirmation refuses overlapping HP within a row. It also refuses a row wider than its Case, when a Case is named. Each refusal names the Modules involved and changes nothing.
- With no Case, a row's width is the span of its confirmed Modules, and the power budget is reported as unknown, never as zero.
- A later photo of the same Rig makes a new Reading. Confirming it makes a new revision. Earlier runs and books stay as they were (spec 001 FR-020).

### Generation and the Book

- Generation and export are unchanged (specs 001, 002 and 004): generation uses confirmed inventory only, and an export costs credits. Reading a photo and confirming it are free.
- The Rig screen shows generation's existing `NOT_COMPUTABLE` reasons in plain words.

### Where photo reading is available

- A read-only capability answer tells the frontend whether photo reading is open on this host, and why not when it isn't. When it's closed, the Photo screen says so and offers manual entry. It never accepts an upload that nothing will read.
- Production keeps photo reading off until three things hold:
  - Spec 007's chain reaches a signed receipt, measured on whole-rig photos.
  - Counsel has answered decision 33.
  - The production evidence-expiry job is in place (decision 21).
- Enabling it is an operator action, never a code default.

### Evaluation (spec 007)

- The evaluation corpus's unit becomes a whole-rig photo. Each photo is labelled with every Module's identity, `row_index` and `start_hp`, plus its Blank Panels.
- The measures are:
  - Identity accuracy per Sighting.
  - Detection recall and precision.
  - Position error in HP.
  - False canonicalization, which must stay zero.
- Thresholds are proposed and approved per spec 007.

### The catalog's role

- The catalog is the reference that Readings match against and the search used to fix a Sighting. It is no longer a public product to browse (ADR-007).
- Anonymous reads of the catalog API are unchanged by this spec. Decision 39's question stays with counsel.

### States

The journey's own machine, per Rig photo. Generation runs keep spec 001's machine.

| From | Event | Guard | To |
|---|---|---|---|
| none | upload | signed in; photo reading available | `reading` |
| `reading` | provider answers | answer parses and every Sighting is bounded | `read` |
| `reading` | provider fails, times out or is off | any | `failed` |
| `failed` | retry | photo reading available; the photo is still stored | `superseded`, with a new Reading of the same photo `reading` |
| `failed` | retry | the photo has expired or been deleted | `failed`, refused |
| `read` | confirm (for the whole Rig) | every current Reading of the Rig is `read`; no overlap; no row past a named Case | `confirmed`, with one new Rig revision for all of them |
| `read` | confirm (for the whole Rig) | a Reading still `reading` or `failed`, an overlap or an overflow | `read`, refused, nothing written |
| `read` or `failed` | retake (a new photo naming this Reading) | photo reading available | `superseded`, with the new photo `reading` |

Illegal:
- A Sighting reaching inventory without a confirmation.
- A `blank_panel` or `unknown` Sighting becoming a Module without the owner choosing one.
- A confirmed revision being edited, when a change has to make a new revision.
- An upload accepted while photo reading is unavailable.

## Testing Decisions

- A good test drives the journey from outside, through HTTP requests, and checks what a user or a later step can observe: the Reading's Sightings, the new Rig revision and its placements, readiness, the run, and the exported pack. It never checks which function was called.
- **Seam 1, the API journey.** This is the main seam, run in CI with no network. It covers:
  - Upload a fixture photo with a recorded provider answer.
  - Read the Sightings, and confirm with one correction, one left out and one Blank Panel.
  - Readiness is true with no manual placement.
  - Generate a run and export a book with inline fulfilment.
  - The pack names exactly the confirmed Modules.
  - Repeat with the provider off: the Reading fails closed and nothing reaches inventory.

  Prior art: the golden-demo export acceptance tests, spec 001's transitions tests for generation and readiness, the evidence tests that use the fake vision provider, and the export API tests that use the fair-use grant.
- **Seam 2, the staging walkthrough.** It starts from a fixture photo, which is the owner's own photo per decision 33, instead of the seeded Rig. It replays the recorded provider answer until spec 007 enables the live provider on staging. Its receipt records the Reading, the revision, the run and the export. Prior art: the staging walkthrough workflow and its design walkthrough receipt.
- The existing browser tests, which mock the API, are updated for the new home page, navigation and reading screen. They are not a third seam.

## Out of Scope

- Reading cables, knob positions or panel text from a photo. A Reading identifies Modules and where they sit, and nothing else.
- Identifying the Case model from a photo. Naming a Case stays optional and manual.
- Formats other than Eurorack.
- Enabling the provider in production, which is the operator chain above.
- Prices, credits and commerce rules.
- Deleting the catalog data, its pipeline (spec 003) or its admin tools.
- A native mobile app. The upload uses the browser's file and camera input.

## Further Notes

- **Downstream changes.** This spec changes these, and each has a dated note:
  - Spec 001: a Rig is what was confirmed from a photo, and decision 35 is superseded.
  - Spec 003: the catalog's role.
  - Specs 005 and 006: per-Sighting candidates from one whole-rig answer.
  - Spec 007: the corpus unit and the owner's photo request.
  - Spec 008: the walkthrough's starting point.
  - Spec 002 and spec 004 don't change.
- **Not deployed anywhere today.** As of 2026-11-07, neither host reads photos. Production also fulfils no export. Until spec 007 and counsel clear photo reading, the manual-entry path is the only way to a book in production, and only once production fulfils exports.
- **Accuracy is unknown.** No whole-rig corpus exists yet, so no one knows how well a Reading performs until spec 007's baseline runs. The manual path and the reading screen's corrections exist so that a weak Reading still ends in a correct Rig.
