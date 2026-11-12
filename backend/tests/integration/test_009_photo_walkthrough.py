"""Spec 009 T060a: the staging walkthrough from a photo, run in-process. This is Seam 2.

The walkthrough signs in as the seeded owner, uploads a fixture photo with its recorded provider
answer, confirms the Reading, generates, and exports a book. Its receipt records the Reading, the
revision, the run and the export, and is sealed. It holds the photo's hash, never the photo. No
staging host is contacted: the API is the app under a TestClient, and the golden demo seed is
synthetic fixture data.

It runs beside spec 008's walkthrough, which still starts from the seeded Rig, with a receipt of
its own (decision 62). So Seam 2 is tested here, at the walkthrough and its receipt, rather than
through spec 008's receipt as T010 first set it.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from core import get_db, settings
from core.ops.f5_cutover import SeedAccount
from core.ops.photo_walkthrough import (
    photo_walkthrough_receipt,
    receipt_intact,
    run_photo_walkthrough,
)
from main import app

REPO = Path(__file__).resolve().parents[3]


def _seed_module():
    spec = importlib.util.spec_from_file_location(
        "seed_golden_demo_009", REPO / "scripts" / "seed_golden_demo.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def host(monkeypatch, tmp_path):
    """Staging as the walkthrough needs it: a recorded provider, and export fulfilment on."""
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    for name, value in {
        "photo_reading_provider": "recorded",
        "photo_reading_recordings_dir": str(recordings),
        "enable_patchbook_design_engine": True,
        "enable_canon_export_fulfillment": True,
        "enable_inline_export_fulfillment": True,
        "export_store_root": str(tmp_path),
        "export_dir": str(tmp_path),
        "download_token_secret": "x" * 40,
        "stripe_test_mode": True,
        "allow_production_payments": False,
        "environment": "staging",
    }.items():
        monkeypatch.setattr(settings, name, value)
    return recordings


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def seeded(db_session: Session):
    mod = _seed_module()
    result = mod.seed_golden_demo(db_session)
    user = SeedAccount(result.username, result.password, mod.DEMO_USER_ROLE)
    admin = SeedAccount(result.admin_username, result.admin_password, mod.DEMO_ADMIN_ROLE)
    # Every demo Module, as the seeded rig holds them, so generation has enough to patch.
    return user, admin, list(mod.MODULE_FIXTURES.values())


def _photo(fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (320, 120), (40, 30, 60)).save(buf, format=fmt)
    return buf.getvalue()


def _record(recordings: Path, photo: bytes, modules: list[dict]) -> None:
    """A recorded answer that names each Module by maker and model, so it fits any catalog."""
    sightings, start, width = [], 0, sum(m["hp"] for m in modules)
    for module in modules:
        sightings.append(
            {
                "box": {
                    "x": start / width,
                    "y": 0.05,
                    "w": module["hp"] / width,
                    "h": 0.9,
                },
                "kind": "module",
                "row_index": 0,
                "start_hp": start,
                "hp": module["hp"],
                "candidates": [{"maker": module["brand"], "name": module["name"], "score": 0.97}],
            }
        )
        start += module["hp"]
    payload = {"provider_version": "recorded-walkthrough-1", "sightings": sightings}
    (recordings / f"{hashlib.sha256(photo).hexdigest()}.json").write_text(json.dumps(payload))


def _steps(result: dict) -> list[str]:
    return [step["step"] for step in result["steps"]]


def test_a_photo_becomes_a_book_and_the_receipt_records_each_stage(
    client: TestClient, seeded, host: Path
) -> None:
    user, admin, modules = seeded
    photo = _photo()
    _record(host, photo, modules)

    result = run_photo_walkthrough(client, user=user, admin=admin, photo=photo, rows="0")
    receipt = photo_walkthrough_receipt(
        result,
        api="http://testserver",
        source_commit_sha="a" * 40,
        checked_at="2026-11-07T00:00:00Z",
    )

    assert result["outcome"] == "PASS", result["steps"]
    # It starts from the photo: the Reading is confirmed before generating, and the book after.
    steps = _steps(result)
    assert steps[:7] == [
        "login_user",
        "capability",
        "photo_start",
        "reading",
        "confirm",
        "generate",
        "export_sources",
    ]
    assert steps[7:] and all(step.startswith("book_") for step in steps[7:])
    reading = receipt["reading"]
    assert (reading["status"], reading["provider"], reading["provider_version"]) == (
        "read",
        "recorded",
        "recorded-walkthrough-1",
    )
    assert reading["photo_sha256"] == hashlib.sha256(photo).hexdigest()
    count = len(modules)
    assert reading["sightings"] == {
        "count": count,
        "kinds": {"module": count},
        "dispositions": {"auto_propose": count},
    }
    revision, run, export = receipt["revision"], receipt["run"], receipt["export"]
    assert revision["placements"] == count and revision["inventory_revision_id"]
    # The run is made from the revision the confirmation made.
    assert run["rig_revision_id"] == revision["rig_revision_id"]
    assert run["generated_count"] >= 1
    assert export["status"] == "succeeded"
    assert len(export["pack_zip_sha256"]) == 64
    assert receipt_intact(receipt)


def test_the_receipt_is_sealed_and_holds_no_secret_and_never_the_photo(
    client: TestClient, seeded, host: Path
) -> None:
    user, admin, modules = seeded
    photo = _photo()
    _record(host, photo, modules)

    result = run_photo_walkthrough(client, user=user, admin=admin, photo=photo, rows="0")
    receipt = photo_walkthrough_receipt(
        result,
        api="http://testserver",
        source_commit_sha="a" * 40,
        checked_at="2026-11-07T00:00:00Z",
    )

    text = json.dumps(receipt)
    assert user.password not in text and admin.password not in text
    assert "access_token" not in text and "Bearer" not in text
    # The photo's hash, never the photo: not as base64, as hex, or as a data URL.
    assert hashlib.sha256(photo).hexdigest() in text
    assert base64.b64encode(photo).decode()[:64] not in text
    assert photo.hex()[:64] not in text and "data:image" not in text
    for tampered in (
        {**receipt, "run": {**receipt["run"], "generated_count": 999}},
        {**receipt, "reading": {**receipt["reading"], "photo_sha256": "e" * 64}},
    ):
        assert not receipt_intact(tampered)


def test_a_photo_with_no_recording_fails_at_the_reading_and_goes_no_further(
    client: TestClient, seeded, host: Path
) -> None:
    user, admin, _ = seeded

    result = run_photo_walkthrough(client, user=user, admin=admin, photo=_photo(), rows="0")

    assert result["outcome"] == "FAIL"
    assert _steps(result)[-1] == "reading"
    assert result["steps"][-1]["code"] == "RECORDING_MISSING"
    assert "confirm" not in _steps(result) and "export" not in result


def test_a_host_that_reads_no_photos_fails_before_the_upload(
    client: TestClient, seeded, host: Path, monkeypatch
) -> None:
    user, admin, _ = seeded
    monkeypatch.setattr(settings, "photo_reading_provider", "disabled")

    result = run_photo_walkthrough(client, user=user, admin=admin, photo=_photo(), rows="0")

    assert result["outcome"] == "FAIL"
    assert _steps(result) == ["login_user", "capability"]
    assert result["steps"][-1]["code"] == "PROVIDER_DISABLED"


def test_a_book_that_never_arrives_fails_the_walkthrough(
    client: TestClient, seeded, host: Path, monkeypatch
) -> None:
    user, admin, modules = seeded
    photo = _photo()
    _record(host, photo, modules)
    # With nothing to fulfil it, the book is never made.
    monkeypatch.setattr(settings, "enable_inline_export_fulfillment", False)

    result = run_photo_walkthrough(client, user=user, admin=admin, photo=photo, rows="0")

    assert result["outcome"] == "FAIL"
    failed = result["steps"][-1]
    assert failed["step"].startswith("book_") and not failed["ok"]
    assert result["export"]["status"] != "succeeded"


def test_a_png_or_webp_fixture_is_uploaded_as_what_it_is(
    client: TestClient, seeded, host: Path
) -> None:
    user, admin, modules = seeded
    for fmt in ("PNG", "WEBP"):
        photo = _photo(fmt)
        _record(host, photo, modules)

        result = run_photo_walkthrough(client, user=user, admin=admin, photo=photo, rows="0")

        assert result["outcome"] == "PASS", (fmt, result["steps"])
