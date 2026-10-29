"""Spec 001 T030/T031: generation runs the canonical compiler and emits a metrics packet."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from canon.contracts import RigMetricsPacket
from canon.models import (
    GeneratedPatchRecord,
    RigMetricsPacketRecord,
    StageReceiptRecord,
)
from canon.compiler import GENERATOR_VERSION
from export.patchbook.design.content_spine import (
    compile_orm_patch,
    seal_orm_patch_to_compilation,
)
from main import app
from patches.models import Patch
from racks.models import Rack
from tests.api.test_generate_bridge import _client

SCORES = (
    "modulation_budget",
    "routing_flex_score",
    "clock_coherence_score",
    "chaos_headroom",
    "learning_gradient_index",
    "performance_density_index",
)


def _generate(db_session: Session, rack: Rack, headers: dict) -> dict:
    client: TestClient = _client(db_session, headers)
    resp = client.post(f"/api/patches/generate/{rack.id}", json={})
    app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_compiler_output_is_stored_for_each_patch(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    body = _generate(db_session, sample_rack_basic, owner_headers)
    rows = (
        db_session.query(GeneratedPatchRecord)
        .filter(GeneratedPatchRecord.patch_library_id == f"library-{body['source_run_id']}")
        .order_by(GeneratedPatchRecord.position.asc())
        .all()
    )
    assert len(rows) == body["generated_count"] >= 1
    for row in rows:
        assert row.patch_plan["generator_version"] == GENERATOR_VERSION
        assert {s["phase"] for s in row.patch_plan["steps"]} == {
            "prep",
            "threshold",
            "peak",
            "release",
            "seal",
        }
        assert row.validation_report["generator_version"] == GENERATOR_VERSION
        assert row.variations
    names = {
        p.name
        for p in db_session.query(Patch).filter(Patch.run_id == body["run_id"]).all()
    }
    # The Patch Book keeps the patch's own name as the plan title.
    assert {row.patch_plan["title"] for row in rows} <= names

    receipts = (
        db_session.query(StageReceiptRecord)
        .filter(StageReceiptRecord.run_id == body["source_run_id"])
        .all()
    )
    assert len(receipts) == 3 * len(rows)
    assert {r.stage for r in receipts} == {"normalize", "generate", "validate"}


def test_compiler_agrees_with_the_adapter_on_graph_and_blocking_findings(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    body = _generate(db_session, sample_rack_basic, owner_headers)
    patches = db_session.query(Patch).filter(Patch.run_id == body["run_id"]).order_by(Patch.id).all()
    assert patches
    for position, patch in enumerate(patches):
        kwargs = dict(
            source_run_id=body["source_run_id"], source_rig_revision_id=body["rig_revision_id"]
        )
        compiled = compile_orm_patch(patch, **kwargs)
        adapter = seal_orm_patch_to_compilation(
            patch, rig_snapshot={}, position=position, **kwargs
        )
        assert [n.module_instance_id for n in compiled.patch_graph.nodes] == [
            n.module_instance_id for n in adapter.patch_graph.nodes
        ]
        assert [(e.source_port_id, e.target_port_id) for e in compiled.patch_graph.edges] == [
            (e.source_port_id, e.target_port_id) for e in adapter.patch_graph.edges
        ]
        # Both carry five phases; only the compiler's prep step carries a startup warning.
        assert {s.phase for s in compiled.patch_plan.steps} == {s.phase for s in adapter.patch_plan.steps}
        assert any(s.warning for s in compiled.patch_plan.steps if s.phase == "prep")
        assert not any(s.warning for s in adapter.patch_plan.steps)
        # The compiler adds the validate stage the adapter lacks.
        assert [r.stage for r in compiled.stage_receipts] == ["normalize", "generate", "validate"]
        assert [r.stage for r in adapter.stage_receipts] == ["design_engine"]
        # Compiling twice gives the same bytes.
        assert compiled.canonical_hash_value() == compile_orm_patch(patch, **kwargs).canonical_hash_value()


def test_rig_metrics_packet_has_counts_and_not_computable_scores(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    body = _generate(db_session, sample_rack_basic, owner_headers)
    record = (
        db_session.query(RigMetricsPacketRecord)
        .filter(RigMetricsPacketRecord.rig_revision_id == body["rig_revision_id"])
        .one()
    )
    packet = RigMetricsPacket.model_validate(record.packet)
    assert packet.canonical_hash == record.canonical_hash
    assert packet.rig_id == str(sample_rack_basic.id)
    assert packet.module_count > 0
    assert sum((packet.category_counts or {}).values()) == packet.module_count
    for name in SCORES:
        assert getattr(packet, name) == "NOT_COMPUTABLE", name


def test_second_run_on_same_revision_reuses_the_packet(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    first = _generate(db_session, sample_rack_basic, owner_headers)
    second = _generate(db_session, sample_rack_basic, owner_headers)
    assert first["rig_revision_id"] == second["rig_revision_id"]
    count = (
        db_session.query(RigMetricsPacketRecord)
        .filter(RigMetricsPacketRecord.rig_revision_id == first["rig_revision_id"])
        .count()
    )
    assert count == 1
