# Intent

## Problem

Deep reads of built books found pages with no diagram, module names printed as database ids, and identical Operation text on every page. A person found these by reading PDFs, because the checks read the layout data and not the PDF. Two gaps let the next regression through on a deployed host:

- `scripts/staging/design_engine_walkthrough.py` exports the seeded demo's run, which loads as `compile_on_export`. A customer's run has sealed rows and loads as `generated_patches`. `scripts/staging/generate_check.py` generates a run but never exports it, so the path customers take has never been exported on a deployed host.
- `execute_walkthrough` reduces the downloaded pack to a SHA-256, so a pass says nothing about what the pages print.

## Proposed outcome

`.github/workflows/staging-walkthrough.yml` gets a check that generates a run, exports it with test credits, downloads the zip, opens `PatchBook.pdf` inside the job, and fails if:

- the export didn't load as `generated_patches` (`source/library_index.json`)
- the PDF's page count differs from `validation/book.json`
- a patch page is missing Construction or Operation
- a page prints `UNKNOWN`, `NOT_COMPUTABLE`, a phase tag such as `[prep]`, or "verify prior connection"
- a page prints a raw port id such as `10:Audio Out:output`
- a module on the page isn't named by its brand and name from the pack's `pages/json` data

Unit tests build a small pack with each defect and fail on it.

Out of scope: fixing any page, running the workflow on staging without the owner's go-ahead, merging, and deploying. No page diagram check: the PDF's text can't show whether a diagram was drawn. Identical Operation text on every page fails as `OPERATION_TEXT_REPEATED` (added 2026-11-12), because since #329 the steps come from each patch's own cables.

## Affected users / systems

CI only: one workflow, one new script, one optional dependency group, and a hook on `execute_walkthrough` that hands the downloaded bytes to a caller. No API behavior changes, and the API image doesn't gain the PDF reader.

## Constraints / non-goals

The repo is public, so its workflow logs and artifacts are too. The pack stays in the job's memory. The receipt and the log hold statuses, counts and hashes only, never page text or module names. Test payments only: the check reads the target server's flags first, as the walkthrough does, and fails closed.

## Open questions

**For the owner: should this run on staging?** Nothing has run there yet.

**For the owner: should the check fail on a missing diagram, or when every page has the same Operation text?** Both were defects in the reports that led here. They aren't on this work's list, so the check doesn't fail on them.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The seeded rig's generated run passes every rule through the real generate, export, compose, zip and download routes | `OBSERVED` | `test_a_run_generated_on_the_seeded_rig_through_the_real_routes_passes`, on SQLite |
| The check rejects each listed defect in a real PDF | `OBSERVED` | `backend/tests/unit/test_staging_generated_export_check.py` |
| A module name with a character outside WinAnsi prints as a black square, and the check fails on it | `OBSERVED` | `Instruō Arbhar` reads back as `Instru■ Arbhar`; `test_a_name_the_fonts_cannot_print_fails` |
| The check passes on staging | `NOT_COMPUTABLE` | Not run. It needs the owner's go-ahead |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-06
