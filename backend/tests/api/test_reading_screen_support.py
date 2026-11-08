"""Spec 009 T050's backend: what the Reading screen reads. The owner sees their own photo
back, each candidate comes with its Module's name, and the catalog answers a name search for
a fix."""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from canon.models import ImageAssetRecord
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

    for name, value in {
        "export_dir": str(tmp_path),
        "export_store_root": str(tmp_path),
        "photo_reading_provider": "recorded",
        "photo_reading_recordings_dir": str(tmp_path),
    }.items():
        monkeypatch.setattr(config_mod.settings, name, value)
    return tmp_path


def _photo(shade: int = 40) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (shade, 30, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def _start(client, user, recordings, photo: bytes, sightings: list[dict]) -> dict:
    payload = {"provider_version": "recorded-1", "sightings": sightings}
    (recordings / f"{hashlib.sha256(photo).hexdigest()}.json").write_text(json.dumps(payload))
    started = client.post(
        "/api/evidence/rig-photos",
        files={"file": ("rig.jpg", photo, "image/jpeg")},
        data={"rows": "0"},
        headers=bearer_headers(user),
    )
    assert started.status_code == 201, started.text
    return started.json()


def _content(client, user, rig_id: int, photo_id: str):
    return client.get(
        f"/api/racks/{rig_id}/evidence/images/{photo_id}/content", headers=bearer_headers(user)
    )


# --- the owner's photo, back -----------------------------------------------------------------


def test_the_owner_gets_their_photo_back_privately(
    client: TestClient, db_session: Session, sample_user: User, recordings: Path
) -> None:
    started = _start(client, sample_user, recordings, _photo(), [])

    answer = _content(client, sample_user, started["rig_id"], started["photo_id"])

    assert answer.status_code == 200
    assert answer.headers["content-type"] == "image/jpeg"
    assert answer.headers["cache-control"] == "private, no-store"
    assert answer.headers["x-content-type-options"] == "nosniff"
    stored = db_session.get(ImageAssetRecord, started["photo_id"])
    assert hashlib.sha256(answer.content).hexdigest() == stored.content_sha256


def test_no_one_else_sees_the_photo(
    client: TestClient, db_session: Session, sample_user: User, recordings: Path
) -> None:
    started = _start(client, sample_user, recordings, _photo(), [])
    stranger = User(username="stranger", email="s@example.com", password_hash="x", role="User")
    db_session.add(stranger)
    db_session.commit()

    assert _content(client, stranger, started["rig_id"], started["photo_id"]).status_code == 404
    signed_out = client.get(
        f"/api/racks/{started['rig_id']}/evidence/images/{started['photo_id']}/content"
    )
    assert signed_out.status_code in {401, 404}


def test_an_expired_or_deleted_photo_is_gone(
    client: TestClient, db_session: Session, sample_user: User, recordings: Path
) -> None:
    expired = _start(client, sample_user, recordings, _photo(40), [])
    deleted = _start(client, sample_user, recordings, _photo(90), [])
    db_session.get(ImageAssetRecord, expired["photo_id"]).retention_expires_at = datetime.now(
        timezone.utc
    ) - timedelta(minutes=1)
    db_session.commit()
    client.delete(
        f"/api/racks/{deleted['rig_id']}/evidence/images/{deleted['photo_id']}",
        headers=bearer_headers(sample_user),
    )

    assert _content(client, sample_user, expired["rig_id"], expired["photo_id"]).status_code == 404
    assert _content(client, sample_user, deleted["rig_id"], deleted["photo_id"]).status_code == 404


# --- candidates by name ----------------------------------------------------------------------


def test_each_candidate_comes_with_its_modules_name_and_width(
    client: TestClient,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    recordings: Path,
) -> None:
    sighting = {
        "box": {"x": 0.0, "y": 0.1, "w": 0.12, "h": 0.8},
        "kind": "module",
        "row_index": 0,
        "start_hp": 0,
        "hp": 10,
        "candidates": [
            {"module_id": sample_vco.id, "score": 0.6},
            {"module_id": sample_vcf.id, "score": 0.3},
        ],
    }
    started = _start(client, sample_user, recordings, _photo(), [sighting])

    readings = client.get(
        f"/api/racks/{started['rig_id']}/evidence/readings", headers=bearer_headers(sample_user)
    ).json()["readings"]

    ((seen,),) = [r["sightings"] for r in readings]
    assert seen["candidates"] == [
        {
            "module_id": sample_vco.id,
            "score": 0.6,
            "brand": sample_vco.brand,
            "name": sample_vco.name,
            "hp": sample_vco.hp,
        },
        {
            "module_id": sample_vcf.id,
            "score": 0.3,
            "brand": sample_vcf.brand,
            "name": sample_vcf.name,
            "hp": sample_vcf.hp,
        },
    ]


# --- a name search for a fix -----------------------------------------------------------------


def test_the_catalog_answers_a_search_by_maker_and_name(
    client: TestClient, db_session: Session, sample_vco: Module, sample_vcf: Module
) -> None:
    db_session.add(
        Module(
            brand="Make Noise", name="Maths", module_type="ENV", hp=20, io_ports=[], source="test"
        )
    )
    db_session.add(
        Module(brand="Odd_Co", name="100% Wet", module_type="FX", hp=8, io_ports=[], source="test")
    )
    db_session.commit()

    def names(q: str) -> list[str]:
        answer = client.get("/api/modules/", params={"q": q, "limit": 50})
        assert answer.status_code == 200, answer.text
        return sorted(m["name"] for m in answer.json()["modules"])

    # Every word has to appear in the maker or the name, in any case.
    assert names("make noise maths") == ["Maths"]
    assert names("test vc") == sorted([sample_vco.name, sample_vcf.name])
    assert names("vcf") == [sample_vcf.name]
    # A search is text, never a pattern.
    assert names("100%") == ["100% Wet"]
    assert names("odd_") == ["100% Wet"]
    assert names("_") == ["100% Wet"]
