"""
Rack validation — HP fit, format gate, power budget (fail-closed, no invent).
"""

from __future__ import annotations

from typing import List, Tuple

from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from cases.models import Case
from modules.catalog import ModuleCatalog
from modules.models import Module

from .schemas import RackModuleSpec, RackValidationError

# Module column, case column, label for each rail.
RAILS = (
    ("power_12v_ma", "power_12v_ma", "+12V"),
    ("power_neg12v_ma", "power_neg12v_ma", "-12V"),
    ("power_5v_ma", "power_5v_ma", "+5V"),
)
UNKNOWN_NAMES_SHOWN = 10


ALTERNATIVES_SHOWN = 3


def tombstone_note(db: Session, module: Module) -> dict | None:
    """Why a placed module is tombstoned, and live modules with the same name.

    None for a live module. The reason comes from its catalog row (the loader's
    retirement manifest); alternatives are same-named modules under other brands that
    are not tombstoned (for a misattributed row, the real maker's module).
    """
    if module.status != "tombstoned":
        return None
    catalog = (
        db.query(ModuleCatalog.tombstone_reason)
        .filter(ModuleCatalog.brand == module.brand, ModuleCatalog.name == module.name)
        .first()
    )
    alternatives = (
        db.query(Module)
        .filter(
            func.lower(Module.name) == module.name.lower(),
            Module.brand != module.brand,
            Module.status.is_distinct_from("tombstoned"),
        )
        .order_by(Module.brand, Module.id)
        .limit(ALTERNATIVES_SHOWN)
        .all()
    )
    return {
        "reason": (catalog.tombstone_reason if catalog else None) or "retired from the catalog",
        "alternatives": [{"id": m.id, "brand": m.brand, "name": m.name} for m in alternatives],
    }


def tombstone_warning(index: int, module: Module, note: dict) -> RackValidationError:
    names = ", ".join(f"{a['brand']} {a['name']}" for a in note["alternatives"])
    return RackValidationError(
        field=f"modules[{index}].module_id",
        message=(
            f"{module.brand} {module.name} is retired from the catalog ({note['reason']})"
            + (f"; consider {names}" if names else "")
        ),
        details={
            "code": "MODULE_TOMBSTONED",
            "module_id": module.id,
            "module_name": module.name,
            "brand": module.brand,
            "reason": note["reason"],
            "alternatives": note["alternatives"],
        },
    )


def hp_needs_reverify(db: Session, module: Module) -> bool:
    """True when the module's HP is a ModularGrid-derived value awaiting a maker-page check.

    The 2026-10-17 remediation could not null ``modules.hp`` (NOT NULL), so it archived the
    value and flagged the row. Placement must refuse such a module (spec 003 FR-035). A row
    flagged only for other fields (for example nulled power) keeps a placeable, confirmed HP.
    """
    if not module.needs_reverify:
        return False
    bind = db.get_bind()
    if not inspect(bind).has_table("catalog_value_archive"):
        return False
    # A reviewed correction from a maker page (spec 003 FR-038) settles the flagged HP.
    row = db.execute(
        text(
            "SELECT 1 FROM catalog_value_archive f WHERE f.table_name = 'modules' "
            "AND f.row_key = :key AND f.field = 'hp' AND f.action = 'flag' "
            "AND NOT EXISTS (SELECT 1 FROM catalog_value_archive c WHERE c.table_name = 'modules' "
            "AND c.row_key = :key AND c.field = 'hp' AND c.action = 'correct') LIMIT 1"
        ),
        {"key": f"{module.brand}::{module.name}"},
    ).first()
    return row is not None


def validate_rack_configuration(
    db: Session, case_id: int, modules: List[RackModuleSpec]
) -> Tuple[bool, List[RackValidationError], List[RackValidationError]]:
    """
    Validate a rack configuration against case constraints.

    Returns:
        (is_valid, hard_errors, soft_warnings)

    Power semantics (C2):
    - Rail is None → unspecified; never invent capacity; advisory if modules draw power.
    - Rail is int (including 0) → enforce exceed as hard error.
    - A module rail that is None is unknown, never 0 (spec 003 FR-022). A rail whose
      known draws fit but which has unknown draws is a ``POWER_RAIL_INCOMPLETE``
      warning: the budget is "at least X mA", not confirmed.
    - powered is False and modules draw power → hard error.
    - Non-Eurorack format with any module placement → hard error (MVP placement is Eurorack-only).
    """
    errors: List[RackValidationError] = []
    warnings: List[RackValidationError] = []

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        errors.append(
            RackValidationError(field="case_id", message=f"Case with id {case_id} not found")
        )
        return False, errors, warnings

    family = (case.format_family or "Eurorack").strip()
    if modules and family.lower() != "eurorack":
        errors.append(
            RackValidationError(
                field="case_id",
                message=(
                    f"Placement is Eurorack-only in MVP; case format is {family!r}. "
                    "Browse non-Eurorack cases in the catalog without attaching modules."
                ),
                details={
                    "code": "FORMAT_NOT_SUPPORTED_FOR_PLACEMENT",
                    "format_family": family,
                    "capacity_unit": case.capacity_unit,
                },
            )
        )

    # Track HP usage per row (Eurorack layout)
    try:
        hp_usage = {i: [False] * int(case.hp_per_row[i]) for i in range(case.rows)}
    except (TypeError, IndexError, ValueError):
        errors.append(
            RackValidationError(
                field="case_id",
                message="Case layout is invalid (hp_per_row / rows mismatch)",
                details={"code": "INVALID_CASE_LAYOUT"},
            )
        )
        return False, errors, warnings

    total_power_12v = 0
    total_power_neg12v = 0
    total_power_5v = 0
    unknown_draw: dict[str, list[str]] = {label: [] for _, _, label in RAILS}

    for idx, module_spec in enumerate(modules):
        module = db.query(Module).filter(Module.id == module_spec.module_id).first()
        if not module:
            errors.append(
                RackValidationError(
                    field=f"modules[{idx}].module_id",
                    message=f"Module with id {module_spec.module_id} not found",
                )
            )
            continue

        if hp_needs_reverify(db, module):
            errors.append(
                RackValidationError(
                    field=f"modules[{idx}].module_id",
                    message=(
                        f"Module {module.name} has an unverified HP; it cannot be placed until "
                        "a manufacturer page confirms its width"
                    ),
                    details={
                        "code": "MODULE_HP_NEEDS_REVERIFY",
                        "module_id": module.id,
                        "module_name": module.name,
                    },
                )
            )
            continue

        if module_spec.row_index >= case.rows:
            errors.append(
                RackValidationError(
                    field=f"modules[{idx}].row_index",
                    message=f"Row index {module_spec.row_index} exceeds case rows ({case.rows})",
                    details={"module_id": module.id, "module_name": module.name},
                )
            )
            continue

        row_hp = case.hp_per_row[module_spec.row_index]
        if module_spec.start_hp + module.hp > row_hp:
            errors.append(
                RackValidationError(
                    field=f"modules[{idx}].start_hp",
                    message=(
                        f"Module {module.name} ({module.hp}HP) at position "
                        f"{module_spec.start_hp} exceeds row capacity ({row_hp}HP)"
                    ),
                    details={
                        "module_id": module.id,
                        "module_name": module.name,
                        "module_hp": module.hp,
                        "start_hp": module_spec.start_hp,
                        "row_hp": row_hp,
                    },
                )
            )
            continue

        for hp in range(module_spec.start_hp, module_spec.start_hp + module.hp):
            if hp_usage[module_spec.row_index][hp]:
                errors.append(
                    RackValidationError(
                        field=f"modules[{idx}].start_hp",
                        message=f"Module {module.name} overlaps with another module at HP {hp}",
                        details={
                            "module_id": module.id,
                            "module_name": module.name,
                            "overlapping_hp": hp,
                        },
                    )
                )
                break
            hp_usage[module_spec.row_index][hp] = True

        if module.power_12v_ma:
            total_power_12v += module.power_12v_ma
        if module.power_neg12v_ma:
            total_power_neg12v += module.power_neg12v_ma
        if module.power_5v_ma:
            total_power_5v += module.power_5v_ma
        for module_field, _, label in RAILS:
            if getattr(module, module_field) is None:
                unknown_draw[label].append(module.name)

    any_draw = total_power_12v > 0 or total_power_neg12v > 0 or total_power_5v > 0
    any_unknown = any(unknown_draw.values())
    unknown_counts = {label: len(names) for label, names in unknown_draw.items()}
    rails_known = (
        case.power_12v_ma is not None
        or case.power_neg12v_ma is not None
        or case.power_5v_ma is not None
    )

    if case.powered is False and any_draw:
        errors.append(
            RackValidationError(
                field="power",
                message=(
                    "Case is marked unpowered but modules declare power draw. "
                    "Choose a powered case or remove powered modules."
                ),
                details={
                    "code": "POWER_ON_UNPOWERED_CASE",
                    "total_power_12v": total_power_12v,
                    "total_power_neg12v": total_power_neg12v,
                    "total_power_5v": total_power_5v,
                },
            )
        )

    if (any_draw or any_unknown) and not rails_known and case.powered is not False:
        warnings.append(
            RackValidationError(
                field="power",
                message=(
                    "Case rail capacities are unspecified; power budget was not enforced. "
                    "Missing power stays missing — not assumed."
                ),
                details={
                    "code": "POWER_UNSPECIFIED",
                    "total_power_12v": total_power_12v,
                    "total_power_neg12v": total_power_neg12v,
                    "total_power_5v": total_power_5v,
                    "unknown_draw_count": unknown_counts,
                },
            )
        )

    # Enforce known rails only (null is not zero).
    if case.power_12v_ma is not None and total_power_12v > case.power_12v_ma:
        errors.append(
            RackValidationError(
                field="power",
                message=(
                    f"+12V power draw ({total_power_12v}mA) exceeds case capacity "
                    f"({case.power_12v_ma}mA)"
                ),
                details={
                    "code": "POWER_EXCEEDED_12V",
                    "total_power_12v": total_power_12v,
                    "case_power_12v": case.power_12v_ma,
                },
            )
        )

    if case.power_neg12v_ma is not None and total_power_neg12v > case.power_neg12v_ma:
        errors.append(
            RackValidationError(
                field="power",
                message=(
                    f"-12V power draw ({total_power_neg12v}mA) exceeds case capacity "
                    f"({case.power_neg12v_ma}mA)"
                ),
                details={
                    "code": "POWER_EXCEEDED_NEG12V",
                    "total_power_neg12v": total_power_neg12v,
                    "case_power_neg12v": case.power_neg12v_ma,
                },
            )
        )

    if case.power_5v_ma is not None and total_power_5v > case.power_5v_ma:
        errors.append(
            RackValidationError(
                field="power",
                message=(
                    f"+5V power draw ({total_power_5v}mA) exceeds case capacity "
                    f"({case.power_5v_ma}mA)"
                ),
                details={
                    "code": "POWER_EXCEEDED_5V",
                    "total_power_5v": total_power_5v,
                    "case_power_5v": case.power_5v_ma,
                },
            )
        )

    # Known draws fit (or the rail was already flagged above); unknown draws mean the
    # budget is only a lower bound.
    totals = {"+12V": total_power_12v, "-12V": total_power_neg12v, "+5V": total_power_5v}
    if case.powered is not False:
        for _, case_field, label in RAILS:
            capacity = getattr(case, case_field)
            names = unknown_draw[label]
            if capacity is None or not names or totals[label] > capacity:
                continue
            count = len(names)
            warnings.append(
                RackValidationError(
                    field="power",
                    message=(
                        f"{label}: at least {totals[label]}mA of {capacity}mA, plus {count} "
                        f"module{'' if count == 1 else 's'} with unknown draw; budget not confirmed"
                    ),
                    details={
                        "code": "POWER_RAIL_INCOMPLETE",
                        "rail": label,
                        "known_draw_ma": totals[label],
                        "case_capacity_ma": capacity,
                        "unknown_draw_count": count,
                        "unknown_modules": names[:UNKNOWN_NAMES_SHOWN],
                    },
                )
            )

    return len(errors) == 0, errors, warnings
