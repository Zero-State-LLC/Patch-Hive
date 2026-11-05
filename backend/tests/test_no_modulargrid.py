from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import check_no_modulargrid as guard  # noqa: E402
from catalog_scrape import denied_host  # noqa: E402


def test_repo_head_has_no_modulargrid_data():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_no_modulargrid.py")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_guard_flags_extracts_and_fetch_code(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.json").write_text('{"u": "https://www.modulargrid.net/e/foo"}')
    (tmp_path / "s.py").write_text('URL = "https://modulargrid.net/e/" + slug\n')
    (tmp_path / "ok.py").write_text("# ModularGrid is never fetched\n")
    bad = guard.violations(["data/x.json", "s.py", "ok.py", "patchhive-replit.zip"])
    assert len(bad) == 3


def test_fetch_layer_denies_modulargrid():
    assert denied_host("https://www.modulargrid.net/e/x")
    assert denied_host("https://modulargrid.net/")
    assert not denied_host("https://www.doepfer.de/a100.htm")


def test_catalog_rows_never_expose_modulargrid_fields(db_session):
    from fastapi.testclient import TestClient

    from core import get_db
    from main import app
    from modules.catalog import ModuleCatalog

    row = ModuleCatalog(
        slug="acme-lead",
        brand="Acme",
        name="Lead",
        modulargrid_id=123,
        modulargrid_url="https://modulargrid.net/e/acme-lead",
        source="Manual",
        access_basis="official_publication",
    )
    db_session.add(row)
    db_session.commit()

    assert not [key for key in row.to_dict() if "modulargrid" in key]

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        body = TestClient(app).get("/api/modules/catalog", params={"limit": 50})
    finally:
        app.dependency_overrides.clear()
    assert body.status_code == 200
    assert "modulargrid" not in body.text.lower()


def test_module_rows_never_expose_a_modulargrid_reference(db_session):
    """Owner decision 52 covers the same URL when it sits in `source_reference`."""
    from fastapi.testclient import TestClient

    from core import get_db
    from main import app
    from modules.models import Module

    for name, reference in (
        ("Lead", "https://www.modulargrid.net/e/acme-lead"),
        ("Maker", "https://acme.example/maker"),
    ):
        db_session.add(
            Module(brand="Acme", name=name, hp=4, module_type="VCO", source="Manual", source_reference=reference)
        )
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        body = TestClient(app).get("/api/modules", params={"brand": "Acme"})
    finally:
        app.dependency_overrides.clear()
    assert body.status_code == 200
    assert "modulargrid" not in body.text.lower()
    assert {row["name"]: row["source_reference"] for row in body.json()["modules"]} == {
        "Lead": None,
        "Maker": "https://acme.example/maker",
    }
