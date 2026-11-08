"""Spec 009 T031: Retry and Retake, so a failed Reading can't block its Rig, and confirming
keeps the rows no current Reading covers. Confirming itself is in
``test_photo_reading_confirm.py``."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from community.models import User
from main import app
from modules.models import Module
from racks.models import RackModule
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


def _sighting(module: Module, start_hp: int, hp: int, *, row: int = 0) -> dict:
    return {
        "box": {"x": start_hp / 84, "y": 0.1, "w": hp / 84, "h": 0.8},
        "kind": "module",
        "row_index": row,
        "start_hp": start_hp,
        "hp": hp,
        "candidates": [{"module_id": module.id, "score": 0.95}],
    }


def _record(recordings: Path, photo: bytes, sightings: list[dict]) -> None:
    payload = {"provider_version": "recorded-1", "sightings": sightings}
    (recordings / f"{hashlib.sha256(photo).hexdigest()}.json").write_text(json.dumps(payload))


def _upload(client, user, photo: bytes, **data):
    return client.post(
        "/api/evidence/rig-photos",
        files={"file": ("rig.jpg", photo, "image/jpeg")},
        data={"rows": "0", **data},
        headers=bearer_headers(user),
    )


def _readings(client, user, rig_id) -> dict[str, dict]:
    answer = client.get(f"/api/racks/{rig_id}/evidence/readings", headers=bearer_headers(user))
    return {r["reading_id"]: r for r in answer.json()["readings"]}


def _retry(client, user, rig_id, reading_id):
    return client.post(
        f"/api/racks/{rig_id}/evidence/readings/{reading_id}/retry", headers=bearer_headers(user)
    )


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


def _failed_start(client, user, photo: bytes) -> tuple[int, str]:
    """A Rig whose only photo has no recorded answer, so its Reading fails."""
    started = _upload(client, user, photo)
    assert started.status_code == 201, started.text
    body = started.json()
    assert _readings(client, user, body["rig_id"])[body["reading_id"]]["status"] == "failed"
    return body["rig_id"], body["reading_id"]


# --- Retry -----------------------------------------------------------------------------------


def test_a_retry_reads_the_stored_photo_again_and_unblocks_the_confirmation(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    recordings: Path,
) -> None:
    photo = _photo(40)
    rig_id, failed = _failed_start(client, sample_user, photo)
    # The provider can answer now.
    _record(recordings, photo, [_sighting(sample_vco, 0, 10)])

    retried = _retry(client, sample_user, rig_id, failed)

    assert retried.status_code == 201, retried.text
    body = retried.json()
    assert body["rig_id"] == rig_id and body["reading_id"] != failed
    readings = _readings(client, sample_user, rig_id)
    assert readings[failed]["status"] == "superseded"
    fresh = readings[body["reading_id"]]
    assert fresh["status"] == "read" and fresh["photo_id"] == readings[failed]["photo_id"]
    assert fresh["photo_sha256"] == hashlib.sha256(photo).hexdigest()
    (sighting,) = fresh["sightings"]
    confirmed = _confirm(
        client, sample_user, rig_id, items=[_keep(sighting["sighting_id"], sample_vco, 0)]
    )
    assert confirmed.status_code == 201, confirmed.text
    assert _placed(db_session, rig_id) == [(sample_vco.id, 0, 0)]


def _expire(client, db: Session, user, rig_id: int, photo_id: str) -> None:
    from datetime import datetime, timedelta, timezone

    from canon.models import ImageAssetRecord

    asset = db.get(ImageAssetRecord, photo_id)
    asset.retention_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.flush()


def _delete(client, db: Session, user, rig_id: int, photo_id: str) -> None:
    deleted = client.delete(
        f"/api/racks/{rig_id}/evidence/images/{photo_id}", headers=bearer_headers(user)
    )
    assert deleted.status_code == 200, deleted.text


def _corrupt(client, db: Session, user, rig_id: int, photo_id: str) -> None:
    from canon.models import ImageAssetRecord

    Path(db.get(ImageAssetRecord, photo_id).storage_path).write_bytes(b"not the photo")


@pytest.mark.parametrize(
    "gone", [_expire, _delete, _corrupt], ids=["expired", "deleted", "not-the-stored-photo"]
)
def test_a_retry_is_refused_once_the_photo_has_expired_or_been_deleted(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    recordings: Path,
    gone,
) -> None:
    photo = _photo(40)
    rig_id, failed = _failed_start(client, sample_user, photo)
    _record(recordings, photo, [_sighting(sample_vco, 0, 10)])
    gone(
        client,
        db_session,
        sample_user,
        rig_id,
        _readings(client, sample_user, rig_id)[failed]["photo_id"],
    )

    retried = _retry(client, sample_user, rig_id, failed)

    assert retried.status_code == 409, retried.text
    assert retried.json()["detail"] == "PHOTO_EXPIRED"
    readings = _readings(client, sample_user, rig_id)
    assert list(readings) == [failed] and readings[failed]["status"] == "failed"


def test_only_a_failed_reading_is_retried(
    client: TestClient, sample_user: User, sample_vco: Module, recordings: Path
) -> None:
    photo = _photo(40)
    _record(recordings, photo, [_sighting(sample_vco, 0, 10)])
    started = _upload(client, sample_user, photo).json()

    retried = _retry(client, sample_user, started["rig_id"], started["reading_id"])

    assert retried.status_code == 409 and retried.json()["detail"] == "READING_NOT_FAILED"
    assert len(_readings(client, sample_user, started["rig_id"])) == 1


def test_a_retry_is_refused_while_photo_reading_is_closed(
    client: TestClient,
    sample_user: User,
    sample_vco: Module,
    recordings: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.config as config_mod

    photo = _photo(40)
    rig_id, failed = _failed_start(client, sample_user, photo)
    _record(recordings, photo, [_sighting(sample_vco, 0, 10)])
    monkeypatch.setattr(config_mod.settings, "photo_reading_provider", "disabled")

    retried = _retry(client, sample_user, rig_id, failed)

    assert retried.status_code == 409 and retried.json()["detail"] == "PHOTO_READING_UNAVAILABLE"
    assert _readings(client, sample_user, rig_id)[failed]["status"] == "failed"


def test_only_the_owner_retries_a_reading_of_their_own_rig(
    client: TestClient, db_session: Session, sample_user: User, recordings: Path
) -> None:
    rig_id, failed = _failed_start(client, sample_user, _photo(40))
    other_rig, _ = _failed_start(client, sample_user, _photo(90))
    stranger = User(username="stranger", email="s@example.com", password_hash="x", role="User")
    db_session.add(stranger)
    db_session.commit()

    assert _retry(client, stranger, rig_id, failed).status_code == 404
    # A Reading is retried only through its own Rig.
    elsewhere = _retry(client, sample_user, other_rig, failed)
    assert elsewhere.status_code == 404 and elsewhere.json()["detail"] == "READING_NOT_FOUND"
    assert _readings(client, sample_user, rig_id)[failed]["status"] == "failed"


# --- Retake ----------------------------------------------------------------------------------


def _photo_count(client, user, rig_id: int) -> int:
    images = client.get(f"/api/racks/{rig_id}/evidence/images", headers=bearer_headers(user))
    return images.json()["total"]


def test_a_retake_replaces_the_reading_it_names_and_only_the_new_one_is_confirmed(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    recordings: Path,
) -> None:
    blurry = _photo(40)
    _record(recordings, blurry, [_sighting(sample_vco, 0, 10)])
    started = _upload(client, sample_user, blurry).json()
    rig_id, first = started["rig_id"], started["reading_id"]
    (old_sighting,) = _readings(client, sample_user, rig_id)[first]["sightings"]
    sharp = _photo(90)
    _record(recordings, sharp, [_sighting(sample_vcf, 0, 8)])

    retaken = _upload(client, sample_user, sharp, rig_id=str(rig_id), replaces_reading_id=first)

    assert retaken.status_code == 201, retaken.text
    readings = _readings(client, sample_user, rig_id)
    assert readings[first]["status"] == "superseded"
    (new_sighting,) = readings[retaken.json()["reading_id"]]["sightings"]
    stale = _confirm(
        client, sample_user, rig_id, items=[_keep(old_sighting["sighting_id"], sample_vco, 0)]
    )
    assert stale.status_code == 400 and stale.json()["detail"]["code"] == "SIGHTING_NOT_IN_READING"
    confirmed = _confirm(
        client, sample_user, rig_id, items=[_keep(new_sighting["sighting_id"], sample_vcf, 0)]
    )
    assert confirmed.status_code == 201, confirmed.text
    assert _placed(db_session, rig_id) == [(sample_vcf.id, 0, 0)]


def test_a_retake_replaces_a_failed_reading(
    client: TestClient, sample_user: User, sample_vco: Module, recordings: Path
) -> None:
    rig_id, failed = _failed_start(client, sample_user, _photo(40))
    sharp = _photo(90)
    _record(recordings, sharp, [_sighting(sample_vco, 0, 10)])

    retaken = _upload(client, sample_user, sharp, rig_id=str(rig_id), replaces_reading_id=failed)

    assert retaken.status_code == 201, retaken.text
    readings = _readings(client, sample_user, rig_id)
    assert readings[failed]["status"] == "superseded"
    assert readings[retaken.json()["reading_id"]]["status"] == "read"


def test_a_photo_that_names_no_reading_is_another_photo_of_the_rig(
    client: TestClient, sample_user: User, sample_vco: Module, recordings: Path
) -> None:
    first = _photo(40)
    _record(recordings, first, [_sighting(sample_vco, 0, 10)])
    started = _upload(client, sample_user, first).json()
    rig_id = started["rig_id"]

    _upload(client, sample_user, _photo(90), rig_id=str(rig_id))

    assert _readings(client, sample_user, rig_id)[started["reading_id"]]["status"] == "read"


def test_a_retake_is_refused_unless_it_names_a_current_reading_of_its_rig(
    client: TestClient, sample_user: User, sample_vco: Module, recordings: Path
) -> None:
    photo = _photo(40)
    _record(recordings, photo, [_sighting(sample_vco, 0, 10)])
    started = _upload(client, sample_user, photo).json()
    rig_id, reading = started["rig_id"], started["reading_id"]
    other_rig, _ = _failed_start(client, sample_user, _photo(60))
    (sighting,) = _readings(client, sample_user, rig_id)[reading]["sightings"]
    assert (
        _confirm(
            client, sample_user, rig_id, items=[_keep(sighting["sighting_id"], sample_vco, 0)]
        ).status_code
        == 201
    )
    before = _photo_count(client, sample_user, rig_id)

    # A new Rig can't replace a Reading, a Reading is replaced only through its own Rig, and
    # a confirmed Reading is done.
    no_rig = _upload(client, sample_user, _photo(90), replaces_reading_id=reading)
    elsewhere = _upload(
        client, sample_user, _photo(90), rig_id=str(other_rig), replaces_reading_id=reading
    )
    done = _upload(client, sample_user, _photo(90), rig_id=str(rig_id), replaces_reading_id=reading)

    assert (no_rig.status_code, no_rig.json()["detail"]) == (400, "RETAKE_NEEDS_RIG")
    assert (elsewhere.status_code, elsewhere.json()["detail"]) == (404, "READING_NOT_FOUND")
    assert (done.status_code, done.json()["detail"]) == (409, "READING_NOT_REPLACEABLE")
    assert _photo_count(client, sample_user, rig_id) == before
    assert _photo_count(client, sample_user, other_rig) == 1
    assert _readings(client, sample_user, rig_id)[reading]["status"] == "confirmed"


# --- confirming keeps the rows no current Reading covers ------------------------------------


def _confirmed_photo(client, user, recordings, module: Module, *, rows: str, shade: int, **data):
    """A photo of ``rows`` showing ``module`` at HP 0, read and confirmed as it was seen."""
    photo = _photo(shade)
    _record(recordings, photo, [_sighting(module, 0, 10)])
    started = _upload(client, user, photo, rows=rows, **data).json()
    (sighting,) = _readings(client, user, started["rig_id"])[started["reading_id"]]["sightings"]
    row = int(rows.split("-")[0])
    confirmed = _confirm(
        client, user, started["rig_id"], items=[_keep(sighting["sighting_id"], module, 0, row)]
    )
    assert confirmed.status_code == 201, confirmed.text
    return started["rig_id"], confirmed.json()


def _second_photo(client, user, recordings, rig_id: int, module: Module, *, rows: str) -> str:
    photo = _photo(150)
    _record(recordings, photo, [_sighting(module, 0, 8)])
    started = _upload(client, user, photo, rows=rows, rig_id=str(rig_id)).json()
    (sighting,) = _readings(client, user, rig_id)[started["reading_id"]]["sightings"]
    return sighting["sighting_id"]


def test_a_later_photo_of_one_row_leaves_the_other_rows_placements_in_place(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    recordings: Path,
) -> None:
    from canon.models import RigRevisionRecord, SystemInventoryRevisionRecord

    rig_id, _ = _confirmed_photo(client, sample_user, recordings, sample_vco, rows="0", shade=40)
    sighting = _second_photo(client, sample_user, recordings, rig_id, sample_vcf, rows="1")

    answer = _confirm(client, sample_user, rig_id, items=[_keep(sighting, sample_vcf, 0, row=1)])

    assert answer.status_code == 201, answer.text
    assert _placed(db_session, rig_id) == sorted([(sample_vco.id, 0, 0), (sample_vcf.id, 1, 0)])
    assert sorted((p["module_id"], p["row_index"]) for p in answer.json()["placements"]) == sorted(
        [(sample_vco.id, 0), (sample_vcf.id, 1)]
    )
    # The inventory and the revision are the whole Rig's, so the kept Module is in both.
    record = db_session.get(SystemInventoryRevisionRecord, answer.json()["inventory_revision_id"])
    assert sorted(len(item["source_candidate_ids"]) for item in record.items) == [0, 1]
    revision = db_session.get(RigRevisionRecord, answer.json()["rig_revision_id"])
    assert sorted(
        (m["module_id"], m["row_index"]) for m in revision.canonical_rig["modules"]
    ) == sorted([(sample_vco.id, 0), (sample_vcf.id, 1)])


def test_a_kept_placement_keeps_its_jumper_setting(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    recordings: Path,
) -> None:
    from cases.models import Case
    from modules.models import PowerConfig

    # The VCO's own draw fits the Case below; its jumper setting's draw doesn't.
    setting = PowerConfig(
        module_id=sample_vco.id,
        brand=sample_vco.brand,
        name=sample_vco.name,
        setting_key="high",
        label="High power",
        kind="jumper",
        power_12v_ma=5000,
        unit_stated=True,
        rails={},
        source_url="https://example.com/vco",
        quote="High power: 5000 mA",
        source_batch="test",
    )
    case = Case(
        brand="Test Mfg",
        name="Two rows",
        total_hp=168,
        rows=2,
        hp_per_row=[84, 84],
        power_12v_ma=1000,
        power_neg12v_ma=1000,
        power_5v_ma=1000,
        source="test",
    )
    db_session.add_all([setting, case])
    db_session.commit()
    rig_id, _ = _confirmed_photo(client, sample_user, recordings, sample_vco, rows="0", shade=40)
    placed = db_session.query(RackModule).filter_by(rack_id=rig_id).one()
    placed.power_config_id = setting.id
    db_session.commit()
    sighting = _second_photo(client, sample_user, recordings, rig_id, sample_vcf, rows="1")
    keep = [_keep(sighting, sample_vcf, 0, row=1)]

    over = _confirm(client, sample_user, rig_id, items=keep, case_id=case.id)
    answer = _confirm(client, sample_user, rig_id, items=keep)

    # The budget counts the kept VCO at its jumper setting, and the setting stays.
    assert over.status_code == 409 and over.json()["detail"]["code"] == "PLACEMENT_INVALID"
    assert "POWER_EXCEEDED_12V" in {e["details"]["code"] for e in over.json()["detail"]["errors"]}
    assert answer.status_code == 201, answer.text
    kept = db_session.query(RackModule).filter_by(rack_id=rig_id, row_index=0).one()
    assert (kept.id, kept.power_config_id) == (placed.id, setting.id)


def test_a_photo_of_several_rows_replaces_every_row_it_covers(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    sample_lfo: Module,
    recordings: Path,
) -> None:
    # The VCO is on row 0 and the VCF on row 1, each from its own photo.
    rig_id, _ = _confirmed_photo(client, sample_user, recordings, sample_vco, rows="0", shade=40)
    vcf = _second_photo(client, sample_user, recordings, rig_id, sample_vcf, rows="1")
    assert (
        _confirm(client, sample_user, rig_id, items=[_keep(vcf, sample_vcf, 0, row=1)]).status_code
        == 201
    )
    # The next photo covers rows 0 to 1 and shows only the LFO.
    photo = _photo(70)
    _record(recordings, photo, [_sighting(sample_lfo, 20, 4, row=1)])
    started = _upload(client, sample_user, photo, rows="0-1", rig_id=str(rig_id)).json()
    (sighting,) = _readings(client, sample_user, rig_id)[started["reading_id"]]["sightings"]

    answer = _confirm(
        client, sample_user, rig_id, items=[_keep(sighting["sighting_id"], sample_lfo, 20, row=1)]
    )

    assert answer.status_code == 201, answer.text
    assert _placed(db_session, rig_id) == [(sample_lfo.id, 1, 20)]


def test_the_checks_run_across_the_whole_resulting_rig(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    sample_lfo: Module,
    sample_case,
    recordings: Path,
) -> None:
    # The VCO was confirmed on row 1; the next photo is of row 0.
    rig_id, _ = _confirmed_photo(client, sample_user, recordings, sample_vco, rows="1", shade=40)
    sighting = _second_photo(client, sample_user, recordings, rig_id, sample_vcf, rows="0")
    before = _placed(db_session, rig_id)

    # A Module added on the uncovered row clashes with the one kept there.
    clash = _confirm(
        client,
        sample_user,
        rig_id,
        items=[_keep(sighting, sample_vcf, 0)],
        added=[{"module_id": sample_lfo.id, "row_index": 1, "start_hp": 4}],
    )
    # The named Case has one row, so the kept row-1 VCO is past it.
    past = _confirm(
        client, sample_user, rig_id, items=[_keep(sighting, sample_vcf, 0)], case_id=sample_case.id
    )

    assert clash.status_code == 409 and clash.json()["detail"]["code"] == "POSITIONS_OVERLAP"
    assert clash.json()["detail"]["modules"] == sorted([sample_vco.id, sample_lfo.id])
    assert past.status_code == 409 and past.json()["detail"]["code"] == "ROW_PAST_CASE"
    assert past.json()["detail"]["modules"] == [sample_vco.id]
    assert _placed(db_session, rig_id) == before == [(sample_vco.id, 1, 0)]
