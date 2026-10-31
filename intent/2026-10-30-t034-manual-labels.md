# Intent

## Problem

The T035 receipt left Dave Jones Otool's two jumper settings unlabelled because its product page separates them only with "-or-". T034 therefore loaded nothing for Otool, and its rail draws stay unknown in rack budgets.

## Proposed outcome

A small receipt, `data/synth-catalog/receipts/t034-manual-labels.json`, supplies a label for an unlabelled setting only when the maker's own manual, linked from the product page, names that jumper position next to the same draws. The loader applies it and stores the manual quote with the setting. Otool gains its two settings. Out of scope: the SMR base setting and the VCA Matrix "80 max" (owner decisions), A-155 width, evidence expiry scheduling.

## Affected users / systems

Catalog loader (`population.py`), `power_configs` rows, rack power budgets.

## Constraints / non-goals

No inferred labels or units; fill-only and idempotent; free GETs with robots.txt respected.

## Open questions

SMR and VCA Matrix (owner), see docs/evidence/OPEN_DECISIONS_2026-10-30_RESEARCH.md §5.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The Otool Plus manual names "Internal 5v" with 80/22 mA and "External 5v" with 12/70/22 mA | `OBSERVED` | jonesvideo.com/otool/Otool_Plus_UserManual.pdf p.1, sha256 7299592c… |
| The draws match the product page's two alternatives exactly | `OBSERVED` | receipts/t035-jumper-power.json |
| The loader then plans 19 settings for 11 modules | `OBSERVED` | test_jumper_settings_load_once_as_power_configs on Postgres 15 |

## Author / date

- Author: Claude (for Daniel Meyer)
- Date: 2026-10-30
