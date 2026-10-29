"""F3 / slice A: generate dual-writes native bridge + inventory (no legacy-* invent),
and follows the spec 001 run lifecycle."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from canon.models import (
    GeneratedPatchRecord,
    GenerationRunRecord,
    PatchLibraryRecord,
    RigRevisionRecord,
    SystemInventoryRevisionRecord,
)
from main import app
from patches.models import Patch
from racks.models import Rack
from runs.bridge import native_source_run_id, rack_content_hash, build_rack_content_snapshot
from runs.models import Run


def _client(db_session: Session, headers: dict | None = None) -> TestClient:
    from core import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app, headers=headers or {})


def _assert_no_legacy_ids(body: dict) -> None:
    for key in ("source_run_id", "rig_revision_id"):
        value = body.get(key) or ""
        assert not str(value).startswith("legacy-"), f"{key} must not be legacy-* ({value})"
    assert str(body.get("source_run_id", "")).startswith("gen-run-")
    assert str(body.get("rig_revision_id", "")).startswith("rig-rev-")


def test_generate_patches_ensures_export_bridge(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    client = _client(db_session, owner_headers)
    resp = client.post(f"/api/patches/generate/{sample_rack_basic.id}", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["run_id"] is not None
    assert body["export_bridge_ready"] is True
    _assert_no_legacy_ids(body)
    snap = build_rack_content_snapshot(db_session, sample_rack_basic)
    content = rack_content_hash(snap)
    assert body["source_run_id"] == native_source_run_id(int(body["run_id"]), content)
    assert body["artifact_manifest_hash"] and len(body["artifact_manifest_hash"]) == 64
    assert body.get("inventory_revision_id")
    assert str(body["inventory_revision_id"]).startswith("inv-rev-")
    assert body.get("inventory_gate_code") in {"OK", "FILTERED"}
    assert body.get("generation_status") in {"OK", "FILTERED"}
    assert body["generated_count"] >= 1

    assert db_session.get(RigRevisionRecord, body["rig_revision_id"]) is not None
    rev = db_session.get(RigRevisionRecord, body["rig_revision_id"])
    assert rev is not None
    assert rev.canonical_rig.get("schema") == "patchhive.rack-snapshot.v1"
    assert rev.canonical_rig.get("bridge") == "native"
    assert isinstance(rev.canonical_rig.get("modules"), list)
    assert len(str(rev.canonical_hash)) == 64
    assert db_session.get(GenerationRunRecord, body["source_run_id"]) is not None
    library = db_session.get(PatchLibraryRecord, f"library-{body['source_run_id']}")
    assert library is not None
    inv = db_session.get(SystemInventoryRevisionRecord, body["inventory_revision_id"])
    assert inv is not None
    assert inv.rack_id == sample_rack_basic.id

    # Path A dual-write: sealed GeneratedPatchRecord rows for Design Engine spine
    sealed = (
        db_session.query(GeneratedPatchRecord)
        .filter(GeneratedPatchRecord.patch_library_id == library.id)
        .order_by(GeneratedPatchRecord.position.asc())
        .all()
    )
    assert len(sealed) == body["generated_count"]
    assert sealed[0].patch_graph and sealed[0].patch_plan
    assert len(str(sealed[0].canonical_hash)) == 64
    # library row remains append-only; integrity is on GeneratedPatchRecord hashes
    assert len(str(library.canonical_hash)) == 64

    # List runs still ready without additional invent
    listed = client.get(f"/api/runs?rack_id={sample_rack_basic.id}")
    assert listed.status_code == 200
    run_row = next(r for r in listed.json()["runs"] if r["id"] == body["run_id"])
    assert run_row["export_bridge_ready"] is True
    assert run_row["source_run_id"] == body["source_run_id"]
    _assert_no_legacy_ids(run_row)

    app.dependency_overrides.clear()


def test_generate_empty_rack_not_computable_writes_no_run(
    db_session: Session, sample_rack_empty: Rack, owner_headers: dict
) -> None:
    """Spec 001 FR-022: an empty inventory answers NOT_COMPUTABLE and writes no run.

    Only the inventory revision is kept, as the record of what was checked.
    """
    client = _client(db_session, owner_headers)
    runs_before = db_session.query(Run).count()
    canon_runs_before = db_session.query(GenerationRunRecord).count()
    resp = client.post(f"/api/patches/generate/{sample_rack_empty.id}", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["generated_count"] == 0
    assert body.get("generation_status") == "NOT_COMPUTABLE"
    assert body.get("inventory_gate_code") == "NOT_COMPUTABLE"
    assert body["run_id"] is None
    assert body["export_bridge_ready"] is False
    assert db_session.query(Run).count() == runs_before
    assert db_session.query(GenerationRunRecord).count() == canon_runs_before
    assert db_session.get(SystemInventoryRevisionRecord, body["inventory_revision_id"]) is not None
    app.dependency_overrides.clear()


def test_generate_records_the_run_lifecycle_and_real_provenance(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    """FR-018: a run ends succeeded; FR-024/FR-026: the canonical run keeps the
    request seed and the engine version, not the run id and a fixed version."""
    from core import settings

    client = _client(db_session, owner_headers)
    resp = client.post(f"/api/patches/generate/{sample_rack_basic.id}", json={"seed": 4242})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert db_session.get(Run, body["run_id"]).status == "succeeded"
    record = db_session.get(GenerationRunRecord, body["source_run_id"])
    assert record.generation_seed == 4242
    assert record.generator_version == settings.patch_engine_version
    app.dependency_overrides.clear()


def test_a_generation_error_leaves_the_run_failed(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict, monkeypatch
) -> None:
    import patches.routes as routes

    def boom(*args, **kwargs):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(routes, "generate_patches_with_ir", boom)
    _client(db_session, owner_headers)  # binds the session
    client_no_raise = TestClient(app, raise_server_exceptions=False, headers=owner_headers)
    resp = client_no_raise.post(f"/api/patches/generate/{sample_rack_basic.id}", json={})
    assert resp.status_code == 500
    run = db_session.query(Run).order_by(Run.id.desc()).first()
    assert run is not None and run.status == "failed"
    assert db_session.query(Patch).filter(Patch.run_id == run.id).count() == 0
    app.dependency_overrides.clear()


def test_generate_twice_does_not_invent_new_rig_rev_for_same_layout(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    """Same layout snapshot → same rig-rev-* id across runs (append-only revisions)."""
    client = _client(db_session, owner_headers)
    first = client.post(f"/api/patches/generate/{sample_rack_basic.id}", json={}).json()
    second = client.post(f"/api/patches/generate/{sample_rack_basic.id}", json={}).json()
    assert first["rig_revision_id"] == second["rig_revision_id"]
    assert first["source_run_id"] != second["source_run_id"]  # distinct gen-run per integer run
    _assert_no_legacy_ids(first)
    _assert_no_legacy_ids(second)
    # Inventory id stable for same placement set
    assert first["inventory_revision_id"] == second["inventory_revision_id"]
    app.dependency_overrides.clear()


def test_a_blocking_finding_fails_the_run_and_saves_nothing(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict, monkeypatch
) -> None:
    """FR-016/FR-019: a contradiction ends the run validation_failed with no patches."""
    import patches.validation as validation

    def blocked(patch_graphs, modules_by_id, allowed_module_ids=None):
        report = validation.ValidationReport()
        report.add(validation.Finding("block", "PORT_DIRECTION_MISMATCH", "test", 0))
        return list(patch_graphs), report

    monkeypatch.setattr(validation, "resolve_and_validate", blocked)
    client = _client(db_session, owner_headers)
    resp = client.post(f"/api/patches/generate/{sample_rack_basic.id}", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["generation_status"] == "VALIDATION_FAILED"
    assert body["generated_count"] == 0
    assert body["validation"]["blocking"] is True
    run = db_session.get(Run, body["run_id"])
    assert run.status == "validation_failed"
    assert db_session.query(Patch).filter(Patch.run_id == body["run_id"]).count() == 0
    # The reason survives the response, and the failed run has no export-ready library.
    assert run.validation_report["blocking"] is True
    assert db_session.get(PatchLibraryRecord, f"library-{body['source_run_id']}") is None
    again = client.get(f"/api/runs/{body['run_id']}").json()
    assert again["export_bridge_ready"] is False
    assert again["validation"]["findings"][0]["code"] == "PORT_DIRECTION_MISMATCH"
    app.dependency_overrides.clear()


def test_patches_outside_the_inventory_fail_the_run(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict, monkeypatch
) -> None:
    """A patch the inventory filter has to drop is a contradiction (OQ-08)."""
    import patches.inventory_gate as gate

    real = gate.filter_patches_to_confirmed_modules

    def drop_one(patches, allowed):
        kept, dropped, messages = real(patches, allowed)
        return kept[1:], dropped + 1, messages

    monkeypatch.setattr(gate, "filter_patches_to_confirmed_modules", drop_one)
    client = _client(db_session, owner_headers)
    body = client.post(f"/api/patches/generate/{sample_rack_basic.id}", json={}).json()
    assert body["generation_status"] == "VALIDATION_FAILED"
    codes = [f["code"] for f in body["validation"]["findings"] if f["severity"] == "block"]
    assert codes == ["MODULE_NOT_IN_INVENTORY"]
    app.dependency_overrides.clear()


def test_a_passing_run_keeps_its_report_and_is_export_ready(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    client = _client(db_session, owner_headers)
    body = client.post(f"/api/patches/generate/{sample_rack_basic.id}", json={}).json()
    assert body["export_bridge_ready"] is True
    run = client.get(f"/api/runs/{body['run_id']}").json()
    assert run["export_bridge_ready"] is True
    assert run["validation"]["blocking"] is False
    app.dependency_overrides.clear()


def test_a_run_that_fails_after_generation_ends_failed(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict, monkeypatch
) -> None:
    """Spec 001 FR-018/FR-019: an error in the dual-write never leaves a run `running`."""
    import export.patchbook.design.dual_write as dual_write

    def boom(*args, **kwargs):
        raise RuntimeError("dual-write down")

    monkeypatch.setattr(dual_write, "dual_write_generated_patches", boom)
    client = _client(db_session, owner_headers)
    try:
        client.post(f"/api/patches/generate/{sample_rack_basic.id}", json={})
    except RuntimeError:
        pass  # TestClient re-raises server errors
    runs = db_session.query(Run).filter(Run.rack_id == sample_rack_basic.id).all()
    assert [r.status for r in runs] == ["failed"]
    assert db_session.query(Patch).filter(Patch.rack_id == sample_rack_basic.id).count() == 0


def test_admin_rerun_goes_through_the_generation_path(
    db_session: Session, sample_rack_basic: Rack
) -> None:
    """A rerun passes the readiness gate and ends terminal; nothing is left queued."""
    from tests.conftest import bearer_headers, make_user

    admin = make_user(db_session, "rerun-admin", role="Admin")
    client = _client(db_session, bearer_headers(admin))
    resp = client.post(f"/api/admin/runs/{sample_rack_basic.id}/rerun")
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "succeeded"
    statuses = {r.status for r in db_session.query(Run).filter(Run.rack_id == sample_rack_basic.id)}
    assert "queued" not in statuses and "running" not in statuses


def test_admin_rerun_refuses_a_rig_the_gate_cannot_compute(
    db_session: Session, sample_case
) -> None:
    from tests.conftest import bearer_headers, make_user

    admin = make_user(db_session, "rerun-admin-2", role="Admin")
    empty = Rack(user_id=admin.id, name="Empty", case_id=sample_case.id)
    db_session.add(empty)
    db_session.commit()
    client = _client(db_session, bearer_headers(admin))
    resp = client.post(f"/api/admin/runs/{empty.id}/rerun")
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "RIG_NOT_COMPUTABLE"
    assert db_session.query(Run).filter(Run.rack_id == empty.id).count() == 0
    assert client.post("/api/admin/runs/999999/rerun").status_code == 404
