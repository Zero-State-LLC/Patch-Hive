"""Spec 003 D8 / T034: a module's jumper settings over the API, and the placement choice."""

import pytest

pytest.importorskip("httpx", reason="httpx is required for FastAPI TestClient")

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cases.models import Case
from main import app
from modules.models import Module, PowerConfig


@pytest.fixture
def client(db_session: Session, owner_headers: dict):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app, headers=owner_headers)
    app.dependency_overrides.clear()


@pytest.fixture
def jumper_module(db_session: Session) -> tuple[Module, list[PowerConfig]]:
    module = Module(
        brand="Velectronic", name="A-Envelope", hp=8, module_type="ENV",
        power_12v_ma=None, power_neg12v_ma=None, power_5v_ma=None,
        source="test", source_reference="https://www.velectronic.net/products/associative-quadruple-envelope",
    )
    db_session.add(module)
    db_session.flush()
    configs = [
        PowerConfig(
            module_id=module.id, brand=module.brand, name=module.name, setting_key=key, label=label,
            kind="jumper", is_recommended=recommended, power_12v_ma=p12, power_neg12v_ma=23,
            power_5v_ma=p5, unit_stated=True, rails={}, source_url=module.source_reference,
            quote="Power consumption", source_batch="t035-jumper-power",
        )
        for key, label, recommended, p12, p5 in (
            ("plus5", "The +5V jumper selected (Recommended)", True, 35, 170),
            ("plus12", "The +12V jumper selected", False, 245, 0),
        )
    ]
    db_session.add_all(configs)
    db_session.commit()
    return module, configs


def test_a_module_lists_its_settings(client: TestClient, jumper_module) -> None:
    module, configs = jumper_module
    response = client.get(f"/api/modules/{module.id}/power-configs")
    assert response.status_code == 200
    body = response.json()
    assert [c["label"] for c in body] == [c.label for c in configs]
    assert body[0] == {
        "id": configs[0].id,
        "module_id": module.id,
        "label": "The +5V jumper selected (Recommended)",
        "kind": "jumper",
        "is_recommended": True,
        "power_12v_ma": 35,
        "power_neg12v_ma": 23,
        "power_5v_ma": 170,
        "unit_stated": True,
        "source_url": "https://www.velectronic.net/products/associative-quadruple-envelope",
        "quote": "Power consumption",
    }


def test_a_module_without_settings_lists_none(client: TestClient, sample_vco: Module) -> None:
    response = client.get(f"/api/modules/{sample_vco.id}/power-configs")
    assert response.status_code == 200 and response.json() == []


def test_an_unknown_module_is_404(client: TestClient) -> None:
    assert client.get("/api/modules/999999/power-configs").status_code == 404


def test_a_placement_keeps_its_chosen_setting(client: TestClient, sample_case: Case, jumper_module) -> None:
    module, configs = jumper_module
    created = client.post(
        "/api/racks",
        json={"case_id": sample_case.id, "modules": [{"module_id": module.id, "row_index": 0, "start_hp": 0}]},
    )
    assert created.status_code == 201
    placed = created.json()["modules"][0]
    assert placed["power_config_id"] is None
    assert [c["id"] for c in placed["module"]["power_configs"]] == [c.id for c in configs]
    # No setting chosen: the jumper rails are unknown, so the budget is not confirmed.
    codes = {(w["details"] or {}).get("code") for w in created.json()["validation_warnings"]}
    assert "POWER_RAIL_INCOMPLETE" in codes

    rack_id = created.json()["id"]
    updated = client.patch(
        f"/api/racks/{rack_id}",
        json={"modules": [{"module_id": module.id, "row_index": 0, "start_hp": 0, "power_config_id": configs[1].id}]},
    )
    assert updated.status_code == 200
    assert updated.json()["modules"][0]["power_config_id"] == configs[1].id
    assert updated.json()["validation_warnings"] == []
    assert client.get(f"/api/racks/{rack_id}").json()["modules"][0]["power_config_id"] == configs[1].id


def test_a_setting_of_another_module_is_a_400(
    client: TestClient, sample_case: Case, sample_vco: Module, jumper_module
) -> None:
    _, configs = jumper_module
    response = client.post(
        "/api/racks",
        json={
            "case_id": sample_case.id,
            "modules": [{"module_id": sample_vco.id, "row_index": 0, "start_hp": 0, "power_config_id": configs[0].id}],
        },
    )
    assert response.status_code == 400
    codes = [(e["details"] or {}).get("code") for e in response.json()["detail"]["errors"]]
    assert codes == ["POWER_CONFIG_NOT_FOR_MODULE"]
