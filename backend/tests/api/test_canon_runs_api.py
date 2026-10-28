"""Canon run list alias (matrix slice B)."""

from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from community.models import User
from main import app
from racks.models import Rack
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


def test_canon_runs_alias_matches_legacy_list(db_session: Session) -> None:
    user = User(username="canon-run", email="canon-run@example.com", password_hash="h")
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
    # As generation does: record the canonical bridge when the run is made.
    from runs.bridge import ensure_legacy_run_export_bridge

    ensure_legacy_run_export_bridge(db_session, run)
    db_session.commit()

    client = _client(db_session)
    legacy = client.get(f"/api/runs?rack_id={rack.id}")
    canon = client.get(f"/api/canon/runs?rig_id={rack.id}")
    assert legacy.status_code == 200
    assert canon.status_code == 200
    assert legacy.json() == canon.json()
    assert canon.json()["runs"][0]["export_bridge_ready"] is True
    assert canon.json()["runs"][0]["source_run_id"].startswith("gen-run-")
    assert canon.json()["runs"][0]["rig_revision_id"].startswith("rig-rev-")
    app.dependency_overrides.clear()
