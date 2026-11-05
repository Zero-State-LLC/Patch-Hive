# Intent

## Problem

`docs/EXTERNAL_SOURCE_POLICY.md` says an unknown access basis blocks bulk publication, and `GET /api/modules/catalog` serves every live row to anyone, including the 376 rows tagged `access_basis = unknown`. Owner decision 39 (`docs/evidence/OWNER_DECISIONS_2026-11-04.md`, in #278) is to leave those rows out of anonymous reads, after checking how many rows that removes from the Modules page. If it guts browsing, it goes back to the owner.

## Proposed outcome

Anonymous reads leave out `unknown` rows on every route that returns them. Anyone signed in reads every live row. A module already placed keeps rendering on its rack. No catalog data changes.

Out of scope: rows with a NULL `access_basis`, which the decision does not name; tagging or promoting any row; whether the catalog route counts as bulk publication, which is for counsel.

## Affected users / systems

- Anonymous visitors see about 10% fewer rows on the Modules page and on Products. Three brands whose only rows are `unknown` leave the anonymous brand list: Acid Rain Technology, Cwejman and Dreadbox.
- Signed-in people see what they see today. A stale token on these routes is now a 401, so the web client renews it and retries. Before, these routes ignored the token.
- API clients that read `/api/modules/` anonymously get fewer rows, and a bad token is now refused.

## Constraints / non-goals

Fail closed: registry services leave these rows out unless the caller asks. `modules` has no access basis of its own, so a `modules` row takes the basis of the catalog row with the same brand and name. A rack reads its placed modules directly, so nothing placed is hidden. No migration.

## Open questions

Owner:

- 912 production rows (731 in a load from the committed inputs) have a NULL basis and stay visible. 179 of them are `CatalogCandidate` rows with a `modulargrid_url`. Should those be tagged `unknown` under FR-033? Should NULL count as unknown? Counting every NULL would remove 34.5% in production and 30.8% from the committed inputs, over the 25% stop line.
- Nothing moves a lead out of `unknown` when a maker page confirms it (FR-034 is Partial), so rows with a maker-verified `modules` twin stay hidden from anonymous readers until that is built.

Counsel: the full bulk-publication question (decision 39).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Production serves 3,736 live rows: 2,448 `official_publication`, 912 NULL, 376 `unknown`. Anonymous readers would keep 3,360, and 10.1% go | `OBSERVED` | Public `GET /api/modules/catalog`, paged twice and merged by id on 2026-11-04 |
| A load of the committed inputs gives 3,599 live rows: 2,492 `official_publication`, 731 NULL, 376 `unknown`. Anonymous readers keep 3,223, and 10.4% go | `OBSERVED` | `import_catalog_population.py --apply` on a throwaway Postgres, counted by SQL |
| #254 moves no row out of `unknown` | `OBSERVED` | Loading main plus #254's diff gives the same `plan_hash` and `inputs_hash` and the same counts; `population.py` never reads `permission_basis` and never updates `access_basis` on an existing row |
| Production's anonymous `GET /api/modules/` serves 347 `modules` rows sharing brand and name with an `unknown` catalog row | `OBSERVED` | Public responses joined by brand and name |
| The API answers carry no shared-cache headers, so a signed-in answer does not reach anonymous readers | `INFERRED` | No `cache-control` or `cf-cache-status` on the public response; `edge/api/src/index.ts` has no cache |
| The registry snapshot fallback holds no rows in production | `INFERRED` | `backend/registry/services.py` says it is not shipped; `Dockerfile.backend` copies only `backend/` |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-04
