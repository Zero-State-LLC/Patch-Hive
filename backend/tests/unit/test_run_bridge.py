"""Unit tests for native run export bridge id/hash helpers + rack content snapshot."""

from __future__ import annotations

from sqlalchemy.orm import Session

from canon.models import RigRevisionRecord
from modules.models import Module
from racks.models import Rack, RackModule
from runs.bridge import (
    build_rack_content_snapshot,
    ensure_legacy_run_export_bridge,
    legacy_artifact_manifest_hash,
    legacy_rig_revision_id,
    legacy_source_run_id,
    native_artifact_manifest_hash,
    native_rig_revision_id,
    native_source_run_id,
    rack_content_hash,
)
from runs.models import Run


def test_legacy_helpers_still_stable_for_migration_parity() -> None:
    assert legacy_rig_revision_id(7) == "legacy-rack-7"
    assert legacy_source_run_id(12) == "legacy-run-12"
    assert len(legacy_artifact_manifest_hash(12, 7)) == 64


def test_native_ids_are_content_bound() -> None:
    content = "a" * 64
    assert native_rig_revision_id(content) == f"rig-rev-{content[:32]}"
    assert native_source_run_id(12, content) == f"gen-run-12-{content[:16]}"
    assert len(native_artifact_manifest_hash(12, 7, content)) == 64
    assert native_artifact_manifest_hash(12, 7, content) != legacy_artifact_manifest_hash(
        12, 7, content
    )


def test_content_bound_manifest_differs_from_historical() -> None:
    historical = legacy_artifact_manifest_hash(12, 7)
    content = legacy_artifact_manifest_hash(12, 7, content_hash="abc")
    assert historical != content
    assert len(content) == 64


def test_rack_snapshot_hash_changes_with_layout(
    db_session: Session,
    sample_rack_basic: Rack,
    sample_effect: Module,
) -> None:
    snap1 = build_rack_content_snapshot(db_session, sample_rack_basic)
    h1 = rack_content_hash(snap1)
    assert snap1["schema"] == "patchhive.rack-snapshot.v1"
    assert snap1["bridge"] == "native"
    assert len(snap1["modules"]) >= 1

    db_session.add(
        RackModule(
            rack_id=sample_rack_basic.id,
            module_id=sample_effect.id,
            row_index=1,
            start_hp=0,
        )
    )
    db_session.commit()

    snap2 = build_rack_content_snapshot(db_session, sample_rack_basic)
    h2 = rack_content_hash(snap2)
    assert h1 != h2

    run = Run(rack_id=sample_rack_basic.id, status="completed")
    db_session.add(run)
    db_session.commit()

    bridge = ensure_legacy_run_export_bridge(db_session, run)
    db_session.commit()
    rev = db_session.get(RigRevisionRecord, bridge.rig_revision_id)
    assert rev is not None
    assert str(rev.canonical_hash) == h2
    assert bridge.content_hash == h2
    assert bridge.rig_revision_id == native_rig_revision_id(h2)
    assert bridge.source_run_id == native_source_run_id(bridge.run_id, h2)
    assert bridge.source_run_id.startswith("gen-run-")
    assert bridge.rig_revision_id.startswith("rig-rev-")
    assert len(bridge.artifact_manifest_hash) == 64
    assert bridge.artifact_manifest_hash != legacy_artifact_manifest_hash(
        bridge.run_id, bridge.rack_id
    )


def test_layout_change_mints_new_immutable_revision(
    db_session: Session,
    sample_rack_basic: Rack,
    sample_effect: Module,
) -> None:
    run = Run(rack_id=sample_rack_basic.id, status="completed")
    db_session.add(run)
    db_session.commit()
    bridge1 = ensure_legacy_run_export_bridge(db_session, run)
    db_session.commit()
    first_rev_id = bridge1.rig_revision_id

    db_session.add(
        RackModule(
            rack_id=sample_rack_basic.id,
            module_id=sample_effect.id,
            row_index=2,
            start_hp=0,
        )
    )
    db_session.commit()

    bridge2 = ensure_legacy_run_export_bridge(db_session, run)
    db_session.commit()
    assert bridge2.rig_revision_id != first_rev_id
    assert db_session.get(RigRevisionRecord, first_rev_id) is not None
    assert db_session.get(RigRevisionRecord, bridge2.rig_revision_id) is not None


def test_a_rig_with_no_case_snapshots_its_case_as_none(
    db_session: Session, sample_user, sample_vco: Module
) -> None:
    rack = Rack(user_id=sample_user.id, case_id=None, name="From a photo", tags=[])
    db_session.add(rack)
    db_session.flush()
    db_session.add(RackModule(rack_id=rack.id, module_id=sample_vco.id, row_index=0, start_hp=0))
    db_session.commit()

    snapshot = build_rack_content_snapshot(db_session, rack)

    assert snapshot["case_id"] is None
    assert snapshot["modules"] == [{"module_id": sample_vco.id, "row_index": 0, "start_hp": 0}]
    assert len(rack_content_hash(snapshot)) == 64
