"""Owner decision 15: an in-rack supply's output is never added to a Rig's power budget.

The budget stays what the Case supplies, and the builder warns. The trigger is a placed
Module whose ``module_type`` is SYSTEM. SYSTEM also covers fans, and nothing stored for a
placed Module tells the two apart, so the warning has to stay true for both.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from main import app
from modules.models import Module
from racks.schemas import RackModuleSpec
from racks.validation import validate_rack_configuration

CODE = "IN_RACK_SUPPLY_NOT_COUNTED"


def _system_module(db: Session, brand: str = "Eowave", name: str = "SOURCE MK3") -> Module:
    module = Module(
        brand=brand,
        name=name,
        hp=4,
        module_type="SYSTEM",
        power_12v_ma=None,
        power_neg12v_ma=None,
        power_5v_ma=None,
        io_ports=[],
        tags=[],
        source="test",
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


def _spec(module: Module, start_hp: int = 0) -> RackModuleSpec:
    return RackModuleSpec(module_id=module.id, row_index=0, start_hp=start_hp)


def _body(module: Module, start_hp: int = 0) -> dict:
    return {"module_id": module.id, "row_index": 0, "start_hp": start_hp}


def _supply_warnings(warnings: list) -> list:
    return [w for w in warnings if (w.details or {}).get("code") == CODE]


def _supply_warnings_json(body: dict) -> list[dict]:
    return [w for w in body["validation_warnings"] if (w["details"] or {}).get("code") == CODE]


@pytest.fixture
def client(db_session: Session, owner_headers: dict):
    from core import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, headers=owner_headers)
    app.dependency_overrides.clear()


def test_the_budget_stays_what_the_case_supplies(
    db_session: Session, sample_case: Case, sample_vco: Module
) -> None:
    """A SYSTEM module doesn't lift a rail: over budget without it is over budget with it."""
    sample_case.power_12v_ma = sample_vco.power_12v_ma - 1
    db_session.commit()
    supply = _system_module(db_session)

    ok, errors, _ = validate_rack_configuration(
        db_session, sample_case.id, [_spec(supply), _spec(sample_vco, start_hp=supply.hp)]
    )

    assert not ok
    exceeded = next(e for e in errors if (e.details or {}).get("code") == "POWER_EXCEEDED_12V")
    assert exceeded.details["total_power_12v"] == sample_vco.power_12v_ma
    assert exceeded.details["case_power_12v"] == sample_vco.power_12v_ma - 1


def test_a_system_module_adds_no_capacity_to_a_case_with_unknown_rails(
    db_session: Session, sample_case: Case, sample_vco: Module
) -> None:
    """Rails the Case doesn't state stay unspecified. The supply doesn't fill them in."""
    sample_case.power_12v_ma = None
    sample_case.power_neg12v_ma = None
    sample_case.power_5v_ma = None
    db_session.commit()
    supply = _system_module(db_session)

    ok, _, warnings = validate_rack_configuration(
        db_session, sample_case.id, [_spec(supply), _spec(sample_vco, start_hp=supply.hp)]
    )

    assert ok
    codes = {(w.details or {}).get("code") for w in warnings}
    assert {"POWER_UNSPECIFIED", CODE} <= codes


def test_the_warning_appears_and_stays_true_for_a_fan(
    db_session: Session, sample_case: Case
) -> None:
    fan = _system_module(db_session, brand="Alyseum", name="EOLE")

    ok, errors, warnings = validate_rack_configuration(db_session, sample_case.id, [_spec(fan)])

    assert ok, errors
    [warning] = _supply_warnings(warnings)
    assert warning.field == "power"
    assert warning.details["modules"] == [
        {"id": fan.id, "brand": "Alyseum", "name": "EOLE"},
    ]
    assert "Alyseum EOLE" in warning.message
    assert "Any power supplied by" in warning.message
    assert "isn't counted" in warning.message
    assert "only what its Case supplies" in warning.message
    # A fan isn't a power supply, and nothing stored here can say which this one is.
    assert "is a power supply" not in warning.message


def test_no_warning_without_a_system_module(
    db_session: Session, sample_case: Case, sample_vco: Module
) -> None:
    ok, _, warnings = validate_rack_configuration(db_session, sample_case.id, [_spec(sample_vco)])
    assert ok
    assert _supply_warnings(warnings) == []

    ok, _, warnings = validate_rack_configuration(db_session, sample_case.id, [])
    assert ok
    assert _supply_warnings(warnings) == []


def test_every_read_says_so_once_and_removing_the_module_clears_it(
    client: TestClient, db_session: Session, sample_case: Case, sample_vco: Module
) -> None:
    """The builder reads the Rig through the canon route, so the warning has to be there."""
    supply = _system_module(db_session)

    created = client.post(
        "/api/racks",
        json={
            "case_id": sample_case.id,
            "modules": [_body(supply), _body(sample_vco, start_hp=supply.hp)],
        },
    )
    assert created.status_code == 201, created.text
    assert len(_supply_warnings_json(created.json())) == 1
    rack_id = created.json()["id"]

    for path in (f"/api/racks/{rack_id}", f"/api/canon/rigs/{rack_id}"):
        read = client.get(path)
        assert read.status_code == 200, read.text
        assert len(_supply_warnings_json(read.json())) == 1, path

    # The Case's capacity on the response is unchanged by the supply.
    assert client.get(f"/api/racks/{rack_id}").json()["case"]["power_12v_ma"] == (
        sample_case.power_12v_ma
    )

    renamed = client.patch(f"/api/racks/{rack_id}", json={"name": "Renamed"})
    assert renamed.status_code == 200, renamed.text
    assert len(_supply_warnings_json(renamed.json())) == 1

    removed = client.patch(f"/api/racks/{rack_id}", json={"modules": [_body(sample_vco)]})
    assert removed.status_code == 200, removed.text
    assert _supply_warnings_json(removed.json()) == []
    for path in (f"/api/racks/{rack_id}", f"/api/canon/rigs/{rack_id}"):
        assert _supply_warnings_json(client.get(path).json()) == [], path


def test_several_system_modules_share_one_warning_and_a_copy_is_named_once(
    db_session: Session, sample_case: Case
) -> None:
    first = _system_module(db_session)
    second = _system_module(db_session, brand="vpme.de", name="UPWR")

    _, _, warnings = validate_rack_configuration(
        db_session,
        sample_case.id,
        [_spec(first), _spec(first, start_hp=first.hp), _spec(second, start_hp=2 * first.hp)],
    )

    [warning] = _supply_warnings(warnings)
    assert [module["id"] for module in warning.details["modules"]] == [first.id, second.id]
    assert warning.message.count("Eowave SOURCE MK3") == 1
    assert "vpme.de UPWR" in warning.message
