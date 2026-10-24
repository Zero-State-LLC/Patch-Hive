# PatchHive specifications

This directory is the feature-specification authority for new work. Existing canonical product laws remain in `docs/CANON.md`; operational truth remains in `CURRENT_STATE.md`.

## Required chain

Every feature follows:

`Journey -> Workflow -> State Transition -> Contract -> Acceptance Test -> Implementation Task`

## Active specifications

- [001 — Rig intelligence (draft)](001-rig-intelligence/spec.md)
- [002 — Patch-book publishing (draft)](002-patch-book-publishing/spec.md)
- [003 — Catalog dataset pipeline (draft)](003-catalog-dataset-pipeline/spec.md)
- [004 — Commerce (draft)](004-commerce/spec.md)
- [005 — Decision Intelligence & Evidence Resolution](005-decision-intelligence/spec.md)
- [006 — Cloudflare Edge Deploy with Clef Classifier](006-cloudflare-edge-clef/spec.md)
- [007 — Evaluation Corpus Freeze & Controlled Staging Enablement (tasks)](007-evaluation-staging-enablement/tasks.md)
- [008 — Dual-Path F5 Cutover & Design Engine Staging Receipts (tasks)](008-dual-path-f5-design-receipts/tasks.md)

## Authority map

1. `.specify/memory/constitution.md` — engineering invariants and specification doctrine.
2. `docs/CANON.md` — adopted PatchHive product canon.
3. `specs/<feature>/` — feature requirements/workflows/contracts/acceptance.
4. `CURRENT_STATE.md` — observed live repository posture.
5. `docs/ROADMAP.md` / `docs/CONTINUATION.md` — sequencing.
6. Other `docs/` — supporting design, operations, evidence, or historical material as labeled.

When documents conflict, do not guess: flag drift and reconcile explicitly.
