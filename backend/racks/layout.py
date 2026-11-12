"""A Rig's rows, with or without a Case (spec 009)."""

from __future__ import annotations

from typing import Any, Iterable

from sqlalchemy.orm import Session

from modules.models import Module

from .models import RackModule


def row_widths(case: Any | None, placements: Iterable[tuple[int, int, int]]) -> list[int]:
    """HP per row. With a Case, the Case's rows. With none, each row is as wide as its
    Modules reach, and the rows run to the last one that holds a Module.

    ``placements`` are ``(row_index, start_hp, hp)``.
    """
    if case is not None:
        return [int(hp) for hp in case.hp_per_row]
    reach: dict[int, int] = {}
    for row_index, start_hp, hp in placements:
        reach[row_index] = max(reach.get(row_index, 0), start_hp + hp)
    return [reach.get(row, 0) for row in range(max(reach) + 1)] if reach else []


def placed_spans(
    rack_modules: Iterable[RackModule], modules: dict[int, Module]
) -> list[tuple[int, int, int]]:
    """``(row_index, start_hp, hp)`` for each placement whose Module is known."""
    return [
        (int(rm.row_index), int(rm.start_hp), int(modules[rm.module_id].hp))
        for rm in rack_modules
        if rm.module_id in modules
    ]


def rack_row_widths(db: Session, case: Any | None, rack_modules: list[RackModule]) -> list[int]:
    """``row_widths`` for stored placements, loading their Modules only when there is no Case."""
    if case is not None:
        return row_widths(case, [])
    ids = {rm.module_id for rm in rack_modules}
    modules = {m.id: m for m in db.query(Module).filter(Module.id.in_(ids)).all()} if ids else {}
    return row_widths(None, placed_spans(rack_modules, modules))
