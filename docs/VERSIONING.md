# PatchHive versioning and release policy

## Purpose

PatchHive uses explicit versioning to separate source compatibility, artifact compatibility, release maturity, and deployment authority. A version label is descriptive evidence; it is never proof that a build is production ready.

## Semantic versioning

Repository releases follow `MAJOR.MINOR.PATCH`.

- **MAJOR** — incompatible public API, persisted-data, canonical contract, or artifact-format change.
- **MINOR** — backward-compatible product capability, compiler behavior, export format, or user workflow.
- **PATCH** — backward-compatible correction, hardening, documentation repair, or operational improvement.

Pre-release identifiers follow SemVer:

- `-alpha.N` — incomplete vertical slices; schema and behavior may change.
- `-beta.N` — feature-complete for the declared scope; defects and UX changes remain expected.
- `-rc.N` — release candidate; scope frozen except release-blocking fixes.

Build metadata may record provenance, for example `0.3.0-rc.1+sha.a842373`.

## Versioned surfaces

The following surfaces MUST carry independent schema or format versions when applicable:

- REST API
- canonical domain contracts
- database migrations
- `PatchGraph`
- `PatchPlan`
- `PatchPageSpec`
- `PageFitReport`
- `PatchBookManifest`
- export bundle and license manifest
- generator and renderer implementations

Application version and artifact version are related but not interchangeable. A patch release may regenerate an artifact only when the applicable artifact contract and determinism rules permit it.

## Compatibility policy

- Existing immutable runs and exports are never rewritten in place.
- A new generator or renderer version creates a new artifact identity.
- Older artifact readers remain supported for at least the current minor release unless a documented security or correctness issue requires withdrawal.
- Database migrations are forward-only in production; rollback means application rollback plus a tested compensating migration or restored backup.
- Removal of an externally used field requires deprecation in at least one minor release unless the field creates a security or integrity risk.

## Release branches and tags

- Development occurs through short-lived branches and pull requests.
- `main` is the integration branch and must remain releasable or explicitly marked non-releasable.
- Release tags are immutable and signed when signing infrastructure is available.
- Tag format: `vMAJOR.MINOR.PATCH[-prerelease]`.
- A release tag must point to the exact commit covered by the release receipt.

## Release automation

- PR titles follow [Conventional Commits](https://www.conventionalcommits.org/); `.github/workflows/pr-title.yml` checks them. Squash merges make the PR title the commit on `main`. Allowed types: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `style`, `revert`, plus repo types `spec`, `data`, `ops`, `infra`, `release`, `sync`, `deps`.
- `feat` bumps MINOR (pre-1.0 and prerelease rules below), `fix`/`perf` bump PATCH, `!` or `BREAKING CHANGE:` bumps MAJOR. Repo types appear in the changelog but do not bump.
- `.github/workflows/release-please.yml` keeps one open release PR on `main`. It updates `CHANGELOG.md`, `.release-please-manifest.json`, `frontend/package.json`, and `backend/pyproject.toml`. Merging it tags `vX.Y.Z[-alpha.N]` and creates the GitHub release.
- While on the alpha line, release-please increments the prerelease number (`-alpha.N`). To move to a new line, add a `Release-As: 0.4.0-alpha.1` footer to a commit, or edit the manifest in a PR.
- `scripts/check_version_consistency.py` (run by `release.yml` on every PR) accepts both PEP 440 spellings in `pyproject.toml`.
- Manual tags still work: pushing `v*.*.*` runs `release.yml`, which checks versions and creates the release.

## Retroactive baseline

Historical work predates this policy. Do not invent version history or imply releases that were never tagged.

The existing canon-aligned MVP is classified retroactively as the **0.x development line**:

- pre-canon and historical implementation: `0.1.x` lineage, descriptive only
- canon-aligned MVP and credits/export integration: `0.2.x` lineage
- one-page Patch Book Generator implementation: planned `0.3.x` lineage
- first production-supported public release: `1.0.0`, only after all production-readiness gates pass

Existing commits and PRs retain their original identities. Retroactive lineage is a documentation classification, not a replacement tag history.

## Release-candidate rules

A release candidate may be cut only when:

1. declared scope is feature complete;
2. migrations and contracts are frozen except blocker fixes;
3. all required automated suites pass on the candidate SHA;
4. deterministic replay and artifact hashes are recorded;
5. security, accessibility, backup/restore, and operational gates have evidence;
6. known issues are documented and classified;
7. production payment and deployment authority remain explicit.

Any release-blocking code change after `rc.N` produces `rc.N+1` and a new evidence receipt. RCs are never silently retagged.

## Release receipt

Every candidate and final release must publish a machine-readable and human-readable receipt containing:

- version and tag
- source SHA
- build timestamp and toolchain identity
- dependency lock hashes
- migration head
- contract and artifact schema versions
- generator and renderer versions
- test suites, counts, duration, and failures
- security and accessibility results
- deterministic golden hashes
- SBOM and provenance artifact references
- known risks and waivers
- deployment target and authority decision

Insufficient evidence is `NOT_COMPUTABLE`, not PASS.
