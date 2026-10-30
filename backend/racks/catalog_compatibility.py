"""Bridge rack placement to catalog compatibility when a case was materialized."""

from __future__ import annotations

from typing import Any, Optional, Protocol, Sequence

from sqlalchemy.orm import Session

from cases.compatibility import evaluate_catalog_compatibility
from cases.compatibility_schemas import (
    CompatibilityModuleIn,
    CompatibilityRequest,
    CompatibilityResponse,
    CompatibilityStatus,
)
from cases.models import Case
from modules.models import PowerConfig
from racks.models import Rack, RackModule
from racks.schemas import RackValidationError


class _ModulePlacement(Protocol):
    module_id: int
    row_index: int
    start_hp: int
    power_config_id: Optional[int]


def catalog_slug_for_case(case: Case) -> Optional[str]:
    meta = case.meta if isinstance(case.meta, dict) else {}
    slug = meta.get("catalog_slug")
    if isinstance(slug, str) and slug.strip():
        return slug.strip()
    return None


def revision_key_for_case(case: Case) -> Optional[str]:
    meta = case.meta if isinstance(case.meta, dict) else {}
    key = meta.get("catalog_revision_key")
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def _placements_to_compat_modules(
    db: Session, placements: Sequence[_ModulePlacement]
) -> list[CompatibilityModuleIn]:
    """Placements as compatibility inputs; a chosen jumper setting supplies the draws.

    A setting that does not belong to the placed module is ignored here; rack
    validation reports it as ``POWER_CONFIG_NOT_FOR_MODULE``. A rail the setting leaves
    NULL falls back to the module's column, as every inline override does.
    """
    modules = []
    for p in placements:
        draws: dict[str, Optional[int]] = {}
        config_id = getattr(p, "power_config_id", None)
        if config_id is not None:
            config = db.query(PowerConfig).filter(PowerConfig.id == config_id).first()
            if config is not None and config.module_id == p.module_id:
                draws = {
                    "power_12v_ma": config.power_12v_ma,
                    "power_neg12v_ma": config.power_neg12v_ma,
                    "power_5v_ma": config.power_5v_ma,
                }
        modules.append(
            CompatibilityModuleIn(
                module_id=p.module_id,
                row_index=p.row_index,
                start_hp=p.start_hp,
                **draws,
            )
        )
    return modules


def evaluate_case_module_catalog_compatibility(
    db: Session,
    case_id: int,
    placements: Sequence[_ModulePlacement],
    *,
    plan_close_lid: bool = False,
) -> dict[str, Any]:
    """Evaluate catalog compatibility for a case_id + module placements (pre- or post-persist)."""
    case = db.query(Case).filter(Case.id == case_id).first()
    if case is None:
        return {
            "bridge_status": "conflict",
            "message": f"Legacy case_id {case_id} not found",
            "catalog_slug": None,
            "case_id": case_id,
            "compatibility": None,
        }

    slug = catalog_slug_for_case(case)
    if not slug:
        return {
            "bridge_status": "incomplete",
            "message": (
                "Case has no meta.catalog_slug. Materialize from the normalized catalog "
                "to enable catalog compatibility checks."
            ),
            "catalog_slug": None,
            "case_id": case.id,
            "compatibility": None,
        }

    modules = _placements_to_compat_modules(db, placements)
    request = CompatibilityRequest(
        revision_key=revision_key_for_case(case),
        modules=modules,
        plan_close_lid=plan_close_lid,
    )
    try:
        report: CompatibilityResponse = evaluate_catalog_compatibility(db, slug, request)
    except LookupError as exc:
        return {
            "bridge_status": "conflict",
            "message": str(exc),
            "catalog_slug": slug,
            "case_id": case.id,
            "compatibility": None,
        }

    return {
        "bridge_status": "ok",
        "message": "Catalog compatibility evaluated from materialized case link",
        "catalog_slug": slug,
        "case_id": case.id,
        "module_count": len(modules),
        "compatibility": report.model_dump(mode="json"),
    }


def dual_gate_catalog_errors_and_warnings(
    db: Session,
    case_id: int,
    placements: Sequence[_ModulePlacement],
    *,
    plan_close_lid: bool = False,
) -> tuple[list[RackValidationError], list[RackValidationError]]:
    """Map catalog compatibility into hard errors (conflict) and soft warnings (incomplete).

    When the case is not linked to the catalog, no dual-gate findings are emitted
    (legacy validation remains authoritative alone).
    """
    report = evaluate_case_module_catalog_compatibility(
        db, case_id, placements, plan_close_lid=plan_close_lid
    )
    errors: list[RackValidationError] = []
    warnings: list[RackValidationError] = []

    if report["bridge_status"] == "incomplete" and report.get("catalog_slug") is None:
        # Unlinked legacy case — dual-gate not applicable.
        return errors, warnings

    if report["bridge_status"] == "conflict" and report.get("compatibility") is None:
        errors.append(
            RackValidationError(
                field="catalog",
                message=report.get("message") or "Catalog compatibility bridge failed",
                details={"code": "CATALOG_BRIDGE_CONFLICT", "bridge": report},
            )
        )
        return errors, warnings

    compat = report.get("compatibility") or {}
    overall: CompatibilityStatus | str = compat.get("overall_status") or "incomplete"

    def _collect(status: str, code: str, message: str, details: dict | None = None) -> None:
        item = RackValidationError(
            field="catalog",
            message=message,
            details={"code": code, **(details or {})},
        )
        if status == "conflict":
            errors.append(item)
        elif status == "incomplete":
            warnings.append(item)

    for key in (
        "format_check",
        "physical_fit",
        "connector_availability",
        "pos5_compatibility",
        "lid_close",
    ):
        check = compat.get(key) or {}
        if check.get("status") in {"conflict", "incomplete"}:
            _collect(
                check["status"],
                check.get("code") or key.upper(),
                check.get("message") or key,
                {"check": key},
            )

    for rail in compat.get("power_headroom") or []:
        if rail.get("status") in {"conflict", "incomplete"}:
            _collect(
                rail["status"],
                f"RAIL_{rail.get('rail', 'UNKNOWN')}",
                rail.get("message") or str(rail.get("rail")),
                {"rail": rail.get("rail")},
            )

    for warn in compat.get("warnings") or []:
        if warn.get("status") == "conflict":
            _collect(warn["status"], warn.get("code") or "CATALOG_WARNING", warn.get("message") or "")
        elif warn.get("status") == "incomplete":
            _collect(warn["status"], warn.get("code") or "CATALOG_WARNING", warn.get("message") or "")

    if overall == "conflict" and not errors:
        errors.append(
            RackValidationError(
                field="catalog",
                message="Catalog compatibility overall status is conflict",
                details={"code": "CATALOG_OVERALL_CONFLICT", "overall_status": overall},
            )
        )
    elif overall == "incomplete" and not warnings and not errors:
        warnings.append(
            RackValidationError(
                field="catalog",
                message="Catalog compatibility overall status is incomplete (missing specs)",
                details={"code": "CATALOG_OVERALL_INCOMPLETE", "overall_status": overall},
            )
        )

    return errors, warnings


def evaluate_rack_catalog_compatibility(
    db: Session,
    rack: Rack,
    *,
    plan_close_lid: bool = False,
) -> dict[str, Any]:
    """Return catalog compatibility for a rack, or an incomplete bridge report."""
    rack_modules = db.query(RackModule).filter(RackModule.rack_id == rack.id).all()
    return evaluate_case_module_catalog_compatibility(
        db,
        rack.case_id,
        rack_modules,
        plan_close_lid=plan_close_lid,
    )
