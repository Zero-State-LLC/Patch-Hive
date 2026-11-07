"""Spec 009 T040: whether a host reads Rig photos, and why not. The closed default is in
``test_spec_009_photo_journey.py``; these cover open, each reason, and the upload agreeing."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from canon.models import ImageAssetRecord
from community.models import User
from main import app
from racks.models import Rack
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
def host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set this host's photo reading: a provider and its recordings folder."""
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "export_dir", str(tmp_path))
    monkeypatch.setattr(config_mod.settings, "export_store_root", str(tmp_path))

    def configure(provider: str, recordings: str = "") -> None:
        monkeypatch.setattr(config_mod.settings, "photo_reading_provider", provider)
        monkeypatch.setattr(config_mod.settings, "photo_reading_recordings_dir", recordings)

    return configure


def _photo() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (40, 30, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def test_a_host_with_recorded_answers_is_open(client: TestClient, host, tmp_path: Path) -> None:
    host("recorded", str(tmp_path))

    assert client.get("/api/evidence/photo-reading").json() == {"available": True, "reason": None}


@pytest.mark.parametrize(
    ("provider", "recordings", "reason"),
    [
        ("disabled", "", "PROVIDER_DISABLED"),
        ("nvidia", "", "PROVIDER_UNAVAILABLE"),
        ("recorded", "", "RECORDINGS_NOT_CONFIGURED"),
        ("recorded", "/no/such/recordings", "RECORDINGS_NOT_CONFIGURED"),
    ],
)
def test_a_closed_host_says_why_and_refuses_the_upload(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    host,
    provider: str,
    recordings: str,
    reason: str,
) -> None:
    host(provider, recordings)

    answer = client.get("/api/evidence/photo-reading").json()
    upload = client.post(
        "/api/evidence/rig-photos",
        files={"file": ("rig.jpg", _photo(), "image/jpeg")},
        data={"rows": "0"},
        headers=bearer_headers(sample_user),
    )

    assert answer == {"available": False, "reason": reason}
    assert upload.status_code == 409
    assert upload.json()["detail"] == "PHOTO_READING_UNAVAILABLE"
    assert db_session.query(Rack).count() == 0
    assert db_session.query(ImageAssetRecord).count() == 0
