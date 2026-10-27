# Spec Kit and DAG audit — 2026-10-26

Scope: `specs/001`–`specs/008`, `.specify/memory/constitution.md`, and task dependency graphs.
Baseline: `main` at `e0fb6a1`. Line numbers refer to that commit. Status is "Fixed" when this PR changes it.

Method: read every `spec.md`, `plan.md`, and `tasks.md`; compared task status against `DEPLOY_NOTES.md` /
`OPERATOR_NOTES.md` and the code; ran the 006–008 suites (`test_006_*`, `test_007_*`, `test_008_*`,
`test_clef_provider.py`, `test_jev_provider.py`: 149 passed, 1 skipped); ran `scripts/check_spec_dag.py`
(added here; the repo had no DAG tooling).

## High

| # | Finding | Location | Status |
| --- | --- | --- | --- |
| H1 | Features 007 and 008 have no `spec.md` or `plan.md`. The constitution's chain (journey → workflow → state → contract → acceptance → task) is unmet for both. | `specs/007-evaluation-staging-enablement/`, `specs/008-dual-path-f5-design-receipts/`; `.specify/memory/constitution.md:24-30` | Fixed: DRAFT spec and plan reconstructed from tasks and operator notes, every claim labeled OBSERVED or INFERRED. Operator must confirm. |
| H2 | Task status does not match code. Every task in 006–008 is `[ ]`, but the notes say the code is implemented and the suites pass. | `specs/006-cloudflare-edge-clef/tasks.md:55-89` vs `DEPLOY_NOTES.md:3`; `specs/007-*/tasks.md:24-53` vs `OPERATOR_NOTES.md:3`; `specs/008-*/tasks.md:24-49` vs `OPERATOR_NOTES.md:3` | Fixed: code done is `[x]`; operator actions stay `[ ]`. |
| H3 | DAG violation once status is honest: 006 T060 (code implemented) depends on T050 (Hyperdrive, DEFERRED). T070 and T080 depend on T060. | `specs/006-cloudflare-edge-clef/tasks.md:77-78, 82, 86`; `DEPLOY_NOTES.md:28-29` | Fixed: split into T060a (code, deps T010+T020) and T060b (operator, deps T050+T060a). Same code/operator split applied to 007 and 008, which have the same mixed shape. |
| H4 | Stray workflow from another product: deploys the `noema.guru` production Worker from this repo. | `.github/workflows/deploy-worker-pin-pr.yml:1-30` | Not fixed (out of scope). Recommend removing it in its own PR. |

## Medium

| # | Finding | Location | Status |
| --- | --- | --- | --- |
| M1 | Literal `\n` merges T060, T060a, and T060b into one task line. | `specs/005-decision-intelligence/tasks.md:24` | Fixed |
| M2 | Spec status headers are stale: 005 says "implementation not authorized"; 006 says "SPECIFIED". Both are implemented. | `specs/005-*/spec.md:3`, `specs/006-*/spec.md:3` | Fixed |
| M3 | 005 T061c, T061d, T062, and T070 duplicate 007 T010–T060 with no cross-reference, so the same work could be tracked twice. | `specs/005-*/tasks.md:29-32` | Fixed: cross-references added. |
| M4 | 001–004 `plan.md`, `data-model.md`, and `research.md` are one-line TODO stubs. Specs are DRAFT with 44–79 `[INFERRED]` claims each. | `specs/00{1..4}-*/plan.md:3`, `data-model.md:1`, `research.md:1` | Not fixed: blocked on each spec's own T001 (operator confirmation). |
| M5 | 005 and 006 have no user stories with Given/When/Then; they use "User outcomes" bullets. 006 FRs had no acceptance criteria in the spec. | `specs/005-*/spec.md:15-21`, `specs/006-*/spec.md:15-20, 22-43` | Partly fixed: FR → task → acceptance table in 006; 005 links `acceptance.md`. Stories not written (would invent behavior). |
| M6 | 006 does not trace the constitution chain: no journeys, workflows, contracts, security, or rollback sections. | `specs/006-*/` | Gap recorded in `plan.md` constitution check. |
| M7 | 006 FR-001 and T030 specify Cloudflare Pages; PR #55 ships on Workers and records T030 as PARTIAL. | `specs/006-*/spec.md:24-25`, `tasks.md:66` | Recorded as a risk and task note; needs an operator decision. |
| M8 | "Provider timeout/retry caps tested" is unchecked, but timeouts are tested. Retry caps were not verified. | `specs/005-*/acceptance.md:24`; `backend/tests/unit/test_jev_provider.py:66`, `test_clef_provider.py:272` | Not changed: reviewer to confirm retry caps before ticking. |

## Low

| # | Finding | Location | Status |
| --- | --- | --- | --- |
| L1 | Task ID style differs: 001–004 use `001-T001`; 005–008 and Spec Kit use bare `T001`. | `specs/00{1..4}-*/tasks.md:5-14` | Fixed: bare IDs. Cross-spec references use `NNN:T001`. |
| L2 | Tasks lack Spec Kit phase headers and `[P]` / `[USn]` markers (005–008); plans lack "Technical Context" and "Constitution Check". | `specs/005-*/plan.md`, `specs/006-*/plan.md` | Partly fixed: constitution checks in 006–008 plans. |
| L3 | Stale risk about the GitHub connector lacking Contents write. | `specs/006-*/plan.md:40` | Fixed |
| L4 | `.specify/` holds only `memory/constitution.md`; no `templates/` or `scripts/`, so `/speckit.*` commands cannot run as shipped. | `.specify/` | Info |
| L5 | 005 Spec Kit gap list still open (Workflows section, transitions table, research, checklists). | `specs/005-*/checklists-gap.md:3-6` | Not fixed; tracked on Project #8. |

## Constitution

Present at the Spec Kit path, version 1.0.0, ratified 2026-09-25. 005 follows it fully (journeys, workflows,
state machines, contracts, acceptance, security). 006–008 follow the authority boundary and fail-closed
rules in code but not the documentation chain (H1, M6).

## DAG

Convention, now documented in `specs/README.md`: `- depends_on: [T010, 005:T061]`; sub-tasks `a` = code,
`b` = operator. `just spec-dag` runs the checker in strict mode.

| Run | Result |
| --- | --- |
| `main` as-is | 1 error (M1), 20 warnings (L1, H1) |
| `main` with tasks ticked as the notes claim | `DONE-BEFORE-DEP 006:T060 is done but 006:T050 is open` |
| This branch | 93 tasks, 49 done, 0 errors, 0 warnings |

Spec graph: 006 → 005; 007 → 005, 006; 008 → 007. Acyclic, all targets exist.
Cross-spec task edges: 007 T010b → 005 T061b2; 008 T050b → 007 T060b.
