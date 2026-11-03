# Accessibility protocol

Target: WCAG 2.2 AA.

Automated checks cover semantic component behavior and axe analysis of the PatchGraph. The interface provides a skip link, landmarks, semantic headings, visible focus, minimum 44×44 px controls, non-color status text, light/dark themes, and reduced-motion handling.

The PatchGraph has Beginner, Structural, and Diagnostic views; keyboard cable traversal; zoom/fit/reset controls; port-direction text; arrowheads; signal labels; cable line patterns; active modes; feedback explanations; and a synchronized HTML cable table. The SVG is never the only representation.

Manual release protocol:

1. Complete create-rig, photo review, run selection, patch inspection, and export flows using keyboard only.
2. Test VoiceOver/Safari and NVDA/Firefox landmarks, headings, forms, status announcements, tabs, and cable table.
3. Verify focus remains visible at 200% zoom and reflow at 320 CSS px.
4. Verify dark/light contrast and that cable classes are distinguishable with monochrome display.
5. Verify reduced-motion preference removes nonessential animation.
6. Inspect generated PDFs for reading order; use the text-first companion when full tagging is unavailable.

Manual screen-reader and PDF tagging results are `NOT_COMPUTABLE` until performed by a human release reviewer.

## Automated coverage (runs in CI on every PR)

These checks run in `frontend/tests/ui/design.spec.ts`, against a mocked API:

- **Design guard:** every screen, in both themes, at 1440 and 375 px. It runs axe (colour contrast included), checks that nothing sits past the viewport, and checks each screen's signature drawing. An "API down" sweep confirms every data screen shows an alert, never a blank page.
- **Protocol pre-pass**, covering steps 3 and 5 of the manual protocol:
  - **Screens:** home, sign in, modules, cases, patches, account, rig detail and the rig builder.
  - **Reflow:** checked at 320 CSS px and at 640 (a 1280 px window at 200% zoom). Nothing may scroll the page sideways.
  - **Focus:** the first tab stops show a visible focus ring.
  - **Skip link:** it is the first tab stop and moves focus to the workspace.
  - **Motion:** reduced motion leaves no animation running longer than 1 ms.
- **Component tests:** axe on the patch graph and the patch rail, and keyboard tests for tabs, the rail's move keys and the toast.

The release reviewer covers what automation cannot: screen readers, PDF reading order, and judging whether announcements make sense.

## Manual pass log

Copy this table into `docs/evidence/ACCESSIBILITY_PASS_<date>.md` for each release candidate. Record the source SHA and the host, normally `staging.patch-hive.com`.

| Step | Setup | Result (PASS / FAIL / N/A) | Defects (id, severity) | Notes |
| --- | --- | --- | --- | --- |
| 1. Keyboard-only flows | Chrome, no pointer | | | create rig, photo review, run selection, patch inspection, export |
| 2a. VoiceOver | Safari, macOS | | | landmarks, headings, forms, status announcements, tabs, cable table |
| 2b. NVDA | Firefox, Windows | | | same as 2a |
| 3. Zoom and reflow | 200% zoom; 320 px | | | automated pre-pass PASS on CI; confirm by eye |
| 4. Contrast and monochrome | both themes, greyscale | | | cable classes still tell apart |
| 5. Reduced motion | OS setting on | | | automated pre-pass PASS on CI |
| 6. PDF reading order | an exported patch book | | | or the text-first companion |

Severity classes:

| Class | Meaning | Release |
| --- | --- | --- |
| **S1** | blocks a task for a keyboard or screen-reader user (no route, no name, focus trap) | blocks |
| **S2** | the task completes with real difficulty (wrong order, missing announcement, contrast below AA) | fix before beta exit |
| **S3** | friction or polish (verbose labels, redundant stops) | tracked |

Status (2026-11-03): the automated coverage above passes on `main`. The manual pass (steps 1, 2, 4 and 6) has not been run, so its results are still `NOT_COMPUTABLE`.
