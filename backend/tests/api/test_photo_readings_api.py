"""Spec 009 T021 over HTTP: the photo start reads the photo, and a Rig's Readings are the
owner's to see. The journey's reading steps are in ``test_spec_009_photo_journey.py``."""

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

    monkeypatch.setattr(config_mod.settings, "export_dir", str(tmp_path))
    monkeypatch.setattr(config_mod.settings, "export_store_root", str(tmp_path))
    monkeypatch.setattr(config_mod.settings, "photo_reading_provider", "recorded")
    monkeypatch.setattr(config_mod.settings, "photo_reading_recordings_dir", str(tmp_path))
    return tmp_path


def _photo(shade: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (shade, 30, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def _record(recordings: Path, photo: bytes, module: Module) -> None:
    sighting = {
        "box": {"x": 0.0, "y": 0.1, "w": 0.12, "h": 0.8},
        "kind": "module",
        "row_index": 0,
        "start_hp": 0,
        "hp": module.hp,
        "candidates": [{"module_id": module.id, "score": 0.95}],
    }
    payload = {"provider_version": "recorded-1", "sightings": [sighting]}
    (recordings / f"{hashlib.sha256(photo).hexdigest()}.json").write_text(json.dumps(payload))


def _start(client: TestClient, user: User, photo: bytes, **data: str):
    return client.post(
        "/api/evidence/rig-photos",
        files={"file": ("rig.jpg", photo, "image/jpeg")},
        data={"rows": "0", **data},
        headers=bearer_headers(user),
    )


def _readings(client: TestClient, user: User, rig_id: int):
    return client.get(f"/api/racks/{rig_id}/evidence/readings", headers=bearer_headers(user))


def test_the_photo_start_names_the_reading_it_made(
    client: TestClient, sample_user: User, sample_vco: Module, recordings: Path
) -> None:
    photo = _photo(40)
    _record(recordings, photo, sample_vco)

    started = _start(client, sample_user, photo)

    assert started.status_code == 201, started.text
    (reading,) = _readings(client, sample_user, started.json()["rig_id"]).json()["readings"]
    assert reading["reading_id"] == started.json()["reading_id"]
    assert reading["photo_id"] == started.json()["photo_id"]
    assert reading["status"] == "read"
    assert [
        [(c["module_id"], c["score"]) for c in s["candidates"]] for s in reading["sightings"]
    ] == [[(sample_vco.id, 0.95)]]


def test_a_photo_with_no_recording_still_starts_the_rig_with_a_failed_reading(
    client: TestClient, sample_user: User, recordings: Path
) -> None:
    started = _start(client, sample_user, _photo(55))

    assert started.status_code == 201, started.text
    (reading,) = _readings(client, sample_user, started.json()["rig_id"]).json()["readings"]
    assert (reading["status"], reading["reason_code"]) == ("failed", "RECORDING_MISSING")
    assert reading["sightings"] == []


def test_each_photo_of_a_rig_gets_its_own_reading_on_its_own_rows(
    client: TestClient, sample_user: User, sample_vco: Module, recordings: Path
) -> None:
    first, second = _photo(40), _photo(90)
    _record(recordings, first, sample_vco)
    _record(recordings, second, sample_vco)
    rig_id = _start(client, sample_user, first).json()["rig_id"]

    added = _start(client, sample_user, second, rig_id=str(rig_id), rows="1")

    assert added.status_code == 201, added.text
    readings = _readings(client, sample_user, rig_id).json()["readings"]
    assert [r["reading_id"] for r in readings][-1] == added.json()["reading_id"]
    assert [(r["first_row"], [s["row_index"] for s in r["sightings"]]) for r in readings] == [
        (0, [0]),
        (1, [1]),
    ]


def test_a_rigs_readings_are_its_owners(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    recordings: Path,
) -> None:
    photo = _photo(40)
    _record(recordings, photo, sample_vco)
    rig_id = _start(client, sample_user, photo).json()["rig_id"]
    stranger = User(username="stranger", email="s@example.com", password_hash="x", role="User")
    db_session.add(stranger)
    db_session.commit()

    assert _readings(client, stranger, rig_id).status_code == 404
    assert client.get(f"/api/racks/{rig_id}/evidence/readings").status_code == 401
