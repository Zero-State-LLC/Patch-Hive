"""The two defined rig scores (spec 001 OQ-11, decision 11 option 2, owner 2026-10-30).

``routing_flex_score`` and ``performance_density_index`` are computed from declared
``io_ports`` and module widths. A module with missing or empty ``io_ports`` makes both scores
``NOT_COMPUTABLE``; zero is never substituted. The catalog has no reliable blank/passive panel
marker on the module row (``category_raw`` is seed-only and "Blank Panel / Multiple" also
covers real modules), so nothing is exempted.
"""

from __future__ import annotations

import math
from typing import Sequence

from canon.contracts import NOT_COMPUTABLE, MetricScore

METRICS_GENERATOR_VERSION = "canon-metrics.1.2.0"
ROUTING_FLEX_K = 8

ROUTING_FLEX_FORMULA = (
    f"routing_flex_score = round(1 - exp(-(total_ports / module_count) / {ROUTING_FLEX_K}), 4)"
)
DENSITY_FORMULA = (
    "performance_density_index = round(total_ports / total_hp, 4), ports per HP; "
    "controls (knobs, switches) are not stored, so port-only"
)


def compute_rig_scores(
    port_counts: Sequence[int | None], widths: Sequence[int | None]
) -> tuple[MetricScore, MetricScore, tuple[str, ...]]:
    """Return ``(routing_flex_score, performance_density_index, confidence_notes)``.

    ``port_counts`` holds one entry per placed module: its number of declared ports, or
    ``None`` when ``io_ports`` is missing. 0 counts as empty. ``widths`` holds one HP per
    module, ``None`` when unknown.
    """
    module_count = len(port_counts)
    with_ports = sum(1 for n in port_counts if n)
    notes = [
        f"Formulas: {ROUTING_FLEX_FORMULA}; {DENSITY_FORMULA}.",
        f"Port coverage: {with_ports}/{module_count} modules declare io_ports.",
        "The other four scores stay NOT_COMPUTABLE (OQ-11 option 2).",
    ]
    if module_count == 0 or with_ports != module_count:
        notes.append(
            "routing_flex_score and performance_density_index are NOT_COMPUTABLE: "
            "a module has missing or empty io_ports (no blank-panel exemption: the catalog "
            "has no reliable marker)."
        )
        return NOT_COMPUTABLE, NOT_COMPUTABLE, tuple(notes)
    total_ports = sum(n for n in port_counts if n)
    flex = round(1 - math.exp(-(total_ports / module_count) / ROUTING_FLEX_K), 4)
    if any(w is None or w <= 0 for w in widths):
        notes.append("performance_density_index is NOT_COMPUTABLE: a module HP is null or 0.")
        return flex, NOT_COMPUTABLE, tuple(notes)
    return flex, round(total_ports / sum(w for w in widths if w), 4), tuple(notes)
