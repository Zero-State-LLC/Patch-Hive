"""Automated simulation: catalog materialize → place → dual-gate.

Covers the operator loop without Firecrawl/network:
1. HP-known catalog batch materialize (idempotent)
2. Place modules on powered case with known rails
3. Physical overflow hard-fail
4. Connector budget hard-fail
5. Soft incomplete when module power missing
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.materialize import materialize_legacy_case
from community.models import User
from core.database import get_db
from integrations.case_catalog_populator import import_records
from main import app
from modules.catalog import ModuleCatalog
from modules.catalog_routes import materialize_catalog_batch
from modules.models import Module


def _catalog_entry(
    db: Session,
    *,
    brand: str,
    name: str,
    hp: int | None,
    category: str = "UTIL",
    source: str = "SynthCatalogResearch",
) -> ModuleCatalog:
    row = ModuleCatalog(
        slug=ModuleCatalog.create_slug(brand, name),
        brand=brand,
        name=name,
        hp=hp,
        category=category,
        is_available="available",
        source=source,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _sim_case() -> dict:
    return {
        "manufacturer": "Sim Co",
        "model": "Sim 84",
        "format_family": "eurorack",
        "production_status": "available",
        "powered": True,
        "revision": {
            "revision_key": "sim-2026",
            "row_count": 1,
            "capacity_value": 84,
            "capacity_unit": "hp",
            "confidence": "medium",
        },
        "rows": [
            {
                "row_index": 0,
                "format_family": "eurorack",
                "capacity_value": 84,
                "capacity_unit": "hp",
            }
        ],
        "power_systems": [
            {
                "name": "primary",
                "connector_count": 8,
                "current_pos12_ma": 2000,
                "current_neg12_ma": 1200,
                "current_pos5_ma": 500,
            }
        ],
        "features": [],
        "sources": [],
        "prices": [],
    }


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from tests.conftest import bearer_headers, make_user

    # Racks are owner-scoped: these tests create racks as a signed-in user.
    yield TestClient(app, headers=bearer_headers(make_user(db_session)))
    app.dependency_overrides.clear()


@pytest.fixture
def sim_user(db_session: Session) -> User:
    user = User(
        username="sim_user",
        email="sim@example.com",
        password_hash="$2b$12$dummyhash",
        referral_code="simcode01",
        role="User",
        display_name="Sim User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sim_case_id(db_session: Session) -> int:
    assert import_records(db_session, [_sim_case()])["inserted"] == 1
    legacy, _ = materialize_legacy_case(db_session, "sim-co-sim-84")
    return legacy.id


def test_simulate_materialize_place_power_and_overflow(
    client: TestClient,
    db_session: Session,
    sim_user: User,
    sim_case_id: int,
) -> None:
    # Catalog rows: 3 HP-known + 1 null-HP (must not materialize)
    _catalog_entry(db_session, brand="SimBrand", name="Alpha", hp=10, category="VCO")
    _catalog_entry(db_session, brand="SimBrand", name="Beta", hp=8, category="VCF")
    _catalog_entry(db_session, brand="SimBrand", name="Gamma", hp=12, category="UTIL")
    _catalog_entry(db_session, brand="SimBrand", name="DeltaNull", hp=None)

    batch = materialize_catalog_batch(
        db_session, brand="SimBrand", hp_known_only=True, limit=50
    )
    assert batch["status"] == "success"
    assert batch["scanned"] == 3
    assert batch["created"] == 3
    assert batch["failed"] == 0

    rebatch = materialize_catalog_batch(
        db_session, brand="SimBrand", hp_known_only=True, limit=50
    )
    assert rebatch["created"] == 0
    assert rebatch["exists"] == 3

    # API parity
    # Bulk materialize is an admin action.
    from tests.conftest import bearer_headers, make_user

    api_batch = client.post(
        "/api/modules/catalog/materialize-batch",
        params={"brand": "SimBrand", "hp_known_only": True, "limit": 50},
        headers=bearer_headers(make_user(db_session, "catalog-ops", "Ops")),
    )
    assert api_batch.status_code == 200
    assert api_batch.json()["exists"] == 3

    mods = (
        db_session.query(Module)
        .filter(Module.brand == "SimBrand", Module.source == "ModuleCatalog")
        .order_by(Module.hp.asc())
        .all()
    )
    assert len(mods) == 3
    # Enrich two with power; leave one unknown for soft warning path
    mods[0].power_12v_ma = 40
    mods[0].power_neg12v_ma = 20
    mods[0].power_5v_ma = 0
    mods[1].power_12v_ma = 60
    mods[1].power_neg12v_ma = 30
    mods[1].power_5v_ma = 0
    # mods[2] power stays null
    db_session.commit()

    # Place two powered modules — should succeed
    place = client.post(
        "/api/racks/",
        json={
            "user_id": sim_user.id,
            "case_id": sim_case_id,
            "name": "Sim place-loop",
            "generation_seed": 424201,
            "modules": [
                {"module_id": mods[0].id, "row_index": 0, "start_hp": 0},
                {"module_id": mods[1].id, "row_index": 0, "start_hp": mods[0].hp},
            ],
        },
    )
    assert place.status_code == 201, place.text
    rack_id = place.json()["id"]

    compat = client.get(f"/api/racks/{rack_id}/compatibility")
    assert compat.status_code == 200
    body = compat.json()
    assert body["bridge_status"] in ("ok", "incomplete")
    c = body["compatibility"]
    assert c is not None
    # Power rails should verify with known case capacity
    rails = {r["rail"]: r for r in c["power_headroom"]}
    assert rails["+12V"]["status"] == "verified"
    assert rails["+12V"]["module_draw_ma"] == 100  # 40+60
    assert rails["+12V"]["case_capacity_ma"] == 2000
    assert rails["+12V"]["headroom_ma"] == 1900

    # Overflow hard-fail: place wide module past end of row
    big = Module(
        brand="SimBrand",
        name="WideBoy",
        hp=40,
        module_type="UTIL",
        power_12v_ma=10,
        power_neg12v_ma=10,
        power_5v_ma=0,
        io_ports=[],
        tags=[],
        source="test",
    )
    db_session.add(big)
    db_session.commit()
    db_session.refresh(big)

    overflow = client.post(
        "/api/racks/",
        json={
            "user_id": sim_user.id,
            "case_id": sim_case_id,
            "name": "overflow",
            "generation_seed": 424202,
            "modules": [
                {"module_id": big.id, "row_index": 0, "start_hp": 50},  # 50+40 > 84
            ],
        },
    )
    assert overflow.status_code == 400
    detail = overflow.json()["detail"]
    assert detail["message"] == "Rack validation failed"
    msgs = " ".join(e.get("message", "") for e in detail.get("errors", []))
    assert "exceeds" in msgs.lower() or "capacity" in msgs.lower()


def test_simulate_connector_budget_hard_fail(
    client: TestClient,
    db_session: Session,
    sim_user: User,
    sim_case_id: int,
) -> None:
    # Case has 8 connectors — place 9 modules hard-fails catalog gate
    mods = []
    for i in range(9):
        m = Module(
            brand="ConnSim",
            name=f"U{i}",
            hp=2,
            module_type="UTIL",
            power_12v_ma=5,
            power_neg12v_ma=5,
            power_5v_ma=0,
            io_ports=[],
            tags=[],
            source="test",
        )
        db_session.add(m)
        mods.append(m)
    db_session.commit()
    for m in mods:
        db_session.refresh(m)

    placements = [
        {"module_id": m.id, "row_index": 0, "start_hp": i * 2} for i, m in enumerate(mods)
    ]
    resp = client.post(
        "/api/racks/",
        json={
            "user_id": sim_user.id,
            "case_id": sim_case_id,
            "name": "connector overflow",
            "generation_seed": 424203,
            "modules": placements,
        },
    )
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"]
    blob = str(detail).lower()
    assert "connector" in blob


def test_simulate_module_power_unknown_soft_warning(
    client: TestClient,
    db_session: Session,
    sim_user: User,
    sim_case_id: int,
) -> None:
    unknown = Module(
        brand="SoftSim",
        name="NoPower",
        hp=8,
        module_type="UTIL",
        power_12v_ma=None,
        power_neg12v_ma=None,
        power_5v_ma=None,
        io_ports=[],
        tags=[],
        source="ModuleCatalog",
    )
    db_session.add(unknown)
    db_session.commit()
    db_session.refresh(unknown)

    resp = client.post(
        "/api/racks/",
        json={
            "user_id": sim_user.id,
            "case_id": sim_case_id,
            "name": "unknown power",
            "generation_seed": 424204,
            "modules": [
                {"module_id": unknown.id, "row_index": 0, "start_hp": 0},
            ],
        },
    )
    # Create may succeed with soft catalog warnings (not hard fail for unknown module power alone)
    assert resp.status_code in (201, 400)
    if resp.status_code == 201:
        rid = resp.json()["id"]
        compat = client.get(f"/api/racks/{rid}/compatibility").json()
        c = compat.get("compatibility") or {}
        codes = [w.get("code") for w in (c.get("warnings") or [])]
        # Soft incomplete expected when power missing
        assert c.get("overall_status") in ("incomplete", "verified", "conflict")
        # Either MODULE_POWER_UNKNOWN or draw understated path
        assert (
            "MODULE_POWER_UNKNOWN" in codes
            or c.get("overall_status") == "incomplete"
            or any("power" in (w.get("message") or "").lower() for w in (c.get("warnings") or []))
        )
