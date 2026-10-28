# Intent

## Problem

The Products page (`/products`) is empty in production and staging. Search returns `{"results": []}` and every manufacturer shows 0 models:
- `device_models` has no rows, so the database paths count nothing.
- `/api/registry/search` reads only `data/registry_snapshots/registry_latest.json`, which the API image (built from `backend/`) does not contain.

The loaded modules are in `module_catalog` (4,172 rows), and 4,130 of them match a registry manufacturer by brand name.

## Proposed outcome

- With a database session, a manufacturer's models are its `device_models` plus its `module_catalog` rows. A row belongs to a manufacturer when its brand matches the canonical name or an alias (case-insensitive), or its `registry_manufacturer_slug` matches.
- `/api/registry/search` takes the session: registry models first, then catalog rows, with LIKE wildcards escaped.
- Manufacturer list counts, detail `model_count` and coverage include catalog rows. The list total is one `COUNT`, not a full list build.
- The snapshot path stays for callers without a session.

Out of scope: populating `device_models`; the seed script decision; filling `registry_manufacturer_slug`.

## Affected users / systems

- `backend/registry/services.py`, `routes.py`; the Products page.

## Constraints / non-goals

Read-only. No writes, no migration, no change to the catalog or the snapshot.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Prod search returns nothing and makers show 0 models | `OBSERVED` | `api.patch-hive.com/api/registry/search?q=maths`, `/manufacturers/make-noise` |
| 4,130 of 4,172 catalog rows match a manufacturer by name; 0 have a registry slug | `OBSERVED` | read-only query on the prod Neon branch |
| Backend suite passes | `OBSERVED` | local run, 970 passed |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-28
