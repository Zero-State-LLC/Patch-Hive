# Intent

## Problem

1. `/health` and `/health/ready` report `"version": "0.1.0"` although the release is `0.3.0-alpha.4`. The value is a hardcoded default in `backend/core/config.py` that Release Please never bumps.
2. `expire_image_assets` (`backend/evidence/retention.py`) has no non-test caller, so evidence images are never cleaned up after retention (OQ-10 note in `docs/evidence/OPEN_DECISIONS_2026-10-30_RESEARCH.md`).

## Proposed outcome

- The API version is read from `backend/pyproject.toml` (`project.version`), which Release Please already bumps, through `backend/core/version.py`. The Docker image copies the backend directory to `/app` (`COPY . .`, `pyproject.toml` not in `.dockerignore`), so the file is present at runtime; the package is not pip-installed there, so `importlib.metadata` would not work. Response shape is unchanged. `scripts/check_version_consistency.py` also fails if `config.py` goes back to a literal.
- An operator CLI, `python -m evidence.expire`, runs the existing expiry. It is a dry run by default and acts only with `--apply`. `expire_image_assets` gains a side-effect-free `dry_run` mode. `docs/OPERATIONS.md` documents it.

Out of scope: any automatic schedule (Cloudflare cron or GitHub scheduled workflow), an admin HTTP endpoint, changing retention periods, deleting anything beyond what `expire_image_assets` already handles, and deploys.

## Affected users / systems

Backend health endpoints, `core.config`, the version-consistency check, evidence retention, ops docs. No canon, payment, vision, or inventory behavior changes.

## Constraints / non-goals

- Expiry touches only `image_assets` (a mutable table: `deleted_at`) and its stored bytes. Append-only tables are not written. Bytes shared with a live asset are kept.
- No scheduling is added. Whether and how to run it automatically is an owner decision.
- Fail closed: an unreadable pyproject yields `"unknown"`, not a made-up version.

## Open questions

- Owner: schedule expiry automatically (Cloudflare cron or GitHub scheduled workflow)? Not decided here.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `0.1.0` came from `Settings.app_version` default | `OBSERVED` | `backend/core/config.py` |
| Release Please bumps `backend/pyproject.toml` `$.project.version` | `OBSERVED` | `release-please-config.json` |
| Image copies `pyproject.toml` to `/app` | `OBSERVED` | `backend/Dockerfile`, `backend/.dockerignore` |
| `expire_image_assets` has no non-test caller | `OBSERVED` | grep of `backend/` |
| Expiry writes only `image_assets.deleted_at` and deletes storage objects | `OBSERVED` | `backend/evidence/retention.py` |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-10-30
