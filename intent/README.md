# Intent files

Non-trivial work starts here. Copy [`_TEMPLATE.md`](_TEMPLATE.md) to a dated, scoped file (for example `intent/2026-09-04-short-slug.md`) and fill every section before writing a spec, plan, or code.

Do not invent a parallel process. After the intent is written, continue with the flow this repo already uses:

1. `intent.md` — problem, proposed outcome, constraints, verified vs assumed
2. Existing engineering docs — [`SYSTEM_CONTEXT.md`](../SYSTEM_CONTEXT.md), [`CURRENT_STATE.md`](../CURRENT_STATE.md), [`docs/CONTINUATION.md`](../docs/CONTINUATION.md), [`docs/engineering/AI_AGENT_GUIDE.md`](../docs/engineering/AI_AGENT_GUIDE.md) (and [`AI_CONTEXT.md`](../AI_CONTEXT.md) when retrieval is needed)
3. Implementation within already-named systems
4. PR with honest `OBSERVED` / `INFERRED` / `NOT_COMPUTABLE` evidence

Trivial docs, chore, and single-line fixes do not need an intent file.
`_TEMPLATE.md` is the blank form; do not fill it in place.

An intent is not a spec, not a plan, and not implementation authority. It does not authorize production deploy, extra bots, or product expansion.
