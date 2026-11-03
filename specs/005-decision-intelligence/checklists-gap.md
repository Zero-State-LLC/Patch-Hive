# Spec 005: Spec Kit gaps (audit 2026-10-16)

- [x] spec.md has no **Workflows** section that names the governing skills, owners, and CI file. The existing `workflows.md` holds domain flows (WF-001 and onward), not process workflows. Closed 2026-11-03: spec.md "Workflows" names the skills, owners and CI files; `workflows.md` keeps the domain flows.
- [x] `state-machines.md` has states and forbidden transitions, but no transitions table (`from | event | guard | to | effect`), no explicit initial or final states, and no mermaid diagram. Closed 2026-11-03: the table, the initial, terminal and final states and the diagram come from `backend/intelligence/resolution_machine.py`; the narrative states with no implementation are marked as drift.
- [x] `research.md` and `checklists/` are missing. Closed 2026-11-03: `research.md` has existed since 2026-10-29 (#134), and `checklists/requirements.md` is added.
- [ ] Open tasks: T061, T062, T070.
