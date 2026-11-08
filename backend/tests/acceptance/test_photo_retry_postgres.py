"""Spec 009 T031 on Postgres: a Retry supersedes its failed Reading with a conditional
update, and confirming a later photo of one row keeps the other row's Placements."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from modules.models import Module
from racks.models import RackModule


@pytest.fixture
def recordings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import core.config as config_mod
    import evidence.readings
    import evidence.routes

    # The acceptance setup reloads core.config; the evidence modules keep the settings they
    # imported, so each instance in use is set.
    instances = {
        id(s): s
        for s in (config_mod.settings, evidence.readings.settings, evidence.routes.settings)
    }
    for instance in instances.values():
        for name, value in {
            "export_dir": str(tmp_path),
            "export_store_root": str(tmp_path),
            "photo_reading_provider": "recorded",
            "photo_reading_recordings_dir": str(tmp_path),
        }.items():
            monkeypatch.setattr(instance, name, value)
    return tmp_path


def _module(db: Session, name: str, hp: int) -> int:
    module = Module(brand="PG Mfg", name=name, module_type="VCO", hp=hp, io_ports=[], source="test")
    db.add(module)
    db.commit()
    return int(module.id)


def _photo(shade: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (shade, 30, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def _record(recordings: Path, photo: bytes, module_id: int, hp: int) -> None:
    sighting = {
        "box": {"x": 0.0, "y": 0.1, "w": hp / 84, "h": 0.8},
        "kind": "module",
        "row_index": 0,
        "start_hp": 0,
        "hp": hp,
        "candidates": [{"module_id": module_id, "score": 0.95}],
    }
    payload = {"provider_version": "recorded-1", "sightings": [sighting]}
    (recordings / f"{hashlib.sha256(photo).hexdigest()}.json").write_text(json.dumps(payload))


def test_a_retry_and_a_photo_of_another_row_on_postgres(
    api_client: TestClient,
    db_session: Session,
    create_user,
    login,
    recordings: Path,
) -> None:
    create_user("pg-retry-owner", "pg-pass")
    headers = {"Authorization": f"Bearer {login('pg-retry-owner', 'pg-pass')}"}
    vco, vcf = _module(db_session, "PG VCO", 10), _module(db_session, "PG VCF", 8)

    def readings(rig_id: int) -> dict[str, dict]:
        answer = api_client.get(f"/api/racks/{rig_id}/evidence/readings", headers=headers)
        return {r["reading_id"]: r for r in answer.json()["readings"]}

    def upload(photo: bytes, **data) -> dict:
        started = api_client.post(
            "/api/evidence/rig-photos",
            files={"file": ("rig.jpg", photo, "image/jpeg")},
            data={"rows": "0", **data},
            headers=headers,
        )
        assert started.status_code == 201, started.text
        return started.json()

    def confirm(rig_id: int, sighting_id: str, module_id: int, row: int):
        item = {"sighting_id": sighting_id, "module_id": module_id, "row_index": row, "start_hp": 0}
        return api_client.post(
            f"/api/racks/{rig_id}/evidence/readings/confirm",
            json={"items": [item], "added": [], "excluded": [], "case_id": None},
            headers=headers,
        )

    # The first photo has no recorded answer, so its Reading fails; once it has one, a
    # Retry reads it, and a second Retry of the failed Reading finds it superseded.
    first = _photo(40)
    started = upload(first)
    rig_id, failed = started["rig_id"], started["reading_id"]
    _record(recordings, first, vco, 10)
    retried = api_client.post(
        f"/api/racks/{rig_id}/evidence/readings/{failed}/retry", headers=headers
    )
    assert retried.status_code == 201, retried.text
    again = api_client.post(
        f"/api/racks/{rig_id}/evidence/readings/{failed}/retry", headers=headers
    )
    assert (again.status_code, again.json()["detail"]) == (409, "READING_NOT_FAILED")
    current = readings(rig_id)
    assert current[failed]["status"] == "superseded"
    (sighting,) = current[retried.json()["reading_id"]]["sightings"]
    assert confirm(rig_id, sighting["sighting_id"], vco, 0).status_code == 201

    # A later photo of row 1 leaves row 0's Placement in place.
    second = _photo(150)
    _record(recordings, second, vcf, 8)
    later = upload(second, rows="1", rig_id=str(rig_id))
    (sighting,) = readings(rig_id)[later["reading_id"]]["sightings"]
    answer = confirm(rig_id, sighting["sighting_id"], vcf, 1)

    assert answer.status_code == 201, answer.text
    db_session.expire_all()
    placed = db_session.query(RackModule).filter(RackModule.rack_id == rig_id).all()
    assert sorted((p.module_id, p.row_index) for p in placed) == [(vco, 0), (vcf, 1)]
