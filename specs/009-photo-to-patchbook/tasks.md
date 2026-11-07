# 009 Tasks: Photo to Patch Book

Each task is a ticket sized for one fresh context window. **AFK** tickets are fully specified, so an agent can take one away from the keyboard. **HITL** tickets need a person. Each ticket's contract is [spec.md](spec.md); this file holds only the order and what done means. A task that pairs code with an operator action is split: `a` is the code, `b` the operator action. `scripts/check_spec_dag.py` checks this file.

- [x] T001 Confirm the spec with the owner. Done 2026-11-07: the owner answered the four open decisions (57 to 60) and agreed the test seams. Merging this spec is the confirmation (decision 23).
  - depends_on: []
- [ ] T010 (AFK) Write the journey's failing tests at the two agreed seams before any code. Seam 1 is the API journey with a recorded provider answer, covering every step in Testing Decisions, including the provider-off case. Seam 2 is the walkthrough receipt's new fields, as a test of the receipt builder. Done when they fail for the missing behavior, not for a setup error.
  - depends_on: [T001]
- [ ] T020 (AFK) A Rig can start from a photo with no Case. A migration makes the Rig's Case optional, with a downgrade that refuses while caseless Rigs exist. Validation, the Rig revision's content and the patch view's drawing handle a Rig with no Case. One request creates the Rig and stores the photo as evidence, under the existing photo retention, expiry and deletion rules. Uploading needs a signed-in owner. Done when Seam 1's upload step passes, the existing upload and Rig tests still pass, and the migration round-trips on an empty database. The migration moves the head named in the two acceptance tests and the production deploy script.
  - depends_on: [T010]
- [ ] T021 (AFK) Readings and Sightings as evidence: the shape in the spec, a recorded provider answer that replays with no network, and dispositions from the existing DecisionPolicy. A malformed answer, a timeout or a disabled provider ends the Reading `failed` with a reason code and no Sightings. Done when Seam 1's reading steps and the provider-off case pass.
  - depends_on: [T020]
- [ ] T022 (AFK) The NVIDIA prompt and parser through the Clef adapter return every Sighting in one whole-rig answer, bounded to five candidates each. Done when the adapter's tests pass on recorded answers, including malformed and oversized ones. It needs no live call.
  - depends_on: [T021, 006:T020]
- [ ] T030 (AFK) Confirming a Reading makes a new Rig revision whose placements are the confirmed positions. Decision 35 is superseded: readiness counts those positions, and "still to place" lists only Modules with no position. Overlaps and rows past a named Case are refused with the Modules named. With no Case, row widths come from the layout, and power reads as unknown. Done when Seam 1 reaches a run and an exported pack that names exactly the confirmed Modules.
  - depends_on: [T021]
- [ ] T040 (AFK) A read-only capability answer says whether photo reading is open on this host, and why not when it isn't. When it's closed, uploads are refused. Done when the API tests cover open and closed, and production's default answer is closed.
  - depends_on: [T021]
- [ ] T050 (AFK) Frontend journey: the home page's primary action, and the Photo, Reading, Rig and Book screens. The Reading screen shows numbered boxes on the photo beside a text list that works by keyboard and screen reader, closest-match choices, catalog search for a fix, "not a Module", add, leave out, and "Correct the layout". Done when the mocked-API browser tests cover a full journey, including the closed-capability fallback, and the design guard passes on each new screen.
  - depends_on: [T030, T040]
- [ ] T051 (AFK) Navigation: My Rigs, Patches and Account, plus Admin for an Admin. The Modules, Products and Cases routes redirect to the home page, and the admin catalog tools stay. Done when the browser tests check the navigation and each redirect, and no public page links to the removed routes.
  - depends_on: [T050]
- [ ] T060 Staging walkthrough from a photo.
  - depends_on: [T030]
  - [ ] T060a (AFK) The walkthrough starts from a fixture photo with its recorded provider answer. Its receipt records the Reading, the revision, the run and the export. Done when the receipt builder's tests pass.
    - depends_on: [T030, T010]
  - [ ] T060b (HITL) The owner supplies the fixture photo of their own Rig (decision 33), and the operator runs the walkthrough on staging and keeps the receipt.
    - depends_on: [T060a]
- [ ] T070 Whole-rig evaluation (spec 007).
  - depends_on: [T021]
  - [ ] T070a (AFK) Spec 007's corpus admits whole-rig photos labelled with each Module's identity, row and start HP, plus Blank Panels. The harness reports identity accuracy, detection recall and precision, position error in HP, and false canonicalization. Done when the harness tests pass on a two-photo fixture corpus.
    - depends_on: [T021]
  - [ ] T070b (HITL) The owner supplies rights-cleared whole-rig photos for the corpus. This replaces spec 007 T010b's request for photos of single Modules.
    - depends_on: [T070a]
- [ ] T080 (HITL) Production enablement: after spec 007's signed receipt (007:T083), counsel's answer on decision 33 and the production evidence-expiry job (decision 21), the operator turns photo reading on in production. No code default changes.
  - depends_on: [T070b, T060b, 007:T083]
- [ ] T090 Converge the code against the spec, then mark which user stories are done, open, or moved.
  - depends_on: [T051, T060b, T022]
