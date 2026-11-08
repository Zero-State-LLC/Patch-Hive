"""Offline tests for scripts/staging/photo_walkthrough.py and staging's photo-reading config
(spec 009 T060a). The walkthrough itself runs in-process in
``tests/integration/test_009_photo_walkthrough.py``; nothing here contacts a host."""

from __future__ import annotations

import hashlib
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from tests.edge_config import edge_source, wrangler

ROOT = Path(__file__).resolve().parents[3]
_spec = spec_from_file_location(
    "photo_walkthrough_script", ROOT / "scripts" / "staging" / "photo_walkthrough.py"
)
assert _spec and _spec.loader
script = module_from_spec(_spec)
sys.modules["photo_walkthrough_script"] = script
_spec.loader.exec_module(script)

STAGING = "https://api-staging.patch-hive.com"


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch):
    def set_(api: str = STAGING, user: str = "pw-user", admin: str = "pw-admin") -> None:
        monkeypatch.setenv("STAGING_API_URL", api)
        monkeypatch.setenv("PATCHHIVE_DEMO_USER_PASSWORD", user)
        monkeypatch.setenv("PATCHHIVE_DEMO_ADMIN_PASSWORD", admin)

    return set_


def _photo(tmp_path: Path) -> Path:
    photo = tmp_path / "rig.jpg"
    photo.write_bytes(b"\xff\xd8 a fixture photo \xff\xd9")
    return photo


@pytest.fixture(autouse=True)
def fixtures_here(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The temp folder stands in for fixtures/photo-walkthrough."""
    monkeypatch.setattr(script, "FIXTURES", tmp_path)


def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args, **kwargs):
        raise AssertionError("the walkthrough must refuse before contacting a host")

    monkeypatch.setattr(script, "run_photo_walkthrough", refuse)


def test_a_recording_is_found_by_the_photos_sha256(tmp_path: Path) -> None:
    photo = _photo(tmp_path)
    recordings = tmp_path / "recordings"
    recordings.mkdir()
    assert script.recording_for(photo, recordings) is None

    named = recordings / f"{hashlib.sha256(photo.read_bytes()).hexdigest()}.json"
    named.write_text("{}")

    assert script.recording_for(photo, recordings) == named


@pytest.mark.parametrize(
    "setting",
    [
        {"api": "https://api.patch-hive.com"},
        {"api": "http://localhost:8000"},
        {"user": ""},
        {"admin": ""},
    ],
    ids=["production", "local", "no-user-password", "no-admin-password"],
)
def test_it_refuses_anything_but_staging_with_the_demo_passwords(
    tmp_path: Path, env, monkeypatch: pytest.MonkeyPatch, setting: dict
) -> None:
    env(**setting)
    _no_network(monkeypatch)

    code = script.main(
        ["--photo", str(_photo(tmp_path)), "--receipt-out", str(tmp_path / "r.json")]
    )

    assert code == 2 and not (tmp_path / "r.json").exists()


def test_it_refuses_a_missing_photo_or_one_with_no_recording_in_the_repo(
    tmp_path: Path, env, monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    _no_network(monkeypatch)
    monkeypatch.setattr(script, "RECORDINGS", tmp_path / "recordings")
    receipt = str(tmp_path / "r.json")

    assert script.main(["--photo", str(tmp_path / "absent.jpg"), "--receipt-out", receipt]) == 2
    assert script.main(["--photo", str(_photo(tmp_path)), "--receipt-out", receipt]) == 2


def test_it_refuses_a_photo_from_outside_the_fixtures_folder(
    tmp_path: Path, env, monkeypatch: pytest.MonkeyPatch
) -> None:
    env()
    _no_network(monkeypatch)
    elsewhere = tmp_path / "fixtures"
    elsewhere.mkdir()
    monkeypatch.setattr(script, "FIXTURES", elsewhere)
    # The photo and its recording are both there, so only the folder can refuse it.
    photo = _photo(tmp_path)
    monkeypatch.setattr(script, "RECORDINGS", tmp_path)
    (tmp_path / f"{hashlib.sha256(photo.read_bytes()).hexdigest()}.json").write_text("{}")

    code = script.main(
        ["--photo", str(_photo(tmp_path)), "--receipt-out", str(tmp_path / "r.json")]
    )

    assert code == 2


def test_staging_replays_recordings_shipped_in_the_image() -> None:
    staging = wrangler()["env"]["staging"]["vars"]
    assert staging["PHOTO_READING_PROVIDER"] == "recorded"
    # The API image copies backend/ to /app (backend/Dockerfile), so the folder ships with it.
    assert staging["PHOTO_READING_RECORDINGS_DIR"] == "/app/data/photo-readings"
    assert (ROOT / "backend" / "data" / "photo-readings").is_dir()
    flag_vars = edge_source().split("const FLAG_VARS = [", 1)[1].split("] as const;", 1)[0]
    assert '"PHOTO_READING_PROVIDER"' in flag_vars
    assert '"PHOTO_READING_RECORDINGS_DIR"' in flag_vars
