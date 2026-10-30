"""Catalog-backed rack compatibility calculations.

Fail-closed: missing case or module specs produce ``incomplete`` rather than
invented fit. Hard contradictions produce ``conflict``. Fully evidenced checks
produce ``verified``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from cases.catalog_service import get_case_by_slug, pick_primary_revision
from cases.compatibility_schemas import (
    CheckResult,
    CompatibilityModuleIn,
    CompatibilityRequest,
    CompatibilityResponse,
    CompatibilityStatus,
    PowerRailResult,
    RowCapacityResult,
)
from cases.models import CaseCatalog, CasePowerSystem, CaseRevision, CaseRow
from modules.models import Module

EURORACK_LIKE = {"eurorack", "intellijel_1u", "pulplogic_1u"}


@dataclass
class ResolvedModule:
    name: str
    row_index: int
    start_hp: int
    hp: Optional[int]
    depth_mm: Optional[float]
    format_family: str
    power_12v_ma: Optional[int]
    power_neg12v_ma: Optional[int]
    power_5v_ma: Optional[int]
    requires_close_patched_lid: Optional[bool]
    module_id: Optional[int]


def _status_rank(status: CompatibilityStatus) -> int:
    return {"verified": 0, "incomplete": 1, "conflict": 2}[status]


def _worst(*statuses: CompatibilityStatus) -> CompatibilityStatus:
    return max(statuses, key=_status_rank)


def _resolve_modules(db: Session, specs: list[CompatibilityModuleIn]) -> tuple[list[ResolvedModule], list[CheckResult]]:
    resolved: list[ResolvedModule] = []
    warnings: list[CheckResult] = []
    for idx, spec in enumerate(specs):
        module: Optional[Module] = None
        if spec.module_id is not None:
            module = db.query(Module).filter(Module.id == spec.module_id).first()
            if module is None:
                warnings.append(
                    CheckResult(
                        status="conflict",
                        code="MODULE_NOT_FOUND",
                        message=f"modules[{idx}]: module_id {spec.module_id} not found",
                        details={"module_id": spec.module_id, "index": idx},
                    )
                )
                continue

        name = spec.name or (module.name if module else f"module[{idx}]")
        hp = spec.hp if spec.hp is not None else (module.hp if module else None)
        # Prefer explicit request depth; fall back to registry depth_mm when present.
        depth = spec.depth_mm
        if depth is None and module is not None:
            depth = getattr(module, "depth_mm", None)
        fmt = (spec.format_family or "eurorack").strip().lower()
        p12 = spec.power_12v_ma if spec.power_12v_ma is not None else (module.power_12v_ma if module else None)
        pn12 = (
            spec.power_neg12v_ma
            if spec.power_neg12v_ma is not None
            else (module.power_neg12v_ma if module else None)
        )
        p5 = spec.power_5v_ma if spec.power_5v_ma is not None else (module.power_5v_ma if module else None)

        if hp is None:
            warnings.append(
                CheckResult(
                    status="incomplete",
                    code="MODULE_HP_UNKNOWN",
                    message=f"modules[{idx}] ({name}): width (HP) unknown",
                    details={"index": idx, "name": name},
                )
            )

        resolved.append(
            ResolvedModule(
                name=name,
                row_index=spec.row_index,
                start_hp=spec.start_hp,
                hp=hp,
                depth_mm=depth,
                format_family=fmt,
                power_12v_ma=p12,
                power_neg12v_ma=pn12,
                power_5v_ma=p5,
                requires_close_patched_lid=spec.requires_close_patched_lid,
                module_id=spec.module_id,
            )
        )
    return resolved, warnings


def _row_layout(revision: CaseRevision, case: CaseCatalog) -> list[CaseRow]:
    rows = sorted(list(revision.rows or []), key=lambda r: r.row_index)
    if rows:
        return rows
    # Synthetic single row from revision capacity when row records are absent.
    if revision.capacity_value is not None or revision.row_count:
        count = revision.row_count or 1
        per = None
        if revision.capacity_value is not None and count:
            per = float(revision.capacity_value) / float(count)
        synthetic: list[CaseRow] = []
        for i in range(int(count)):
            synthetic.append(
                CaseRow(
                    row_index=i,
                    format_family=case.format_family,
                    capacity_value=per,
                    capacity_unit=revision.capacity_unit,
                    depth_min_mm=revision.depth_min_mm,
                    depth_max_mm=revision.depth_max_mm,
                )
            )
        return synthetic
    return []


def _format_check(case: CaseCatalog, modules: list[ResolvedModule]) -> CheckResult:
    case_fmt = case.format_family
    if not modules:
        return CheckResult(
            status="verified",
            code="FORMAT_EMPTY",
            message="No modules to evaluate for format compatibility",
            details={"case_format_family": case_fmt},
        )

    conflicts = []
    for m in modules:
        # Eurorack-like modules only fit eurorack-like case rows; strict mismatch otherwise.
        if case_fmt in EURORACK_LIKE and m.format_family not in EURORACK_LIKE:
            conflicts.append(m.name)
        elif case_fmt not in EURORACK_LIKE and m.format_family != case_fmt:
            # Placement engine is Eurorack-first; non-matching formats conflict for planning.
            if m.format_family in EURORACK_LIKE:
                conflicts.append(m.name)
            elif m.format_family != case_fmt:
                conflicts.append(m.name)

    if conflicts:
        return CheckResult(
            status="conflict",
            code="FORMAT_MISMATCH",
            message=(
                f"Case format {case_fmt!r} is not compatible with module format(s) "
                f"for: {', '.join(conflicts)}"
            ),
            details={"case_format_family": case_fmt, "conflicting_modules": conflicts},
        )

    if case_fmt not in EURORACK_LIKE:
        return CheckResult(
            status="incomplete",
            code="FORMAT_PLACEMENT_LIMITED",
            message=(
                f"Case format {case_fmt!r} is cataloged; row-wise HP placement is "
                "Eurorack-oriented and may be incomplete for this ecosystem."
            ),
            details={"case_format_family": case_fmt},
        )

    return CheckResult(
        status="verified",
        code="FORMAT_OK",
        message=f"Module formats are compatible with case format {case_fmt!r}",
        details={"case_format_family": case_fmt},
    )


def _physical_and_capacity(
    case: CaseCatalog,
    revision: CaseRevision,
    modules: list[ResolvedModule],
) -> tuple[CheckResult, list[RowCapacityResult], list[CheckResult]]:
    warnings: list[CheckResult] = []
    rows = _row_layout(revision, case)
    if not rows:
        incomplete = CheckResult(
            status="incomplete",
            code="LAYOUT_UNKNOWN",
            message="Case revision has no row/capacity layout; physical fit not computable",
            details={},
        )
        return incomplete, [], [incomplete]

    row_by_index = {r.row_index: r for r in rows}
    used: dict[int, float] = {r.row_index: 0.0 for r in rows}
    occupancy: dict[int, list[bool]] = {}
    for r in rows:
        cap = int(r.capacity_value) if r.capacity_value is not None and r.capacity_unit == "hp" else 0
        occupancy[r.row_index] = [False] * max(cap, 0)

    fit_status: CompatibilityStatus = "verified"
    messages: list[str] = []

    for m in modules:
        if m.row_index not in row_by_index:
            fit_status = "conflict"
            messages.append(f"{m.name}: row {m.row_index} does not exist on case")
            continue

        row = row_by_index[m.row_index]
        unit = row.capacity_unit or revision.capacity_unit
        if unit != "hp":
            fit_status = _worst(fit_status, "incomplete")
            messages.append(
                f"{m.name}: row {m.row_index} uses capacity unit {unit!r}; HP placement incomplete"
            )
            if m.hp is not None and row.capacity_value is not None:
                used[m.row_index] += float(m.hp)
            continue

        if m.hp is None:
            fit_status = _worst(fit_status, "incomplete")
            messages.append(f"{m.name}: HP unknown; cannot verify placement")
            continue

        row_hp = int(row.capacity_value) if row.capacity_value is not None else None
        if row_hp is None:
            fit_status = _worst(fit_status, "incomplete")
            messages.append(f"{m.name}: row {m.row_index} capacity unknown")
            continue

        if m.start_hp + m.hp > row_hp:
            fit_status = "conflict"
            messages.append(
                f"{m.name}: {m.hp}HP at start {m.start_hp} exceeds row {m.row_index} capacity {row_hp}HP"
            )
            continue

        cells = occupancy[m.row_index]
        overlap = False
        for hp in range(m.start_hp, m.start_hp + m.hp):
            if hp < len(cells) and cells[hp]:
                overlap = True
                break
        if overlap:
            fit_status = "conflict"
            messages.append(f"{m.name}: overlaps another module on row {m.row_index}")
            continue

        for hp in range(m.start_hp, m.start_hp + m.hp):
            if hp < len(cells):
                cells[hp] = True
        used[m.row_index] += float(m.hp)

        # Depth: conservative usable depth is min of depth_min_mm and depth_max_mm when both set.
        case_depth = row.depth_min_mm
        if case_depth is None:
            case_depth = revision.depth_min_mm
        if case_depth is None:
            case_depth = row.depth_max_mm or revision.depth_max_mm

        if m.depth_mm is not None:
            if case_depth is None:
                fit_status = _worst(fit_status, "incomplete")
                warnings.append(
                    CheckResult(
                        status="incomplete",
                        code="DEPTH_CASE_UNKNOWN",
                        message=(
                            f"{m.name}: module depth {m.depth_mm}mm provided but case usable "
                            "depth is unspecified"
                        ),
                        details={"module": m.name, "module_depth_mm": m.depth_mm},
                    )
                )
            elif m.depth_mm > case_depth:
                fit_status = "conflict"
                messages.append(
                    f"{m.name}: depth {m.depth_mm}mm exceeds conservative case depth {case_depth}mm"
                )
        else:
            if case_depth is not None:
                warnings.append(
                    CheckResult(
                        status="incomplete",
                        code="DEPTH_MODULE_UNKNOWN",
                        message=f"{m.name}: module depth not provided; depth fit not verified",
                        details={"module": m.name, "case_depth_mm": case_depth},
                    )
                )
                fit_status = _worst(fit_status, "incomplete")

    remaining: list[RowCapacityResult] = []
    for row in rows:
        cap = float(row.capacity_value) if row.capacity_value is not None else None
        used_v = used.get(row.row_index, 0.0)
        if cap is None:
            remaining.append(
                RowCapacityResult(
                    row_index=row.row_index,
                    format_family=row.format_family,
                    capacity_unit=row.capacity_unit,
                    capacity_value=None,
                    used_value=used_v or None,
                    remaining_value=None,
                    status="incomplete",
                    message="Row capacity unspecified",
                )
            )
            fit_status = _worst(fit_status, "incomplete")
            continue
        rem = cap - used_v
        status: CompatibilityStatus = "verified"
        msg = f"{rem:g} remaining of {cap:g} {row.capacity_unit or 'units'}"
        if rem < 0:
            status = "conflict"
            msg = f"Over capacity by {abs(rem):g}"
            fit_status = "conflict"
        remaining.append(
            RowCapacityResult(
                row_index=row.row_index,
                format_family=row.format_family,
                capacity_unit=row.capacity_unit,
                capacity_value=cap,
                used_value=used_v,
                remaining_value=rem,
                status=status,
                message=msg,
            )
        )

    code = {
        "verified": "PHYSICAL_FIT_OK",
        "incomplete": "PHYSICAL_FIT_INCOMPLETE",
        "conflict": "PHYSICAL_FIT_CONFLICT",
    }[fit_status]
    physical = CheckResult(
        status=fit_status,
        code=code,
        message="; ".join(messages) if messages else "Physical row placement evaluated",
        details={"message_count": len(messages)},
    )
    return physical, remaining, warnings


def _primary_power(revision: CaseRevision) -> Optional[CasePowerSystem]:
    systems = list(revision.power_systems or [])
    if not systems:
        return None
    for s in systems:
        if s.name == "primary":
            return s
    return systems[0]


def _power_checks(
    case: CaseCatalog,
    revision: CaseRevision,
    modules: list[ResolvedModule],
) -> tuple[list[PowerRailResult], CheckResult, CheckResult, list[CheckResult]]:
    warnings: list[CheckResult] = []
    power = _primary_power(revision)

    draw12 = sum(m.power_12v_ma or 0 for m in modules)
    draw_n12 = sum(m.power_neg12v_ma or 0 for m in modules)
    draw5 = sum(m.power_5v_ma or 0 for m in modules)
    any_draw = draw12 > 0 or draw_n12 > 0 or draw5 > 0
    # A rail a module does not state is unknown, never 0 (spec 003 FR-022), +5V included:
    # a jumper-set 4ms module may draw from +5V without the page saying so.
    unknown12 = [m.name for m in modules if m.power_12v_ma is None]
    unknown_n12 = [m.name for m in modules if m.power_neg12v_ma is None]
    unknown5 = [m.name for m in modules if m.power_5v_ma is None]
    any_unknown_draw = bool(unknown12 or unknown_n12 or unknown5)

    rails: list[PowerRailResult] = []

    def rail_result(name: str, capacity: Optional[int], draw: int, unknown: list[str]) -> PowerRailResult:
        n = len(unknown)
        plus_unknown = f" plus {n} unknown" if n else ""
        common = {"rail": name, "module_draw_ma": draw, "unknown_draw_count": n, "unknown_modules": unknown}
        if capacity is None:
            if draw > 0 or n:
                return PowerRailResult(
                    **common,
                    case_capacity_ma=None,
                    headroom_ma=None,
                    status="incomplete",
                    message=f"{name}: case capacity unspecified; cannot compute headroom",
                )
            return PowerRailResult(
                **common,
                case_capacity_ma=None,
                headroom_ma=None,
                status="incomplete",
                message=f"{name}: case capacity unspecified",
            )
        headroom = capacity - draw
        if headroom < 0:
            return PowerRailResult(
                **common,
                case_capacity_ma=capacity,
                headroom_ma=headroom,
                status="conflict",
                message=f"{name}: draw {draw}mA{plus_unknown} exceeds capacity {capacity}mA",
            )
        if n:
            return PowerRailResult(
                **common,
                case_capacity_ma=capacity,
                headroom_ma=headroom,
                status="incomplete",
                message=(
                    f"{name}: at least {draw}mA of {capacity}mA{plus_unknown}; "
                    f"at most {headroom}mA headroom"
                ),
            )
        return PowerRailResult(
            **common,
            case_capacity_ma=capacity,
            headroom_ma=headroom,
            status="verified",
            message=f"{name}: {headroom}mA headroom ({draw}/{capacity}mA)",
        )

    cap12 = power.current_pos12_ma if power else None
    cap_n12 = power.current_neg12_ma if power else None
    cap5 = power.current_pos5_ma if power else None

    if case.powered is False and any_draw:
        rails.append(
            PowerRailResult(
                rail="+12V",
                case_capacity_ma=0,
                module_draw_ma=draw12,
                headroom_ma=-draw12 if draw12 else 0,
                status="conflict",
                message="Case is unpowered but modules declare power draw",
            )
        )
        pos5 = CheckResult(
            status="conflict",
            code="POWER_ON_UNPOWERED_CASE",
            message="Unpowered case cannot supply module rails including +5V",
            details={"draw_5v_ma": draw5},
        )
        connectors = CheckResult(
            status="conflict",
            code="CONNECTORS_UNPOWERED",
            message="Unpowered case has no powered header budget",
            details={},
        )
        return rails, connectors, pos5, warnings

    rails.extend(
        [
            rail_result("+12V", cap12, draw12, unknown12),
            rail_result("-12V", cap_n12, draw_n12, unknown_n12),
            rail_result("+5V", cap5, draw5, unknown5),
        ]
    )

    if any_unknown_draw:
        warnings.append(
            CheckResult(
                status="incomplete",
                code="MODULE_POWER_UNKNOWN",
                message="One or more modules lack power specs; draw totals may be understated",
                details={
                    "unknown_draw_count": {
                        "+12V": len(unknown12),
                        "-12V": len(unknown_n12),
                        "+5V": len(unknown5),
                    },
                },
            )
        )

    # +5V requirement: modules needing +5 when case has no +5 rail.
    needs_5 = [m.name for m in modules if (m.power_5v_ma or 0) > 0]
    if needs_5 and cap5 is None:
        pos5 = CheckResult(
            status="incomplete",
            code="POS5_CASE_UNKNOWN",
            message=(
                "Modules require +5V but case +5V capacity is unspecified "
                f"({', '.join(needs_5)})"
            ),
            details={"modules": needs_5},
        )
    elif needs_5 and cap5 == 0:
        pos5 = CheckResult(
            status="conflict",
            code="POS5_UNAVAILABLE",
            message=f"Modules require +5V but case reports 0mA (+5): {', '.join(needs_5)}",
            details={"modules": needs_5, "case_pos5_ma": cap5},
        )
    elif needs_5 and cap5 is not None and draw5 > cap5:
        pos5 = CheckResult(
            status="conflict",
            code="POS5_EXCEEDED",
            message=f"+5V draw {draw5}mA exceeds case capacity {cap5}mA",
            details={"draw_ma": draw5, "capacity_ma": cap5},
        )
    elif needs_5 and unknown5:
        pos5 = CheckResult(
            status="incomplete",
            code="POS5_INCOMPLETE",
            message=(
                f"+5V: at least {draw5}/{cap5}mA, plus {len(unknown5)} module"
                f"{'' if len(unknown5) == 1 else 's'} with unknown +5V draw"
            ),
            details={"draw_ma": draw5, "capacity_ma": cap5, "unknown_modules": unknown5},
        )
    elif needs_5:
        pos5 = CheckResult(
            status="verified",
            code="POS5_OK",
            message=f"+5V requirement within capacity ({draw5}/{cap5}mA)",
            details={"draw_ma": draw5, "capacity_ma": cap5},
        )
    elif unknown5:
        pos5 = CheckResult(
            status="incomplete",
            code="POS5_UNKNOWN",
            message=(
                f"+5V draw unknown for {len(unknown5)} module"
                f"{'' if len(unknown5) == 1 else 's'}; +5V need not confirmed"
            ),
            details={"modules": unknown5, "capacity_ma": cap5},
        )
    else:
        pos5 = CheckResult(
            status="verified",
            code="POS5_NOT_REQUIRED",
            message="Every module states +5V draw, and none needs it",
            details={},
        )

    # Connector / header availability — only when module count and connector_count known.
    connector_count = power.connector_count if power else None
    module_count = len(modules)
    if connector_count is None:
        connectors = CheckResult(
            status="incomplete",
            code="CONNECTORS_UNKNOWN",
            message="Case header/connector count unspecified; availability not computable",
            details={"module_count": module_count},
        )
    elif module_count > connector_count:
        connectors = CheckResult(
            status="conflict",
            code="CONNECTORS_EXCEEDED",
            message=f"{module_count} modules exceed {connector_count} power connectors",
            details={"module_count": module_count, "connector_count": connector_count},
        )
    else:
        connectors = CheckResult(
            status="verified",
            code="CONNECTORS_OK",
            message=f"{module_count}/{connector_count} power connectors used",
            details={
                "module_count": module_count,
                "connector_count": connector_count,
                "remaining": connector_count - module_count,
            },
        )

    if power is None and case.powered is not False:
        warnings.append(
            CheckResult(
                status="incomplete",
                code="POWER_SYSTEM_MISSING",
                message="No power system on revision; rail headroom incomplete",
                details={},
            )
        )

    return rails, connectors, pos5, warnings


def _lid_check(
    revision: CaseRevision,
    modules: list[ResolvedModule],
    plan_close_lid: bool,
) -> CheckResult:
    wants_close = plan_close_lid or any(m.requires_close_patched_lid for m in modules)
    if not wants_close:
        return CheckResult(
            status="verified",
            code="LID_NOT_REQUIRED",
            message="Close-patched lid not required for this plan",
            details={
                "close_patched_lid": revision.close_patched_lid,
                "removable_lid": revision.removable_lid,
            },
        )

    if revision.close_patched_lid is True:
        return CheckResult(
            status="verified",
            code="LID_CLOSE_SUPPORTED",
            message="Case supports close-patched lid operation",
            details={"close_patched_lid": True},
        )
    if revision.close_patched_lid is False:
        return CheckResult(
            status="conflict",
            code="LID_CLOSE_UNSUPPORTED",
            message="Plan requires closing lid while patched; case reports close_patched_lid=false",
            details={"close_patched_lid": False},
        )
    return CheckResult(
        status="incomplete",
        code="LID_CLOSE_UNKNOWN",
        message="Close-patched lid capability unspecified on case revision",
        details={"close_patched_lid": None, "removable_lid": revision.removable_lid},
    )


def evaluate_catalog_compatibility(
    db: Session,
    slug: str,
    request: CompatibilityRequest,
) -> CompatibilityResponse:
    case = get_case_by_slug(db, slug)
    if case is None:
        raise LookupError(f"Catalog case not found: {slug}")

    if request.revision_key:
        revision = next(
            (r for r in case.revisions if r.revision_key == request.revision_key),
            None,
        )
        if revision is None:
            raise LookupError(f"Revision not found: {request.revision_key}")
    else:
        revision = pick_primary_revision(list(case.revisions or []))
        if revision is None:
            raise LookupError("Case has no revisions")

    modules, resolve_warnings = _resolve_modules(db, request.modules)
    format_check = _format_check(case, modules)
    physical, remaining, depth_warnings = _physical_and_capacity(case, revision, modules)
    rails, connectors, pos5, power_warnings = _power_checks(case, revision, modules)
    lid = _lid_check(revision, modules, request.plan_close_lid)

    warnings = resolve_warnings + depth_warnings + power_warnings
    # Surface incomplete rails as warnings when overall may still be useful.
    for rail in rails:
        if rail.status == "incomplete":
            warnings.append(
                CheckResult(
                    status="incomplete",
                    code=f"RAIL_{rail.rail}",
                    message=rail.message,
                    details={
                        "rail": rail.rail,
                        "draw_ma": rail.module_draw_ma,
                        "capacity_ma": rail.case_capacity_ma,
                    },
                )
            )

    statuses: list[CompatibilityStatus] = [
        format_check.status,
        physical.status,
        connectors.status,
        pos5.status,
        lid.status,
        *[r.status for r in rails],
        *[r.status for r in remaining],
        *[w.status for w in warnings if w.status == "conflict"],
    ]
    overall = _worst(*statuses) if statuses else "verified"

    notes = [
        "Compatibility is not manufacturer-verified authority when inputs use research seed data.",
        "Missing values remain incomplete; they are never treated as zero capacity.",
    ]
    if revision.confidence in {"low", "conflict"}:
        notes.append(f"Case revision confidence is {revision.confidence!r}.")

    return CompatibilityResponse(
        case_slug=case.slug,
        manufacturer=case.manufacturer,
        model=case.model,
        format_family=case.format_family,
        revision_key=revision.revision_key,
        overall_status=overall,
        format_check=format_check,
        physical_fit=physical,
        remaining_capacity=remaining,
        power_headroom=rails,
        connector_availability=connectors,
        pos5_compatibility=pos5,
        lid_close=lid,
        warnings=warnings,
        notes=notes,
    )
