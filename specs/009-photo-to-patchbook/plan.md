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
