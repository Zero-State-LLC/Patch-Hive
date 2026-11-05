"""Confirmed-inventory gate for rack-backed patch generation."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from canon.visual_contracts import InventoryItem, ResolutionStatus, SystemInventoryRevision
from modules.models import Module
from patches.engine import generate_patches_with_ir
from patches.inventory_gate import (
    build_manual_inventory_from_rack,
    evaluate_rack_inventory_gate,
    filter_patches_to_confirmed_modules,
    modules_still_to_place,
)
from racks.models import Rack


def test_manual_inventory_from_rack_marks_modules_confirmed(
    db_session: Session, sample_rack_basic: Rack
) -> None:
    inventory = build_manual_inventory_from_rack(db_session, sample_rack_basic)
    assert inventory.canonical_hash == inventory.computed_hash()
    assert inventory.items
    assert all(item.resolution.value == "USER_CONFIRMED" for item in inventory.items)
    assert inventory.system_id == f"rack-{sample_rack_basic.id}"


def test_empty_rack_inventory_not_computable(db_session: Session, sample_rack_empty: Rack) -> None:
    report, patches = evaluate_rack_inventory_gate(db_session, sample_rack_empty)
    assert report.ready is False
    assert report.code == "NOT_COMPUTABLE"
    assert patches == []


def test_filter_drops_foreign_module_connections(
    db_session: Session, sample_rack_basic: Rack
) -> None:
    report, _ = evaluate_rack_inventory_gate(db_session, sample_rack_basic)
    allowed = report.allowed_catalog_module_ids
    assert allowed
    known = next(iter(allowed))
    foreign_id = max(allowed) + 9999

    class _Conn:
        def __init__(self, from_module_id: int, to_module_id: int) -> None:
            self.from_module_id = from_module_id
            self.to_module_id = to_module_id

    class _Patch:
        def __init__(self, connections: list[_Conn]) -> None:
            self.connections = connections
            self.name = "x"

    good = _Patch([_Conn(known, known)])
    bad = _Patch([_Conn(known, foreign_id)])
    kept, dropped, messages = filter_patches_to_confirmed_modules([good, bad], allowed)
    assert dropped == 1
    assert len(kept) == 1
    assert messages


def test_generate_with_ir_records_inventory_gate(
    db_session: Session, sample_rack_basic: Rack
) -> None:
    _ir, graphs, provenance = generate_patches_with_ir(db_session, sample_rack_basic, seed=42)
    metrics = provenance.to_dict()["metrics"]
    assert "inventory_gate" in metrics
    assert metrics["inventory_gate"]["ready"] is True
    assert metrics.get("inventory_revision_id") or metrics["inventory_gate"].get(
        "inventory_revision_id"
    )
    assert metrics.get("generation_status") in {"OK", "FILTERED"}
    report, _ = evaluate_rack_inventory_gate(db_session, sample_rack_basic)
    for graph in graphs:
        for conn in graph.connections:
            assert conn.from_module_id in report.allowed_catalog_module_ids
            assert conn.to_module_id in report.allowed_catalog_module_ids


def test_generate_empty_rack_is_not_computable(
    db_session: Session, sample_rack_empty: Rack
) -> None:
    _ir, graphs, provenance = generate_patches_with_ir(db_session, sample_rack_empty, seed=42)
    assert graphs == []
    metrics = provenance.to_dict()["metrics"]
    assert metrics["generation_status"] == "NOT_COMPUTABLE"
    assert metrics["inventory_gate"]["code"] == "NOT_COMPUTABLE"


def _photo_item(index: int, **fields) -> InventoryItem:
    return InventoryItem(
        instance_id=f"inst-{index}",
        resolution=ResolutionStatus.USER_CONFIRMED,
        source_candidate_ids=(f"cand-{index}",),
        **fields,
    )


def _photo_inventory(*items: InventoryItem) -> SystemInventoryRevision:
    return SystemInventoryRevision(
        inventory_revision_id="inv-rev-test",
        system_id="rack-test",
        items=items,
        created_at=datetime.now(timezone.utc),
    )


def test_to_place_reads_the_catalog_id_label_and_counts_each_copy(
    db_session: Session, sample_rack_basic: Rack, sample_vco: Module
) -> None:
    """Two confirmed copies, one placed: one is still to place."""
    label = f"catalog-module-{sample_vco.id}"
    inventory = _photo_inventory(
        _photo_item(1, module_revision_id=label), _photo_item(2, module_revision_id=label)
    )
    left = modules_still_to_place(db_session, sample_rack_basic, inventory)
    assert [(entry.instance_id, entry.module_id) for entry in left] == [("inst-2", sample_vco.id)]


def test_to_place_matches_an_exact_brand_and_name_only(
    db_session: Session, sample_rack_empty: Rack, sample_vco: Module
) -> None:
    inventory = _photo_inventory(
        _photo_item(
            1,
            module_revision_id="catalog-cand-1",
            manufacturer=sample_vco.brand.upper(),
            model=sample_vco.name,
        ),
        _photo_item(
            2,
            module_revision_id="catalog-cand-2",
            manufacturer=sample_vco.brand,
            model=f"{sample_vco.name} Mk2",
        ),
    )
    left = modules_still_to_place(db_session, sample_rack_empty, inventory)
    assert [entry.module_id for entry in left] == [sample_vco.id, None]


def test_to_place_does_not_pick_between_two_catalog_rows_of_one_name(
    db_session: Session, sample_rack_empty: Rack, sample_vco: Module
) -> None:
    twin = Module(
        brand=sample_vco.brand,
        name=sample_vco.name,
        hp=sample_vco.hp,
        module_type=sample_vco.module_type,
        io_ports=[],
        source="test",
    )
    db_session.add(twin)
    db_session.commit()
    inventory = _photo_inventory(
        _photo_item(
            1,
            module_revision_id="catalog-cand-1",
            manufacturer=sample_vco.brand,
            model=sample_vco.name,
        )
    )
    left = modules_still_to_place(db_session, sample_rack_empty, inventory)
    assert [entry.module_id for entry in left] == [None]


def test_to_place_ignores_placement_and_unconfirmed_items(
    db_session: Session, sample_rack_basic: Rack
) -> None:
    """A placement revision's rows are the rack itself, and only USER_CONFIRMED counts."""
    placement = build_manual_inventory_from_rack(db_session, sample_rack_basic)
    assert modules_still_to_place(db_session, sample_rack_basic, placement) == []
    observed = _photo_inventory(
        InventoryItem(
            instance_id="inst-observed",
            module_revision_id="catalog-cand-observed",
            resolution=ResolutionStatus.OBSERVED,
            source_candidate_ids=("cand-observed",),
        )
    )
    assert modules_still_to_place(db_session, sample_rack_basic, observed) == []
