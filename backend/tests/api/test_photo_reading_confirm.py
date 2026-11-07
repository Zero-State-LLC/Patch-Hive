"""Spec 009 T030: confirming a Rig's Readings. The journey's own steps are in
``test_spec_009_photo_journey.py``; these cover each refusal and what a confirmation writes."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from canon.models import PhotoReadingRecord, RigRevisionRecord, SystemInventoryRevisionRecord
from cases.models import Case
from community.models import User
from main import app
from modules.models import Module
from racks.models import Rack, RackModule
from tests.conftest import bearer_headers


@pytest.fixture
def client(db_session: Session):
    from core import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def recordings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import core.config as config_mod

    for name, value in {
        "export_dir": str(tmp_path),
        "export_store_root": str(tmp_path),
        "photo_reading_provider": "recorded",
        "photo_reading_recordings_dir": str(tmp_path),
    }.items():
        monkeypatch.setattr(config_mod.settings, name, value)
    return tmp_path


def _photo(shade: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (shade, 30, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def _sighting(module: Module | None, start_hp: int, hp: int, *, kind: str = "module") -> dict:
    return {
        "box": {"x": start_hp / 84, "y": 0.1, "w": hp / 84, "h": 0.8},
        "kind": kind,
        "row_index": 0,
        "start_hp": start_hp,
        "hp": hp,
        "candidates": [{"module_id": module.id, "score": 0.95}] if module else [],
    }


def _start(client, user, recordings, sightings, *, shade: int = 40, **data) -> int:
    photo = _photo(shade)
    payload = {"provider_version": "recorded-1", "sightings": sightings}
    (recordings / f"{hashlib.sha256(photo).hexdigest()}.json").write_text(json.dumps(payload))
    started = client.post(
        "/api/evidence/rig-photos",
        files={"file": ("rig.jpg", photo, "image/jpeg")},
        data={"rows": "0", **data},
        headers=bearer_headers(user),
    )
    assert started.status_code == 201, started.text
    return started.json()["rig_id"]


def _sighting_ids(client, user, rig_id) -> list[str]:
    readings = client.get(
        f"/api/racks/{rig_id}/evidence/readings", headers=bearer_headers(user)
    ).json()["readings"]
    return [s["sighting_id"] for r in readings if r["status"] == "read" for s in r["sightings"]]


def _confirm(client, user, rig_id, **body):
    payload = {"items": [], "added": [], "excluded": [], "case_id": None, **body}
    return client.post(
        f"/api/racks/{rig_id}/evidence/readings/confirm", json=payload, headers=bearer_headers(user)
    )


def _keep(sighting_id: str, module: Module, start_hp: int, row: int = 0) -> dict:
    return {
        "sighting_id": sighting_id,
        "module_id": module.id,
        "row_index": row,
        "start_hp": start_hp,
    }


def _placed(db: Session, rig_id: int) -> list[tuple[int, int, int]]:
    rows = db.query(RackModule).filter(RackModule.rack_id == rig_id).all()
    return sorted((rm.module_id, rm.row_index, rm.start_hp) for rm in rows)


# --- what confirming writes ------------------------------------------------------------------


def test_confirming_places_the_kept_and_added_modules_and_names_the_power_unknown(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    sample_lfo: Module,
    recordings: Path,
) -> None:
    rig_id = _start(client, sample_user, recordings, [_sighting(sample_vco, 0, 10)])
    (sighting,) = _sighting_ids(client, sample_user, rig_id)

    # The owner corrects the identity to a Module the provider never named, and adds one.
    answer = _confirm(
        client,
        sample_user,
        rig_id,
        items=[_keep(sighting, sample_vcf, 0)],
        added=[{"module_id": sample_lfo.id, "row_index": 1, "start_hp": 2}],
    )

    assert answer.status_code == 201, answer.text
    body = answer.json()
    assert body["ready_for_generation"] is True and body["modules_to_place"] == []
    assert _placed(db_session, rig_id) == sorted([(sample_vcf.id, 0, 0), (sample_lfo.id, 1, 2)])
    assert any(w["details"]["code"] == "POWER_UNSPECIFIED" for w in body["warnings"])
    assert db_session.get(RigRevisionRecord, body["rig_revision_id"]) is not None
    record = db_session.get(SystemInventoryRevisionRecord, body["inventory_revision_id"])
    assert [item["source_candidate_ids"] for item in record.items] == [[sighting], []]
    reading = (
        db_session.query(PhotoReadingRecord).filter(PhotoReadingRecord.rack_id == rig_id).one()
    )
    assert reading.status == "confirmed"
    rig = db_session.get(Rack, rig_id)
    assert rig.name == rig.name_suggested != "Modular Starter Rack"


def test_generation_uses_the_revision_the_confirmation_made(
    client: TestClient,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    sample_vca: Module,
    recordings: Path,
) -> None:
    sightings = [
        _sighting(sample_vco, 0, 10),
        _sighting(sample_vcf, 10, 8),
        _sighting(sample_vca, 18, 6),
    ]
    rig_id = _start(client, sample_user, recordings, sightings)
    ids = _sighting_ids(client, sample_user, rig_id)
    modules = [sample_vco, sample_vcf, sample_vca]
    confirmed = _confirm(
        client,
        sample_user,
        rig_id,
        items=[_keep(sid, m, s["start_hp"]) for sid, m, s in zip(ids, modules, sightings)],
    )
    assert confirmed.status_code == 201, confirmed.text

    generated = client.post(
        f"/api/patches/generate/{rig_id}", json={}, headers=bearer_headers(sample_user)
    )

    assert generated.status_code == 200, generated.text
    assert generated.json()["rig_revision_id"] == confirmed.json()["rig_revision_id"]


def test_a_named_case_becomes_the_rigs(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_case: Case,
    recordings: Path,
) -> None:
    rig_id = _start(client, sample_user, recordings, [_sighting(sample_vco, 0, 10)])
    (sighting,) = _sighting_ids(client, sample_user, rig_id)

    answer = _confirm(
        client, sample_user, rig_id, items=[_keep(sighting, sample_vco, 0)], case_id=sample_case.id
    )

    assert answer.status_code == 201, answer.text
    assert db_session.get(Rack, rig_id).case_id == sample_case.id


def test_a_later_photo_makes_a_new_revision_and_the_earlier_one_stays(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    recordings: Path,
) -> None:
    rig_id = _start(client, sample_user, recordings, [_sighting(sample_vco, 0, 10)])
    (first,) = _sighting_ids(client, sample_user, rig_id)
    earlier = _confirm(client, sample_user, rig_id, items=[_keep(first, sample_vco, 0)]).json()
    assert _confirm(client, sample_user, rig_id, items=[]).json()["detail"]["code"] == (
        "NO_CURRENT_READING"
    )

    _start(
        client, sample_user, recordings, [_sighting(sample_vcf, 0, 8)], shade=90, rig_id=str(rig_id)
    )
    (second,) = _sighting_ids(client, sample_user, rig_id)
    later = _confirm(
        client,
        sample_user,
        rig_id,
        items=[_keep(second, sample_vcf, 10)],
        added=[{"module_id": sample_vco.id, "row_index": 0, "start_hp": 0}],
    )

    assert later.status_code == 201, later.text
    assert later.json()["rig_revision_id"] != earlier["rig_revision_id"]
    assert db_session.get(RigRevisionRecord, earlier["rig_revision_id"]) is not None
    assert _placed(db_session, rig_id) == sorted([(sample_vco.id, 0, 0), (sample_vcf.id, 0, 10)])


# --- what confirming refuses, writing nothing ------------------------------------------------


def _refused(db: Session, rig_id: int, answer, status: int, code: str) -> dict:
    assert answer.status_code == status, answer.text
    detail = answer.json()["detail"]
    assert detail["code"] == code
    assert _placed(db, rig_id) == []
    assert db.query(SystemInventoryRevisionRecord).filter_by(rack_id=rig_id).count() == 0
    assert db.query(PhotoReadingRecord).filter_by(rack_id=rig_id, status="confirmed").count() == 0
    return detail


def test_a_reading_that_failed_holds_the_confirmation(
    client: TestClient, db_session: Session, sample_user: User, sample_vco: Module, recordings: Path
) -> None:
    rig_id = _start(client, sample_user, recordings, [_sighting(sample_vco, 0, 10)])
    (sighting,) = _sighting_ids(client, sample_user, rig_id)
    # A second photo with no recording: its Reading fails.
    client.post(
        "/api/evidence/rig-photos",
        files={"file": ("rig.jpg", _photo(120), "image/jpeg")},
        data={"rows": "1", "rig_id": str(rig_id)},
        headers=bearer_headers(sample_user),
    )

    answer = _confirm(client, sample_user, rig_id, items=[_keep(sighting, sample_vco, 0)])

    detail = _refused(db_session, rig_id, answer, 409, "READING_NOT_READ")
    assert len(detail["readings"]) == 1


def test_every_module_sighting_must_be_kept_or_left_out(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    recordings: Path,
) -> None:
    sightings = [
        _sighting(sample_vco, 0, 10),
        _sighting(sample_vcf, 10, 8),
        _sighting(None, 18, 4, kind="blank_panel"),
    ]
    rig_id = _start(client, sample_user, recordings, sightings)
    vco, vcf, _panel = _sighting_ids(client, sample_user, rig_id)

    answer = _confirm(client, sample_user, rig_id, items=[_keep(vco, sample_vco, 0)])

    assert _refused(db_session, rig_id, answer, 409, "SIGHTINGS_UNDECIDED")["sightings"] == [vcf]


@pytest.mark.parametrize(
    ("change", "status", "code"),
    [
        ("twice", 400, "SIGHTING_DECIDED_TWICE"),
        ("stranger_sighting", 400, "SIGHTING_NOT_IN_READING"),
        ("panel", 409, "BLANK_PANEL_NOT_INVENTORY"),
        ("missing_module", 400, "MODULE_NOT_FOUND"),
        ("missing_case", 400, "CASE_NOT_FOUND"),
        ("past_case", 409, "ROW_PAST_CASE"),
        ("nothing", 400, "NO_MODULES"),
    ],
)
def test_a_confirmation_it_cannot_apply_is_refused_and_writes_nothing(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_case: Case,
    recordings: Path,
    change: str,
    status: int,
    code: str,
) -> None:
    rig_id = _start(
        client,
        sample_user,
        recordings,
        [_sighting(sample_vco, 0, 10), _sighting(None, 10, 4, kind="blank_panel")],
    )
    vco, panel = _sighting_ids(client, sample_user, rig_id)
    body: dict = {"items": [_keep(vco, sample_vco, 0)]}
    if change == "twice":
        body["excluded"] = [vco]
    elif change == "stranger_sighting":
        body["excluded"] = ["sight-not-here"]
    elif change == "panel":
        body["items"].append(_keep(panel, sample_vco, 20))
    elif change == "missing_module":
        body["items"] = [{**_keep(vco, sample_vco, 0), "module_id": 999_999}]
    elif change == "missing_case":
        body["case_id"] = 999_999
    elif change == "past_case":
        body["case_id"] = sample_case.id
        body["items"] = [_keep(vco, sample_vco, 80)]  # 10 HP from HP 80 runs past 84
    elif change == "nothing":
        body = {"excluded": [vco]}

    detail = _refused(
        db_session, rig_id, _confirm(client, sample_user, rig_id, **body), status, code
    )
    if code == "ROW_PAST_CASE":
        assert detail["modules"] == [sample_vco.id]


def test_only_the_owner_confirms(
    client: TestClient, db_session: Session, sample_user: User, sample_vco: Module, recordings: Path
) -> None:
    rig_id = _start(client, sample_user, recordings, [_sighting(sample_vco, 0, 10)])
    (sighting,) = _sighting_ids(client, sample_user, rig_id)
    stranger = User(username="stranger", email="s@example.com", password_hash="x", role="User")
    db_session.add(stranger)
    db_session.commit()

    answer = _confirm(client, stranger, rig_id, items=[_keep(sighting, sample_vco, 0)])

    assert answer.status_code == 404
    assert _placed(db_session, rig_id) == []
