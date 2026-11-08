# Plan: 009-photo-to-patchbook

The spec's Implementation Decisions and Testing Decisions are the plan, and [tasks.md](tasks.md) orders them as tickets. This file only adds what the spec leaves to the environment.

## Stack (as built)

The same as spec 001's [plan](../001-rig-intelligence/plan.md): Python 3.11 with FastAPI, SQLAlchemy 2 and Alembic on Postgres 15; React 18 with TypeScript and Vite; the Cloudflare Worker in front of the API (spec 006). Photo evidence storage and expiry already exist (spec 001, decisions 21 and 26).

## Order

1. T010 first: the failing journey tests at the two agreed seams.
2. T020 to T040, the backend: start from a photo, Readings, confirmation, the capability answer. T022 can run beside T030.
3. T050 and T051, the frontend, once the backend contracts pass.
4. T060 and T070, whose `b` halves wait on the owner's photos.
5. T080, last, on the operator's word.

## Convergence (T090)

T090 checked every user story and Implementation Decision against the code on 2026-11-07, at `e1e03dd`. It found these drifts. Each is fixed, waiting on the owner, or left with a reason. The story-by-story status is added to spec.md when the last of them closes.

| # | Drift | Stories | State |
|---|---|---|---|
| D1 | T010 set Seam 2's contract as spec 008's walkthrough receipt carrying the Reading (`PhotoReadingEvidence`, `capture_walkthrough_receipt(reading=)`). T060a built a separate photo walkthrough with its own receipt instead, and left T010's four strict xfails in place. Spec 008's note says its walkthrough starts from a photo "instead of the seeded Rig". | 43 | Fixed: the owner kept the two walkthroughs apart (decision 62). Seam 2 is tested at the photo walkthrough and its receipt, which now also checks that the Reading comes before generation and the book and that the receipt never holds the photo. T010's xfails for the contract not built are gone. Spec 008's note says what's built. |
| D2 | The spec said confirming makes a Rig revision "authored as a photo confirmation", and always a new one. A Rig revision is named by its content and shared with generation of the same layout. The authorship lives on the inventory revision sealed with it. | 30 | Fixed (#370): the spec says what was built. |
| D3 | My Rigs listed the owner's Rigs together with everyone's public ones, and an Admin's list held every Rig. | 37 | Fixed (#370). |
| D4 | A run that couldn't be computed showed a general hint: the frontend mapped a code the API never sends. | 28 | Fixed (#370). An unknown jack never stops a run: its jacks print by role (spec 002), so it has no reason to show. |
| D5 | The Reading screen could only be reached from the upload, and a new photo only from the Reading screen. | 30, 31 | Fixed (#370): the Rig screen's Photos section. |
| D6 | My Rigs' New went to manual entry, not the photo step. | 2, 5 | Fixed (#370). The photo step still offers manual entry. |
| D7 | The Reading screen's own overlap and past-the-Case warnings didn't name the Modules; only a red border did. | 22, 34 | Fixed (#370). |
| D8 | The home page's example reading wasn't in the Reading screen's order. | 3, 13 | Fixed (#370). |
| D9 | The Rig screen still spoke of inventory evidence and photo/manual confirmation. | 27, 35 | Fixed (#370). |
| D10 | Nothing on the site deleted a photo, though the Photo screen said you could. | 33 | Fixed (#370): each kept photo on the Rig screen, with the day it goes. |
| D11 | A Case can't be named on the Reading screen, manual entry refuses a Rig with no Case, and the Rig screen draws no rail for a Rig with no Case. The placement editor also couldn't place anything on a Rig with no Case, so a Rig started from a photo couldn't be corrected there. | 23, 24, 36 | Fixed (#372): the Reading screen names a Case, the editor goes on without one and places on open rows, and the Rig screen draws a Rig with no Case. |
| D12 | Export shows the balance but not the export's price before it is committed. | 29 | Fixed (#374): the commerce answer names `export_cost`, and the Rig screen's and the Style Studio's exports show the price, or the plan that covers it, before the click. They wait while the balance is short or the price didn't load. |
| D13 | The home page has an example reading as text, with no photo, no boxes and no book page. | 3 | A later PR, or with T060b's owner photo. |
| D14 | The placement editor still has spec 005's per-Module photo step. It uploads outside spec 009's photo reading on every host, and its mock provider makes up candidates from each photo's hash. Each must still be confirmed by hand, and production accounts aren't open yet. | 20, 35 | Fixed (#373): the owner had it removed (decision 63). The mock detector never runs in production, so a photo sent to that API there is stored and no candidate is made up. Staging keeps it for its evidence check on a test card (006 T060b). |
