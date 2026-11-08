"""Confirming a Rig's Readings (spec 009): the owner's final list becomes the Rig's layout.

Confirmation applies to the whole Rig, across every current Reading of it, and needs each of
them to be ``read``. The owner keeps Sightings (each with the catalog Module chosen for it and
its position), adds Modules by hand, and leaves Sightings out; every module or unknown
Sighting must be kept or left out. Confirmed positions count as placement (decision 59,
superseding 35), so the result is one new Rig revision whose placements are those positions,
and an inventory revision that names the Sightings it came from.

The list replaces only the rows the current Readings cover: a photo of one row says nothing
about the others, so their Placements stay, and every check runs across the whole resulting
Rig.

Everything is checked before anything is written. A refusal names the Modules involved and
changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from canon.contracts import canonical_sha256
from canon.inventory_persist import persist_system_inventory_revision
from canon.models import PhotoReadingRecord, PhotoSightingRecord
from canon.visual_contracts import InventoryItem, ResolutionStatus, SystemInventoryRevision
from cases.models import Case
from core import generate_rig_suggested_name
from evidence.readings import CURRENT_STATUSES, move_readings
from modules.models import Module
from racks.catalog_compatibility import dual_gate_catalog_errors_and_warnings
from racks.models import Rack, RackModule
from racks.schemas import RackModuleSpec, RackValidationError
from racks.validation import validate_rack_configuration
from runs.bridge import ensure_rig_revision

# Sightings the owner must keep or leave out; a Blank Panel or not-Eurorack one may go unsaid.
DECIDED_KINDS = frozenset({"module", "unknown"})
CONFIRMATION_BUILDER = "photo_reading_confirmation"


class ConfirmedSighting(BaseModel):
    sighting_id: str = Field(min_length=1)
    module_id: int = Field(ge=1)
    row_index: int = Field(ge=0)
    start_hp: int = Field(ge=0)


class AddedModule(BaseModel):
    module_id: int = Field(ge=1)
    row_index: int = Field(ge=0)
    start_hp: int = Field(ge=0)


class ReadingConfirmRequest(BaseModel):
    items: list[ConfirmedSighting] = Field(default_factory=list)
    added: list[AddedModule] = Field(default_factory=list)
    excluded: list[str] = Field(default_factory=list)
    case_id: int | None = Field(default=None, ge=1)


class ConfirmRefused(Exception):
    """A confirmation that changes nothing. ``detail`` carries ``code`` and, where Modules
    are involved, ``modules``."""

    def __init__(self, status_code: int, code: str, **detail: Any) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.detail = {"code": code, **detail}


@dataclass(frozen=True)
class ConfirmResult:
    rig_revision_id: str
    inventory: SystemInventoryRevision
    placements: list[dict[str, int]]
    warnings: list[RackValidationError]


@dataclass(frozen=True)
class _Placement:
    module: Module
    row_index: int
    start_hp: int
    sighting_id: str | None
    # A Placement kept from a row no current Reading covers, with its jumper setting.
    placement_id: int | None = None
    power_config_id: int | None = None


def _current_readings(db: Session, rack: Rack) -> list[PhotoReadingRecord]:
    readings = (
        db.query(PhotoReadingRecord)
        .filter(
            PhotoReadingRecord.rack_id == rack.id,
            PhotoReadingRecord.status.in_(CURRENT_STATUSES),
        )
        .order_by(PhotoReadingRecord.created_at.asc(), PhotoReadingRecord.id.asc())
        .all()
    )
    if not readings:
        raise ConfirmRefused(409, "NO_CURRENT_READING")
    waiting = [str(r.id) for r in readings if r.status != "read"]
    if waiting:
        raise ConfirmRefused(409, "READING_NOT_READ", readings=waiting)
    return readings


def _placements(
    db: Session, body: ReadingConfirmRequest, sightings: dict[str, PhotoSightingRecord]
) -> list[_Placement]:
    named = [item.sighting_id for item in body.items] + list(body.excluded)
    repeated = sorted({sid for sid in named if named.count(sid) > 1})
    if repeated:
        raise ConfirmRefused(400, "SIGHTING_DECIDED_TWICE", sightings=repeated)
    unknown = sorted(set(named) - set(sightings))
    if unknown:
        raise ConfirmRefused(400, "SIGHTING_NOT_IN_READING", sightings=unknown)
    panels = sorted(
        item.sighting_id for item in body.items if sightings[item.sighting_id].kind == "blank_panel"
    )
    if panels:
        raise ConfirmRefused(409, "BLANK_PANEL_NOT_INVENTORY", sightings=panels)
    decided = set(named)
    undecided = sorted(
        sid for sid, s in sightings.items() if s.kind in DECIDED_KINDS and sid not in decided
    )
    if undecided:
        raise ConfirmRefused(409, "SIGHTINGS_UNDECIDED", sightings=undecided)

    wanted = {item.module_id for item in body.items} | {add.module_id for add in body.added}
    modules = {m.id: m for m in db.query(Module).filter(Module.id.in_(wanted))} if wanted else {}
    missing = sorted(wanted - set(modules))
    if missing:
        raise ConfirmRefused(400, "MODULE_NOT_FOUND", modules=missing)
    return [
        _Placement(modules[item.module_id], item.row_index, item.start_hp, item.sighting_id)
        for item in body.items
    ] + [
        _Placement(modules[add.module_id], add.row_index, add.start_hp, None) for add in body.added
    ]


def _covered_rows(readings: list[PhotoReadingRecord]) -> set[int]:
    return {row for r in readings for row in range(int(r.first_row), int(r.last_row) + 1)}


def _kept_placements(db: Session, rack: Rack, covered: set[int]) -> list[_Placement]:
    """The Rig's Placements on rows no current Reading covers, which stay as they are."""
    kept = (
        db.query(RackModule)
        .options(joinedload(RackModule.module))
        .filter(RackModule.rack_id == rack.id, RackModule.row_index.notin_(covered))
        .order_by(RackModule.row_index.asc(), RackModule.start_hp.asc(), RackModule.id.asc())
        .all()
    )
    return [
        _Placement(
            rm.module,
            int(rm.row_index),
            int(rm.start_hp),
            None,
            placement_id=int(rm.id),  # type: ignore[arg-type]
            power_config_id=rm.power_config_id,
        )
        for rm in kept
    ]


def _check_layout(
    db: Session, placements: list[_Placement], case_id: int | None
) -> list[RackValidationError]:
    """Refuse overlapping HP in a row, and a row past a named Case, naming the Modules; then
    every other rule a placement keeps. Returns the advisories, such as an unknown budget."""
    clashing: set[int] = set()
    for i, a in enumerate(placements):
        for b in placements[i + 1 :]:
            if a.row_index == b.row_index and (
                a.start_hp < b.start_hp + b.module.hp and b.start_hp < a.start_hp + a.module.hp
            ):
                clashing |= {int(a.module.id), int(b.module.id)}
    if clashing:
        raise ConfirmRefused(409, "POSITIONS_OVERLAP", modules=sorted(clashing))

    case = db.get(Case, case_id) if case_id is not None else None
    if case_id is not None and case is None:
        raise ConfirmRefused(400, "CASE_NOT_FOUND")
    if case is not None:
        widths = list(case.hp_per_row or [])
        past = sorted(
            {
                int(p.module.id)
                for p in placements
                if p.row_index >= len(widths) or p.start_hp + p.module.hp > widths[p.row_index]
            }
        )
        if past:
            raise ConfirmRefused(409, "ROW_PAST_CASE", modules=past)

    specs = [
        RackModuleSpec(
            module_id=p.module.id,
            row_index=p.row_index,
            start_hp=p.start_hp,
            power_config_id=p.power_config_id,
        )
        for p in placements
    ]
    _, errors, warnings = validate_rack_configuration(db, case_id, specs)
    catalog_errors, catalog_warnings = dual_gate_catalog_errors_and_warnings(db, case_id, specs)
    errors = list(errors) + list(catalog_errors)
    if errors:
        involved = sorted(
            {
                int((e.details or {})["module_id"])
                for e in errors
                if (e.details or {}).get("module_id")
            }
        )
        raise ConfirmRefused(
            409, "PLACEMENT_INVALID", modules=involved, errors=[e.model_dump() for e in errors]
        )
    return list(warnings) + list(catalog_warnings)


def _instance_id(placement: _Placement, index: int) -> str:
    if placement.sighting_id:
        return f"sighting-{placement.sighting_id}"
    if placement.placement_id is not None:
        return f"placement-{placement.placement_id}"
    return f"added-{index}"


def _inventory_revision(
    rack: Rack, placements: list[_Placement], *, confirmed_by: str, now: datetime
) -> SystemInventoryRevision:
    items = tuple(
        InventoryItem(
            instance_id=_instance_id(p, index),
            module_revision_id=f"catalog-module-{p.module.id}",
            manufacturer=p.module.brand,
            model=p.module.name,
            position=index,
            resolution=ResolutionStatus.USER_CONFIRMED,
            source_candidate_ids=(p.sighting_id,) if p.sighting_id else (),
            evidence_ids=(p.sighting_id,) if p.sighting_id else (),
            confirmed_by=confirmed_by,
            confirmed_at=now,
        )
        for index, p in enumerate(placements)
    )
    payload = {
        "system_id": f"rack-{rack.id}",
        "items": [
            {
                "instance_id": item.instance_id,
                "module_revision_id": item.module_revision_id,
                "position": item.position,
                "source_candidate_ids": list(item.source_candidate_ids),
            }
            for item in items
        ],
        "placements": [[p.row_index, p.start_hp] for p in placements],
        "builder": CONFIRMATION_BUILDER,
        "confirmed_at": now.isoformat(),
    }
    return SystemInventoryRevision(
        inventory_revision_id=f"inv-rev-{canonical_sha256(payload)[:24]}",
        system_id=f"rack-{rack.id}",
        items=items,
        unresolved_candidate_ids=(),
        created_at=now,
        created_by=confirmed_by,
    ).seal()


def confirm_readings(
    db: Session, rack: Rack, body: ReadingConfirmRequest, *, confirmed_by: str
) -> ConfirmResult:
    """Check the owner's final list against the Rig's current Readings, then write it as the
    Rig's placements, one inventory revision and one Rig revision. The caller commits."""
    readings = _current_readings(db, rack)
    sightings = {
        str(s.id): s
        for s in db.query(PhotoSightingRecord).filter(
            PhotoSightingRecord.reading_id.in_([r.id for r in readings])
        )
    }
    confirmed = _placements(db, body, sightings)
    covered = _covered_rows(readings)
    placements = confirmed + _kept_placements(db, rack, covered)
    if not placements:
        raise ConfirmRefused(400, "NO_MODULES")
    case_id = body.case_id if body.case_id is not None else rack.case_id
    warnings = _check_layout(db, placements, case_id)

    ids = [str(r.id) for r in readings]
    if move_readings(db, ids, from_statuses=("read",), to="confirmed") != len(ids):
        # A Retake or Retry replaced one since they were loaded; the owner reviews again.
        raise ConfirmRefused(409, "READINGS_CHANGED")

    now = datetime.now(timezone.utc)
    rack.case_id = case_id
    db.query(RackModule).filter(
        RackModule.rack_id == rack.id, RackModule.row_index.in_(covered)
    ).delete()
    for p in confirmed:
        db.add(
            RackModule(
                rack_id=rack.id, module_id=p.module.id, row_index=p.row_index, start_hp=p.start_hp
            )
        )
    if rack.name == rack.name_suggested:
        # The owner hasn't named it, so the name follows what's on it now.
        rack.name = rack.name_suggested = generate_rig_suggested_name(p.module for p in placements)
    db.flush()

    inventory = _inventory_revision(rack, placements, confirmed_by=confirmed_by, now=now)
    persist_system_inventory_revision(db, inventory, rack_id=int(rack.id))  # type: ignore[arg-type]
    revision = ensure_rig_revision(db, rack)
    db.flush()
    return ConfirmResult(
        rig_revision_id=str(revision.id),
        inventory=inventory,
        placements=[
            {"module_id": int(p.module.id), "row_index": p.row_index, "start_hp": p.start_hp}
            for p in placements
        ],
        warnings=warnings,
    )
