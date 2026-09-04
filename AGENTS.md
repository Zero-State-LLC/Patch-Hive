# Agent and contributor instructions

This file is the instruction source for humans and coding agents in this repository.
Harness adapters (`CLAUDE.md`) only point here.

## Identity

**PatchHive** (`Zero-State-LLC/Patch-Hive`) is a deterministic Eurorack **rig-intelligence** and **Patch Book** publishing product. It is not an audio engine and not a hardware controller.

## Intent

Non-trivial work starts with an intent draft copied from [`intent/_TEMPLATE.md`](intent/_TEMPLATE.md). See [`intent/README.md`](intent/README.md). Trivial docs, chore, and single-line fixes do not need an intent file.

## Commands

| Task | Command |
|---|---|
| Test | `just test` |
| Lint | `just lint` |
| Validate | `just validate` (`just lint` + `just test`) |
| Build (frontend) | `just build` |

Also documented: `just setup`. Backend-only: `cd backend && pytest tests --ignore=tests/acceptance -q`. Frontend-only: `cd frontend && npm test -- --run && npm run type-check`.

## Invariants

- No audio processing product work (`audio` is port/domain metadata only).
- No hardware control or MIDI/CV activation.
- Vision cannot self-confirm inventory. Image → evidence → user confirm → inventory.
- Prefer `NOT_COMPUTABLE` over invented hardware facts.
- Payments stay test-mode by default (`ALLOW_PRODUCTION_PAYMENTS=false`).
- Do not put secrets, tokens, or live credentials in the tree.
- Do not invent product behavior the spec does not name.
- Fail closed. Do not deploy to production without explicit authority.

## Docs entry

This repo has no `graft/`. Start at [`SYSTEM_CONTEXT.md`](SYSTEM_CONTEXT.md). Then [`CURRENT_STATE.md`](CURRENT_STATE.md), [`docs/CONTINUATION.md`](docs/CONTINUATION.md), and [`AI_CONTEXT.md`](AI_CONTEXT.md) as needed. Long agent rules stay in [`docs/engineering/AI_AGENT_GUIDE.md`](docs/engineering/AI_AGENT_GUIDE.md).

## Escalation

If CI, tests, or validators look wrong — missing coverage, silent skips, green-but-inert checks, or a suite that contradicts the spec:

1. Open a bounded defect issue labeled `bug`. Do not expand the current task to paper over it.
2. Do **not** patch tests, fixtures, or CI to force green.
3. Do **not** weaken an assertion to match a broken implementation.

A red honest check is better than a green lie.

## Team context

Org and partner status is not this repo. When a task needs cross-repo or partner state, load [Zero-State-LLC/agent-context](https://github.com/Zero-State-LLC/agent-context):

1. `HANDOFF.md`
2. `STATUS.md`
3. `DECISIONS.md` only if a prior choice affects this task

Clone: `gh repo clone Zero-State-LLC/agent-context ~/agent-context`. Pull `--ff-only` before trusting a local copy. Templates and the SDLC pack live in that repo's `templates/` and `templates/sdlc/`.

## Skills

Name only skills that already exist. Do not invent skills or bots.

This repo has no `spec.md` `## Workflows`. Team-pack defaults when that section is empty: `anti-slop-code`, `production-systems`, `google-developer-style`.

In-tree specialist: `codebase-memory` ([`.agents/skills/codebase-memory/`](.agents/skills/codebase-memory/)).
