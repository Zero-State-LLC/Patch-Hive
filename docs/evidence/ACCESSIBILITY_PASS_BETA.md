# Accessibility pass for beta exit

**Status: not run.** Every result below is `NOT_COMPUTABLE` until a person fills it in. Protocol and severity classes: [docs/ACCESSIBILITY.md](../ACCESSIBILITY.md). VoiceOver with Safari and the PDF reading-order check are enough to exit beta (decision 22).

| Field | Value |
| --- | --- |
| Reviewer | |
| Date | |
| Source SHA (`/health/ready` version and commit) | |
| Host | `staging.patch-hive.com` |

## What to walk through

Do this with the keyboard, then again with VoiceOver on Safari.

1. Sign in. To check sign-up, use an invite code.
2. Open a Rig, or start one from a photo at `/rigs/new/photo`. Staging can only read recorded photos, so an unrecorded one ends in manual entry, which is part of this walk.
3. Review the reading at `/rigs/<id>/reading` and confirm its Modules.
4. Generate patches, pick a run and open a patch. Listen to the cable table.
5. Export a Patch Book, then download it.

## Results

| Step | Setup | Result (PASS / FAIL / N/A) | Defects (id, severity) | Notes |
| --- | --- | --- | --- | --- |
| 1. Keyboard-only flows | Chrome, no pointer | | | the walk above |
| 2a. VoiceOver | Safari, macOS | | | landmarks, headings, forms, status announcements, tabs, cable table |
| 3. Zoom and reflow | 200% zoom; 320 px | | | the automated pre-pass covers this; confirm by eye |
| 4. Contrast and monochrome | both themes, greyscale | | | cable classes still tell apart |
| 5. Reduced motion | OS setting on | | | the automated pre-pass covers this |
| 6. PDF reading order | the exported Patch Book | | | or the text-first companion |

## Defects

| Id | Step | Severity (S1, S2, S3) | What happens | Fixed in |
| --- | --- | --- | --- | --- |
