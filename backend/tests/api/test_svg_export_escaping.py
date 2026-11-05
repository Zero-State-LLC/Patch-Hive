"""User-entered names can't become markup in SVG served from the API origin."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from main import app
from modules.models import Module
from patches.models import Patch
from racks.models import Rack, RackModule

SCRIPT = "<script>alert(1)</script>"
BREAKOUT = '--><svg onload="alert(1)">'


@pytest.fixture
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def hostile_rack(db_session: Session) -> Rack:
    case = Case(
        brand=SCRIPT, name=BREAKOUT, total_hp=84, rows=1, hp_per_row=[84],
        power_12v_ma=1000, power_neg12v_ma=1000, power_5v_ma=0, source="test",
    )
    module = Module(
        brand=SCRIPT, name=BREAKOUT, hp=8, module_type=SCRIPT,
        power_12v_ma=10, power_neg12v_ma=10, power_5v_ma=0, io_ports=[], tags=[], source="test",
    )
    db_session.add_all([case, module])
    db_session.flush()
    rack = Rack(user_id=1, case_id=case.id, name=SCRIPT, tags=[], is_public=True)
    db_session.add(rack)
    db_session.flush()
    db_session.add(RackModule(rack_id=rack.id, module_id=module.id, row_index=0, start_hp=0))
    db_session.commit()
    return rack


def _assert_inert(text: str) -> None:
    root = ET.fromstring(text)
    tags = {element.tag.rsplit("}", 1)[-1] for element in root.iter()}
    assert "script" not in tags
    assert all("onload" not in element.attrib for element in root.iter())
    assert sum(1 for element in root.iter() if element.tag.endswith("svg")) == 1


def test_rack_layout_svg_escapes_names_and_blocks_scripts(
    client: TestClient, hostile_rack: Rack
) -> None:
    resp = client.get(f"/api/export/racks/{hostile_rack.id}/layout.svg")
    assert resp.status_code == 200
    _assert_inert(resp.text)
    assert "&lt;script&gt;" in resp.text
    policy = resp.headers["content-security-policy"]
    assert "default-src 'none'" in policy
    assert "sandbox" in policy


def test_patch_diagram_svg_escapes_names_and_blocks_scripts(
    client: TestClient, db_session: Session, hostile_rack: Rack
) -> None:
    patch = Patch(
        rack_id=hostile_rack.id, name="P", category="Voice", connections=[], generation_seed=1,
        generation_version="1.0.0", engine_config={}, is_public=True,
    )
    db_session.add(patch)
    db_session.commit()
    resp = client.get(f"/api/export/patches/{patch.id}/diagram.svg")
    assert resp.status_code == 200
    _assert_inert(resp.text)
    assert "sandbox" in resp.headers["content-security-policy"]


def test_a_failed_svg_keeps_exception_text_out_of_the_response(
    client: TestClient, hostile_rack: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    detail = "postgresql://ops:hunter2@db.internal/patchhive"

    def fail(*_args, **_kwargs):
        raise RuntimeError(detail)

    monkeypatch.setattr("export.routes.generate_rack_layout_svg", fail)
    resp = client.get(f"/api/export/racks/{hostile_rack.id}/layout.svg")
    assert resp.status_code == 500
    assert detail not in resp.text
