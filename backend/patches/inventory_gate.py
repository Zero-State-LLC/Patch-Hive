"""Confirmed-inventory gates for legacy rack → patch generation.

Rack modules placed by the user are treated as manual USER_CONFIRMED inventory
for the dual-path generator. Vision candidates must never appear as module IDs
here; those require the confirmation workflow before inventory revision creation.

This module bridges `canon.inventory` contracts into the existing
`patches.engine` surface without requiring Alembic persistence yet.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from canon.inventory import inventory_ready_for_generation
from canon.inventory_persist import load_system_inventory_revision
from canon.models import SystemInventoryRevisionRecord
from canon.visual_contracts import InventoryItem, ResolutionStatus, SystemInventoryRevision
from modules.models import Module
from racks.models import Rack, RackModule

GATE_VERSION = "inventory-gate.1.0.0"
# Who a placement revision names, which tells it apart from a photo confirmation's.
PLACEMENT_REVISION_AUTHOR_PREFIX = "rack-owner:"
CATALOG_MODULE_LABEL = re.compile(r"catalog-module-(\d+)")


@dataclass(frozen=True)
class InventoryGateReport:
    """Outcome of binding a rack to a confirmed inventory revision."""

    inventory: SystemInventoryRevision
    allowed_catalog_module_ids: frozenset[int]
    ready: bool
    code: str  # OK | NOT_COMPUTABLE | FILTERED
    messages: tuple[str, ...]
    dropped_patch_count: int = 0

    def provenance_dict(self) -> dict[str, object]:
        return {
            "gate_version": GATE_VERSION,
            "inventory_revision_id": self.inventory.inventory_revision_id,
            "inventory_canonical_hash": self.inventory.canonical_hash,
            "allowed_module_count": len(self.allowed_catalog_module_ids),
            "ready": self.ready,
            "code": self.code,
            "messages": list(self.messages),
            "dropped_patch_count": self.dropped_patch_count,
        }


def confirmed_catalog_module_ids(db: Session, rack: Rack) -> frozenset[int]:
    """Catalog Module.id values present on the rack (user-confirmed placements)."""

    rows = db.query(RackModule.module_id).filter(RackModule.rack_id == rack.id).all()
    return frozenset(int(module_id) for (module_id,) in rows if module_id is not None)


def build_manual_inventory_from_rack(
    db: Session,
    rack: Rack,
    *,
    created_at: datetime | None = None,
    created_by: str | None = None,
) -> SystemInventoryRevision:
    """Build an immutable inventory revision from placed rack modules.

    Each placed module is USER_CONFIRMED (manual/hybrid confirmation path).
    Module identity uses stable `catalog-module-{id}` revision labels until a
    dedicated module-revision registry is fully authoritative for generation.
    """

    created = created_at or datetime.now(timezone.utc)
    rack_modules = (
        db.query(RackModule).filter(RackModule.rack_id == rack.id).order_by(RackModule.id).all()
    )
    items: list[InventoryItem] = []
    for index, rm in enumerate(rack_modules):
        module = db.query(Module).filter(Module.id == rm.module_id).first()
        manufacturer = module.brand if module else None
        model = module.name if module else None
        items.append(
            InventoryItem(
                instance_id=f"rack-mod-{rm.id}",
                module_revision_id=f"catalog-module-{rm.module_id}",
                manufacturer=manufacturer,
                model=model,
                position=index,
                resolution=ResolutionStatus.USER_CONFIRMED,
                source_candidate_ids=(),
                evidence_ids=(f"manual-rack-{rack.id}-placement-{rm.id}",),
                confirmed_by=created_by or f"rack-owner:{rack.user_id}",
                confirmed_at=created,
            )
        )

    from canon.contracts import canonical_sha256

    # Identity excludes timestamps so repeated builds yield the same revision id.
    payload = {
        "system_id": f"rack-{rack.id}",
        "items": [
            {
                "instance_id": item.instance_id,
                "module_revision_id": item.module_revision_id,
                "position": item.position,
                "resolution": item.resolution.value,
            }
            for item in items
        ],
        "builder": "manual_rack_placement",
        "gate_version": GATE_VERSION,
    }
    revision_id = f"inv-rev-{canonical_sha256(payload)[:24]}"
    revision = SystemInventoryRevision(
        inventory_revision_id=revision_id,
        system_id=f"rack-{rack.id}",
        previous_revision_id=None,
        items=tuple(items),
        unresolved_candidate_ids=(),
        created_at=created,
        created_by=created_by or f"{PLACEMENT_REVISION_AUTHOR_PREFIX}{rack.user_id}",
    )
    return revision.seal()


@dataclass(frozen=True)
class ModuleToPlace:
    """A photo-confirmed module not on the rack yet (owner decision 35, #283).

    A photo gives no reliable row or HP, so nothing places it automatically. ``module_id``
    is what the rack route takes, and None when no single catalog row matches.
    """

    instance_id: str
    module_revision_id: str
    manufacturer: str | None
    model: str | None
    module_id: int | None


def _catalog_module_id(db: Session, item: InventoryItem) -> int | None:
    """The catalog row an item names: its id label, else its one exact brand and name match."""

    label = CATALOG_MODULE_LABEL.fullmatch(item.module_revision_id)
    if label:
        module = db.get(Module, int(label.group(1)))
        return int(module.id) if module else None
    if not item.manufacturer or not item.model:
        return None
    matches = (
        db.query(Module.id)
        .filter(
            func.lower(Module.brand) == item.manufacturer.lower(),
            func.lower(Module.name) == item.model.lower(),
        )
        .limit(2)
        .all()
    )
    return int(matches[0][0]) if len(matches) == 1 else None


def modules_still_to_place(
    db: Session, rack: Rack, inventory: SystemInventoryRevision
) -> list[ModuleToPlace]:
    """Confirmed photo items in ``inventory`` that no placement on the rack accounts for.

    Each placement accounts for one confirmed copy. A placement revision's own items have
    no source candidates, so they are never listed.
    """

    placed = Counter(
        int(module_id)
        for (module_id,) in db.query(RackModule.module_id).filter(RackModule.rack_id == rack.id)
    )
    left: list[ModuleToPlace] = []
    for item in inventory.items:
        if item.resolution is not ResolutionStatus.USER_CONFIRMED or not item.source_candidate_ids:
            continue
        module_id = _catalog_module_id(db, item)
        if module_id is not None and placed[module_id] > 0:
            placed[module_id] -= 1
            continue
        left.append(
            ModuleToPlace(
                instance_id=item.instance_id,
                module_revision_id=item.module_revision_id,
                manufacturer=item.manufacturer,
                model=item.model,
                module_id=module_id,
            )
        )
    return left


def latest_confirmation_revision(db: Session, rack: Rack) -> SystemInventoryRevision | None:
    """The owner's newest photo confirmation, even if a generation sealed a revision since."""

    author = SystemInventoryRevisionRecord.created_by
    row = (
        db.query(SystemInventoryRevisionRecord.id)
        .filter(
            SystemInventoryRevisionRecord.rack_id == rack.id,
            or_(author.is_(None), ~author.startswith(PLACEMENT_REVISION_AUTHOR_PREFIX)),
        )
        .order_by(SystemInventoryRevisionRecord.created_at.desc())
        .first()
    )
    return load_system_inventory_revision(db, row.id) if row else None


def connection_module_ids(connections: Iterable[object]) -> set[int]:
    """Extract catalog module ids from Connection dataclasses or dicts."""

    ids: set[int] = set()
    for connection in connections:
        if isinstance(connection, dict):
            for key in ("from_module_id", "to_module_id"):
                value = connection.get(key)
                if value is not None:
                    ids.add(int(value))
        else:
            ids.add(int(connection.from_module_id))
            ids.add(int(connection.to_module_id))
    return ids


def filter_patches_to_confirmed_modules(
    patches: Sequence[object],
    allowed_module_ids: frozenset[int],
) -> tuple[list[object], int, tuple[str, ...]]:
    """Keep only patches whose every cable endpoint is on confirmed modules.

    Empty connection lists are retained (engine may emit sparse study patches).
    """

    kept: list[object] = []
    dropped = 0
    messages: list[str] = []
    for patch in patches:
        connections = getattr(patch, "connections", None)
        if connections is None and isinstance(patch, dict):
            connections = patch.get("connections") or []
        used = connection_module_ids(connections or [])
        if used and not used.issubset(allowed_module_ids):
            dropped += 1
            foreign = sorted(used - allowed_module_ids)
            messages.append(f"Dropped patch using modules outside confirmed inventory: {foreign}")
            continue
        kept.append(patch)
    return kept, dropped, tuple(messages)


def evaluate_rack_inventory_gate(
    db: Session,
    rack: Rack,
    *,
    patches: Sequence[object] | None = None,
    created_at: datetime | None = None,
) -> tuple[InventoryGateReport, list[object]]:
    """Build inventory, optionally filter patches, return report + kept patches."""

    inventory = build_manual_inventory_from_rack(db, rack, created_at=created_at)
    allowed = confirmed_catalog_module_ids(db, rack)
    ready = inventory_ready_for_generation(inventory) and bool(allowed)

    if not ready:
        report = InventoryGateReport(
            inventory=inventory,
            allowed_catalog_module_ids=allowed,
            ready=False,
            code="NOT_COMPUTABLE",
            messages=(
                "No USER_CONFIRMED modules in rack inventory; "
                "hardware-constrained generation is not computable.",
            ),
            dropped_patch_count=0,
        )
        return report, []

    if patches is None:
        report = InventoryGateReport(
            inventory=inventory,
            allowed_catalog_module_ids=allowed,
            ready=True,
            code="OK",
            messages=(),
            dropped_patch_count=0,
        )
        return report, []

    kept, dropped, messages = filter_patches_to_confirmed_modules(patches, allowed)
    code = "FILTERED" if dropped else "OK"
    report = InventoryGateReport(
        inventory=inventory,
        allowed_catalog_module_ids=allowed,
        ready=True,
        code=code,
        messages=messages,
        dropped_patch_count=dropped,
    )
    return report, kept
