"""API tests for run list bridge fields."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from canon.models import GenerationRunRecord, PatchLibraryRecord, RigRevisionRecord
from community.models import User
from main import app
from racks.models import Rack
from runs.bridge import (
    build_rack_content_snapshot,
    ensure_legacy_run_export_bridge,
    native_artifact_manifest_hash,
    native_rig_revision_id,
    native_source_run_id,
    rack_content_hash,
)
from runs.models import Run


def _client(db_session: Session) -> TestClient:
    from core import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from tests.conftest import bearer_headers, make_user

    # Read-only checks over racks owned by other users: sign in as a read-all admin role.
    return TestClient(app, headers=bearer_headers(make_user(db_session, "auditor", "ReadOnly")))


def _seed_run(db_session: Session, *, bridged: bool = True) -> Run:
    """A run as generation leaves it: with its canonical bridge recorded."""
    user = User(username="run-user", email="run@example.com", password_hash="hash")
    case = Case(
        brand="PatchHive",
        name="Case",
        total_hp=84,
        rows=1,
        hp_per_row=[84],
        source="test",
    )
    db_session.add_all((user, case))
    db_session.flush()
    rack = Rack(user_id=user.id, case_id=case.id, name="Rig")
    db_session.add(rack)
    db_session.flush()
    run = Run(rack_id=rack.id, status="succeeded", created_at=datetime.utcnow())
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    if bridged:
        ensure_legacy_run_export_bridge(db_session, run)
        db_session.commit()
    return run


def test_list_runs_returns_the_recorded_export_bridge(db_session: Session) -> None:
    client = _client(db_session)
    run = _seed_run(db_session)
    rack = db_session.get(Rack, run.rack_id)
    assert rack is not None
    content_hash = rack_content_hash(build_rack_content_snapshot(db_session, rack))
    expected_manifest = native_artifact_manifest_hash(
        int(run.id), int(run.rack_id), content_hash=content_hash
    )

    resp = client.get(f"/api/runs?rack_id={run.rack_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    row = body["runs"][0]
    assert row["id"] == run.id
    assert row["rack_id"] == run.rack_id
    assert row["rig_revision_id"] == native_rig_revision_id(content_hash)
    assert row["source_run_id"] == native_source_run_id(int(run.id), content_hash)
    assert row["artifact_manifest_hash"] == expected_manifest
    assert row["export_bridge_ready"] is True
    assert len(row["artifact_manifest_hash"]) == 64
    assert row.get("created_at")

    rev = db_session.get(RigRevisionRecord, row["rig_revision_id"])
    assert rev is not None
    assert str(rev.canonical_hash) == content_hash
    assert rev.canonical_rig.get("schema") == "patchhive.rack-snapshot.v1"
    assert rev.canonical_rig.get("bridge") == "native"
    assert db_session.get(GenerationRunRecord, row["source_run_id"]) is not None
    assert db_session.get(PatchLibraryRecord, f"library-{row['source_run_id']}") is not None

    # Idempotent second list
    resp2 = client.get(f"/api/runs?rack_id={run.rack_id}")
    assert resp2.status_code == 200
    assert resp2.json()["runs"][0]["source_run_id"] == row["source_run_id"]
    assert resp2.json()["runs"][0]["artifact_manifest_hash"] == expected_manifest

    app.dependency_overrides.clear()


def test_get_run_bridge_matches_list(db_session: Session) -> None:
    client = _client(db_session)
    run = _seed_run(db_session)
    listed = client.get(f"/api/runs?rack_id={run.rack_id}").json()["runs"][0]
    got = client.get(f"/api/runs/{run.id}")
    assert got.status_code == 200
    body = got.json()
    assert body["source_run_id"] == listed["source_run_id"]
    assert body["rig_revision_id"] == listed["rig_revision_id"]
    assert body["artifact_manifest_hash"] == listed["artifact_manifest_hash"]
    app.dependency_overrides.clear()


def test_reading_runs_writes_nothing(db_session: Session) -> None:
    """Spec 001 FR-020: reads never mint canon rows, and a later layout change
    never re-binds an old run to a new rig revision."""
    from racks.models import RackModule

    client = _client(db_session)
    unbridged = _seed_run(db_session, bridged=False)

    def counts() -> tuple[int, int, int]:
        return (
            db_session.query(RigRevisionRecord).count(),
            db_session.query(GenerationRunRecord).count(),
            db_session.query(PatchLibraryRecord).count(),
        )

    before = counts()
    row = client.get(f"/api/runs/{unbridged.id}").json()
    assert row["export_bridge_ready"] is False
    assert client.get(f"/api/runs?rack_id={unbridged.rack_id}").status_code == 200
    assert counts() == before

    # A bridged run keeps its recorded revision after the layout changes.
    ensure_legacy_run_export_bridge(db_session, unbridged)
    db_session.commit()
    recorded = client.get(f"/api/runs/{unbridged.id}").json()
    db_session.add(RackModule(rack_id=unbridged.rack_id, module_id=999, row_index=0, start_hp=0))
    db_session.commit()
    after = counts()
    again = client.get(f"/api/runs/{unbridged.id}").json()
    assert again["rig_revision_id"] == recorded["rig_revision_id"]
    assert again["source_run_id"] == recorded["source_run_id"]
    assert counts() == after
    app.dependency_overrides.clear()
