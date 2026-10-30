# Intent

## Problem

After #164, 88 `module_catalog` rows still carry `hp_source = legacy_unsourced`: their HP is an uncited value from `overlays/module-catalog-hp-v1.json`. Spec 003 T039 asks for a free maker-page lookup of them. #164 left 52 citations unconfirmed (ADDAC and Befaco blocked, Instruō timed out, seven pages naming another product or version or contradicting themselves), and never looked up the retailer-cited or uncited ones.

## Proposed outcome

- `overlays/module-catalog-hp-v4.json` (the v3 schema) re-sources each marked value that a maker page confirms. The page must name that exact product and state its width, and each entry quotes it. Where the page states another width, v4 carries the page value, so a fresh load gets it right.
- `provenance/maker-corrections-v4.json` holds guarded `correct` entries for every table that holds a value the maker page shows is wrong. The loader reads it after `maker-corrections-v3` (`PROVENANCE_MANIFESTS`).
- The existing `_schedule_hp_source_markers` clears the marker on each re-sourced row. No loader logic changes.
- T039's note gets the new counts. T039 stays open while ADDAC System and Befaco remain.
- Out of scope: ADDAC System and Befaco (their sites answered with a bot challenge and a CAPTCHA; nothing routes around a block), removing `UNSOURCED_HP_OVERLAYS`, and any HP outside the FR-007 band.

## Affected users / systems

`module_catalog` on staging and prod (two HP values, 26 markers cleared), the catalog loader's data files, and the catalog API's `hp_source` field. `modules` holds no row for either corrected module.

## Constraints / non-goals

Values come only from the maker's own pages. Plain free GETs only, with robots.txt read and honoured per host, 2 s apart per host, a host stopped at its first block, CAPTCHA or challenge. No paid APIs and no third-party catalogue sites. Corrections fire only while the stored value is the reviewed old value. HP stays fill-null. Dry run, then apply with the reviewed `plan_hash`.

## Open questions

- Doepfer A-155: doepfer.de states 50 HP, and the stored v1 value is 4. FR-007 and FR-038 keep HP in the 1 to 42 band, so no manifest may write 50. The owner decides whether the band should admit wider modules. Until then the row stays marked.
- The six Instruō pages could not be fetched: the TLS handshake to www.instruomodular.com timed out (60 s), and a 90 s retry ended with an SSL EOF on robots.txt. Without a readable robots.txt, no page was requested.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Each v4 entry's page names that product and states its width (quote in the entry) | `OBSERVED` | plain GET 2026-10-30; the build script checked each quote against the saved page text |
| Doepfer pages state A-106-1 14 HP and A-138m 20 HP; v1 says 8 for both | `OBSERVED` | https://doepfer.de/A106.htm, https://doepfer.de/A138m.htm |
| A staging-like replay marks 88 rows, and the branch apply corrects 2 values, clears 26 markers, leaves 62, and changes nothing else | `OBSERVED` | replica replay 4d5bfe9, then 2e3c90d, then this branch, Postgres 15.13, slug:hp digests |
| Staging and prod hold the same values as the replay | `INFERRED` | check with the staging dry run |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-30
