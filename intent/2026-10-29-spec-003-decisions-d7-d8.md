# Intent

## Problem

Three catalog decisions were open: a paid Frap pass (R3), rebuilding the crawl cache (R4) and jumper-dependent power (R5). Several spec 003 open questions are now answerable from the repo.

## Proposed outcome

- **D7:** Frap stays excluded. Its host accepts no TCP connection from the crawl network (observed 2026-10-29); a paid renderer would route around that. T026 closes.
- **D8:** `power_configs` is the chosen schema (one +12/−12/+5 set per jumper setting, each with its source). It's not built until T035 reads the settings from about 45 maker pages under an approved cap; T034 then builds it.
- Open questions closed: access basis, Thomann, file conventions, case pipeline, brand count. Fetch cost is partly resolved, with observed numbers.
- The decisions note's §6 is updated.

## Affected users / systems

Spec 003 docs only.

## Constraints / non-goals

No paid fetch is run. T035 waits on a cap.

## Open questions

The cap for T035 (estimated 20–50 context.dev credits).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| frap.tools refuses TCP 80/443 from here | `OBSERVED` | curl and nc, 2026-10-29 |
| 45 live modules in scope for T035 | `OBSERVED` | read-only prod query |
| 20–50 credits | `INFERRED` | the v2 crawl's credits per call |

## Author / date

- Author: Daniel Meyer (with Claude)
- Date: 2026-10-29
