"""Spec 009 T020: starting a Rig from a photo, and a Rig with no Case on the existing paths.

The journey's own steps are in ``test_spec_009_photo_journey.py``. These cover what the
journey doesn't: what the photo start refuses, and that a Rig with no Case validates,
generates and draws.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from canon.models import ImageAssetRecord
from community.models import User
from export.patchbook.render_schematic import render_patch_schematic
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
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "export_dir", str(tmp_path))
    monkeypatch.setattr(config_mod.settings, "export_store_root", str(tmp_path))
    return tmp_path


@pytest.fixture
def reading_open(monkeypatch: pytest.MonkeyPatch, storage: Path) -> None:
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "photo_reading_provider", "recorded")
    monkeypatch.setattr(config_mod.settings, "photo_reading_recordings_dir", str(storage))


def _photo(shade: int = 40) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (shade, 30, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def _start(client: TestClient, user: User, photo: bytes, **data: str):
    return client.post(
        "/api/evidence/rig-photos",
        files={"file": ("rig.jpg", photo, "image/jpeg")},
        data={"rows": "0", **data},
        headers=bearer_headers(user),
    )


def _stored(db: Session) -> tuple[int, int]:
    return db.query(Rack).count(), db.query(ImageAssetRecord).count()


def _caseless_rig(db: Session, user: User, *placements: tuple[Module, int, int]) -> Rack:
    rack = Rack(user_id=user.id, case_id=None, name="From a photo", tags=[])
    db.add(rack)
    db.flush()
    for module, row_index, start_hp in placements:
        db.add(
            RackModule(rack_id=rack.id, module_id=module.id, row_index=row_index, start_hp=start_hp)
        )
    db.commit()
    return rack


# --- what the photo start refuses ------------------------------------------------------------


def test_a_host_that_reads_no_photos_refuses_and_stores_nothing(
    client: TestClient, db_session: Session, sample_user: User, storage: Path
) -> None:
    before = _stored(db_session)

    answer = _start(client, sample_user, _photo())

    assert answer.status_code == 409
    assert answer.json()["detail"] == "PHOTO_READING_UNAVAILABLE"
    assert _stored(db_session) == before


@pytest.mark.parametrize("rows", ["x", "-1", "2-1", "0-", "0-1-2", "1.5"])
def test_rows_it_cannot_read_are_refused_before_anything_is_stored(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    reading_open: None,
    rows: str,
) -> None:
    before = _stored(db_session)

    answer = _start(client, sample_user, _photo(), rows=rows)

    assert answer.status_code == 400
    assert answer.json()["detail"] == "ROWS_INVALID"
    assert _stored(db_session) == before


def test_a_file_that_is_not_an_image_starts_no_rig(
    client: TestClient, db_session: Session, sample_user: User, reading_open: None
) -> None:
    before = _stored(db_session)

    answer = _start(client, sample_user, b"not an image at all")

    assert answer.status_code == 400
    assert _stored(db_session) == before


def test_a_retention_past_the_cap_is_refused(
    client: TestClient, db_session: Session, sample_user: User, reading_open: None
) -> None:
    answer = _start(client, sample_user, _photo(), retention_days="91")

    assert answer.status_code == 400
    assert answer.json()["detail"] == "RETENTION_DAYS_INVALID"


# --- a photo of an existing Rig --------------------------------------------------------------


def test_a_second_photo_joins_the_owners_rig(
    client: TestClient, db_session: Session, sample_user: User, reading_open: None
) -> None:
    first = _start(client, sample_user, _photo(40))
    assert first.status_code == 201, first.text
    rig_id = first.json()["rig_id"]

    second = _start(client, sample_user, _photo(90), rig_id=str(rig_id), rows="1")

    assert second.status_code == 201, second.text
    assert second.json()["rig_id"] == rig_id
    assert db_session.query(Rack).filter(Rack.user_id == sample_user.id).count() == 1
    images = client.get(
        f"/api/racks/{rig_id}/evidence/images", headers=bearer_headers(sample_user)
    ).json()
    assert images["total"] == 2
    assert all(asset["retention_days"] == 30 for asset in images["assets"])


def test_a_photo_cannot_join_someone_elses_rig(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_rack_basic: Rack,
    reading_open: None,
) -> None:
    stranger = User(username="stranger", email="s@example.com", password_hash="x", role="User")
    db_session.add(stranger)
    db_session.commit()
    before = _stored(db_session)

    answer = _start(client, stranger, _photo(), rig_id=str(sample_rack_basic.id))

    assert answer.status_code == 404
    assert _stored(db_session) == before


def test_a_rig_from_a_photo_is_private(
    client: TestClient, db_session: Session, sample_user: User, reading_open: None
) -> None:
    started = _start(client, sample_user, _photo())
    rig_id = started.json()["rig_id"]

    assert client.get(f"/api/canon/rigs/{rig_id}").status_code == 404
    assert client.get(f"/api/racks/{rig_id}/evidence/images").status_code in {401, 404}


# --- a Rig with no Case on the existing paths ------------------------------------------------


def test_a_rig_with_no_case_takes_placements_without_one(
    client: TestClient, db_session: Session, sample_user: User, sample_vco: Module
) -> None:
    rack = _caseless_rig(db_session, sample_user)

    answer = client.patch(
        f"/api/racks/{rack.id}",
        json={"modules": [{"module_id": sample_vco.id, "row_index": 2, "start_hp": 150}]},
        headers=bearer_headers(sample_user),
    )

    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["case_id"] is None and body["case"] is None
    assert [(m["row_index"], m["start_hp"]) for m in body["modules"]] == [(2, 150)]


def test_a_rig_with_no_case_refuses_overlapping_placements(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
) -> None:
    rack = _caseless_rig(db_session, sample_user)

    answer = client.patch(
        f"/api/racks/{rack.id}",
        json={
            "modules": [
                {"module_id": sample_vco.id, "row_index": 0, "start_hp": 0},
                {"module_id": sample_vcf.id, "row_index": 0, "start_hp": 1},
            ]
        },
        headers=bearer_headers(sample_user),
    )

    assert answer.status_code == 400
    assert db_session.query(RackModule).filter(RackModule.rack_id == rack.id).count() == 0


def test_a_rig_with_no_case_generates_from_its_placements(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_vco: Module,
    sample_vcf: Module,
    sample_vca: Module,
) -> None:
    rack = _caseless_rig(
        db_session,
        sample_user,
        (sample_vco, 0, 0),
        (sample_vcf, 0, sample_vco.hp),
        (sample_vca, 0, sample_vco.hp + sample_vcf.hp),
    )

    answer = client.post(
        f"/api/patches/generate/{rack.id}", json={}, headers=bearer_headers(sample_user)
    )

    assert answer.status_code == 200, answer.text
    assert answer.json()["rig_revision_id"]


def test_a_rig_with_no_case_is_drawn_as_wide_as_its_modules(
    db_session: Session, sample_user: User, sample_vco: Module, sample_vcf: Module
) -> None:
    rack = _caseless_rig(db_session, sample_user, (sample_vco, 0, 0), (sample_vcf, 1, 4))

    schematic = render_patch_schematic(
        db_session,
        rack,
        [
            {
                "from_module_id": sample_vco.id,
                "from_port": "out",
                "to_module_id": sample_vcf.id,
                "to_port": "in",
                "cable_type": "audio",
            }
        ],
    )

    assert schematic.diagram_svg
    widest = max(sample_vco.hp, 4 + sample_vcf.hp)
    assert f'width="{widest * 8 + 80}"' in schematic.diagram_svg
    assert f'height="{120 * 2 + 40}"' in schematic.diagram_svg


def test_a_photo_is_kept_from_providers_unless_the_owner_agrees(
    client: TestClient, sample_user: User, reading_open: None
) -> None:
    kept = _start(client, sample_user, _photo(40)).json()
    shared = _start(
        client,
        sample_user,
        _photo(90),
        rig_id=str(kept["rig_id"]),
        consent_provider_processing="true",
    ).json()

    images = client.get(
        f"/api/racks/{kept['rig_id']}/evidence/images", headers=bearer_headers(sample_user)
    ).json()["assets"]
    consent = {asset["id"]: asset["consent_provider_processing"] for asset in images}
    assert consent == {kept["photo_id"]: False, shared["photo_id"]: True}
