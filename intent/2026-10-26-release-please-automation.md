# Intent

## Problem

Versions, changelog entries, and tags are maintained by hand. `CHANGELOG.md` still called `0.3.0-alpha.2` "Proposed (untagged)" ten days after the tag was pushed, and three `feat` merges (specs 006–008) since that tag have no changelog entry or version bump. `backend/pyproject.toml` and `frontend/package.json` must be bumped together by hand, and nothing checks that PR titles (which become squash commits on `main`) carry a type.

## Proposed outcome

- release-please keeps one release PR open on `main`. That PR bumps `frontend/package.json` and `backend/pyproject.toml` together, updates `.release-please-manifest.json`, and writes `CHANGELOG.md` from Conventional Commit titles.
- Merging the release PR, and only that, tags `vX.Y.Z[-alpha.N]` and creates the GitHub release (prerelease for `-alpha`/`-beta`/`-rc`).
- A PR-title check requires Conventional Commits, including the repo's own types (`spec`, `data`, `ops`, `infra`, `release`, `sync`, `deps`).
- `scripts/check_version_consistency.py` accepts both PEP 440 spellings release-please may write.
- Board automation (`project-collaboration.yml`) targets the renamed `Backlog` status.

Out of scope: deploys of any kind, publishing packages to registries, signing tags, changing the SemVer policy in `docs/VERSIONING.md`, and choosing the next version line (`0.3.0-alpha.3` vs `0.4.0-alpha.1` is an operator call via `Release-As:`).

## Affected users / systems

CI (`.github/workflows/release-please.yml`, `pr-title.yml`, `release.yml`, `project-collaboration.yml`), release tags and GitHub releases, `CHANGELOG.md`, the two version files, and every contributor's PR titles. Canon, evidence/vision, inventory, patch generation, and payment flags are not touched.

## Constraints / non-goals

- No deploy, no production authority: nothing in these workflows builds, ships, or changes runtime config. A release tag is descriptive evidence, not production readiness (`docs/VERSIONING.md`).
- Tags and releases happen only when a human merges the release PR; no workflow pushes to `main` directly.
- Payments stay test-mode; no secrets beyond the default `GITHUB_TOKEN`.
- Existing tags and history are not rewritten. Manual tagging through `release.yml` keeps working.
- Fail closed: `release.yml` still blocks a PR whose two version files disagree.

## Open questions

- Next version line: `0.3.0-alpha.3` (release-please default) or `0.4.0-alpha.1` (board plan). Operator decides.
- Org setting "Allow GitHub Actions to create and approve pull requests" must be enabled. Org admin decides.
- Release PRs opened with `GITHUB_TOKEN` do not trigger other workflows; required checks on them need a re-run or an App/PAT token. Operator decides which.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Tags `v0.3.0-alpha.1` and `v0.3.0-alpha.2` exist; alpha.2 commit dated 2026-10-16 | `OBSERVED` | `git ls-remote --tags`, `git log v0.3.0-alpha.2` |
| Repo squash-merges with PR title as the commit subject | `OBSERVED` | repo settings `squash_merge_commit_title=COMMIT_OR_PR_TITLE` |
| Version check passes on both spellings (`0.3.0a2`, `0.3.0-alpha.3`, `0.4.0rc1`, `1.0.0b2`) | `OBSERVED` | local run of `scripts/check_version_consistency.py` converter |
| release-please writes `0.3.0-alpha.N` into `pyproject.toml` via the toml jsonpath updater | `INFERRED` | release-please `extra-files` docs; not yet run on this repo |
| First release PR proposes `0.3.0-alpha.3` | `INFERRED` | release-please prerelease versioning strategy; not yet run |
| release-please opens its PR once merged | `NOT_COMPUTABLE` | depends on org Actions billing and the org PR-creation setting |

## Author / date

- Author: Claude (Claude Code session), for Daniel Meyer
- Date: 2026-10-26
