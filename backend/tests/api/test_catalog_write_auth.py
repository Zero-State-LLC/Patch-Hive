"""
Module and case writes change shared reference data: they require an admin and are audited.
"""

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from admin.models import AdminAuditLog
from cases.models import Case
from community.models import User
from core.security import create_access_token
from main import app
from modules.models import Module

MODULE = {"brand": "Acme", "name": "Osc", "hp": 8, "module_type": "VCO", "io_ports": [], "tags": [], "source": "Manual"}
CASE = {"brand": "Acme", "name": "Box 104", "total_hp": 104, "rows": 1, "hp_per_row": [104], "source": "Manual"}


def _create_user(db_session: Session, username: str, role: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash="hash",
        referral_code=f"{username}code",
        role=role,
        display_name=username.title(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict:
    token = create_access_token({"user_id": user.id, "username": user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _module(db_session: Session) -> Module:
    module = Module(brand="Acme", name="Existing", hp=4, module_type="VCA", io_ports=[], tags=[], source="Manual")
    db_session.add(module)
    db_session.commit()
    return module


def _case(db_session: Session) -> Case:
    case = Case(brand="Acme", name="Old Box", total_hp=84, rows=1, hp_per_row=[84], source="Manual")
    db_session.add(case)
    db_session.commit()
    return case


def test_module_writes_need_a_token(client: TestClient, db_session: Session):
    module = _module(db_session)
    assert client.post("/api/modules/", json=MODULE).status_code == 401
    assert client.patch(f"/api/modules/{module.id}", json={"hp": 40}).status_code == 401
    assert client.delete(f"/api/modules/{module.id}").status_code == 401
    db_session.refresh(module)
    assert module.hp == 4 and module.status == "active"


def test_module_writes_need_an_admin(client: TestClient, db_session: Session):
    module = _module(db_session)
    headers = _auth_headers(_create_user(db_session, "plain", "User"))
    assert client.post("/api/modules/", json=MODULE, headers=headers).status_code == 403
    assert client.patch(f"/api/modules/{module.id}", json={"hp": 40}, headers=headers).status_code == 403
    assert client.delete(f"/api/modules/{module.id}", headers=headers).status_code == 403


def test_admin_module_writes_are_audited(client: TestClient, db_session: Session):
    module = _module(db_session)
    headers = _auth_headers(_create_user(db_session, "boss", "Admin"))
    assert client.post("/api/modules/", json=MODULE, headers=headers).status_code == 201
    assert client.patch(f"/api/modules/{module.id}", json={"hp": 6}, headers=headers).status_code == 200
    assert client.delete(f"/api/modules/{module.id}", headers=headers).status_code == 204
    actions = [row.action_type for row in db_session.query(AdminAuditLog).order_by(AdminAuditLog.id)]
    assert actions == ["module.create", "module.update", "module.tombstone"]
    update = db_session.query(AdminAuditLog).filter_by(action_type="module.update").one()
    assert update.delta_json == {"before": {"hp": 4}, "after": {"hp": 6}}


def test_reads_stay_public(client: TestClient, db_session: Session):
    _module(db_session)
    assert client.get("/api/modules/").status_code == 200
    assert client.get("/api/cases/").status_code == 200


def test_case_writes_need_an_admin(client: TestClient, db_session: Session):
    case = _case(db_session)
    assert client.post("/api/cases/", json=CASE).status_code == 401
    headers = _auth_headers(_create_user(db_session, "plain2", "User"))
    assert client.patch(f"/api/cases/{case.id}", json={"name": "x"}, headers=headers).status_code == 403
    assert client.delete(f"/api/cases/{case.id}", headers=headers).status_code == 403
    assert db_session.get(Case, case.id) is not None


def test_admin_case_writes_are_audited(client: TestClient, db_session: Session):
    case = _case(db_session)
    headers = _auth_headers(_create_user(db_session, "boss2", "Ops"))
    assert client.post("/api/cases/", json=CASE, headers=headers).status_code == 201
    assert client.patch(f"/api/cases/{case.id}", json={"name": "New Box"}, headers=headers).status_code == 200
    assert client.delete(f"/api/cases/{case.id}", headers=headers).status_code == 204
    actions = [row.action_type for row in db_session.query(AdminAuditLog).order_by(AdminAuditLog.id)]
    assert actions == ["case.create", "case.update", "case.delete"]
