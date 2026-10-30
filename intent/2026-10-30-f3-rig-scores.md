# Intent

## Problem

Spec 001 OQ-11: the six rig scores had no formulas, so all were `NOT_COMPUTABLE`. `canon/runes.py` `map_metrics` also averaged ports per module and treated a module with no ports as zero.

## Proposed outcome

Owner decision 11, option 2 (2026-10-30). `routing_flex_score = round(1 - exp(-(total_ports / module_count) / 8), 4)` and `performance_density_index = round(total_ports / total_hp, 4)`, both in `canon/rig_scores.py`. Either is `NOT_COMPUTABLE` if any module has missing or empty `io_ports`; the density index also if any HP is null or 0. Metrics version `canon-metrics.1.2.0`; formula and covered fraction go in `confidence_notes`. The other four scores stay `NOT_COMPUTABLE`. `map_metrics` uses the same function.

## Affected users / systems

- `canon/rig_metrics.py`, `canon/runes.py`, spec 001 tasks and spec. No schema change; frontend `MetricScore` already allows `NOT_COMPUTABLE`.

## Constraints / non-goals

Never substitute zero. No port-data pass. No blank-panel exemption.

## Open questions

None.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The module row has no reliable blank-panel marker | `OBSERVED` | `category_raw` exists only in seed JSON; "Blank Panel / Multiple" includes real modules (Bastl Wackel Kontakt) |
| Packets sealed before keep their hash | `OBSERVED` | `test_rig_metrics_packet_sealed_before_fr027_keeps_its_hash` passes |
| Full backend suite passes | `OBSERVED` | 1295 passed, 10 skipped on Postgres 15.13 |
