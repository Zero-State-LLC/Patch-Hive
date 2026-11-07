"""Spec 009 T010, Seam 1: the photo-to-book journey over HTTP, with a recorded provider answer.

The tests drive the API from outside and check what a person or a later step can see: the
Reading and its Sightings, the new Rig revision and its placements, readiness, the run, and the
book. Nothing here is built yet, so each journey test is a strict xfail that names the ticket
that builds its step. It fails on an assertion about missing behavior, and a setup error still
fails the run. When a ticket lands, its marker comes off. The last test is the manual path's
book: it passes today, and it guards the step the journey ends on.

Contracts these tests set, which spec 009 leaves to its tickets:

- `GET /api/evidence/photo-reading` answers `{"available": bool, "reason": str | None}`.
- `POST /api/evidence/rig-photos` takes a `file` and the `rows` it covers ("0", or "0-1"), and an
  optional `rig_id`. It creates the Rig, with no Case, when `rig_id` is absent. It answers 201
  with `rig_id`, `photo_id` and `reading_id`, or 409 `PHOTO_READING_UNAVAILABLE` and stores
  nothing.
- `GET /api/racks/{rig_id}/evidence/readings` lists the Rig's Readings with their Sightings.
- `POST /api/racks/{rig_id}/evidence/readings/confirm` takes `items` (each a `sighting_id`,
  `module_id`, `row_index` and `start_hp`), `added`, `excluded` and an optional `case_id`. It
  answers 201 with `rig_revision_id`, `ready_for_generation` and `placements`, or 409 with
  `{"code": ..., "modules": [...]}` and writes nothing.
- The recorded provider is `photo_reading_provider = "recorded"` (T020 adds the setting, default
  `disabled`; T021 makes it read). Its answers live in
  `photo_reading_recordings_dir`, one `<photo sha256>.json` per photo, holding
  `provider_version` and `sightings`.

Writes stay off the canon alias, which spec 008's cutover audit keeps read-only.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from canon.models import CanonicalCreditLedgerEntryRecord, ImageAssetRecord
from community.models import User
from main import app
from modules.models import Module
from racks.models import Rack
from tests.conftest import bearer_headers

T020 = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="spec 009 T020: a Rig starts from a photo"
)
T021 = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="spec 009 T021: Readings and Sightings"
)
T030 = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="spec 009 T030: confirming a Reading"
)
T040 = pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="spec 009 T040: the photo-reading capability"
)

DISPOSITIONS = {"auto_propose", "user_review", "unresolved"}
KINDS = {"module", "blank_panel", "unknown", "not_eurorack"}


# --- helpers ---------------------------------------------------------------------------------


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

    for name, value in {
        "export_dir": str(tmp_path),
        "export_store_root": str(tmp_path),
        "download_token_secret": "x" * 40,
        "secret_key": "y" * 40,
    }.items():
        monkeypatch.setattr(config_mod.settings, name, value)
    return tmp_path


def _photo(shade: int = 40) -> bytes:
    """A small JPEG. Each shade hashes differently, so each photo gets its own recording."""
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (shade, 30, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def _sha(photo: bytes) -> str:
    return hashlib.sha256(photo).hexdigest()


def _open_reading(monkeypatch: pytest.MonkeyPatch, recordings: Path) -> None:
    """Turn photo reading on with the recorded provider, as the tests and the walkthrough do."""
    from core.config import Settings, settings

    fields = Settings.model_fields
    assert "photo_reading_provider" in fields and "photo_reading_recordings_dir" in fields, (
        "spec 009 T020: settings have no photo-reading provider yet"
    )
    monkeypatch.setattr(settings, "photo_reading_provider", "recorded")
    monkeypatch.setattr(settings, "photo_reading_recordings_dir", str(recordings))


def _record(recordings: Path, photo: bytes, sightings: list[dict]) -> None:
    recordings.mkdir(parents=True, exist_ok=True)
    payload = {"provider_version": "recorded-1", "sightings": sightings}
    (recordings / f"{_sha(photo)}.json").write_text(json.dumps(payload))


def _sighting(module: Module | None, start_hp: int, hp: int, *, kind: str = "module", candidates=None):
    x = start_hp / 84
    return {
        "box": {"x": round(x, 4), "y": 0.1, "w": round(hp / 84, 4), "h": 0.8},
        "kind": kind,
        "row_index": 0,
        "start_hp": start_hp,
        "hp": hp,
        "candidates": candidates
        if candidates is not None
        else ([{"module_id": module.id, "score": 0.93}] if module else []),
    }


def _upload(client: TestClient, user: User | None, photo: bytes, *, rows: str = "0"):
    headers = bearer_headers(user) if user else {}
    return client.post(
        "/api/evidence/rig-photos",
        files={"file": ("rig.jpg", photo, "image/jpeg")},
        data={"rows": rows},
        headers=headers,
    )


def _readings(client: TestClient, user: User, rig_id: int) -> list[dict]:
    """The Rig's Readings, once none is still `reading`."""
    for _ in range(20):
        answer = client.get(f"/api/racks/{rig_id}/evidence/readings", headers=bearer_headers(user))
        assert answer.status_code == 200, f"spec 009 T021: no readings route ({answer.status_code})"
        readings = answer.json()["readings"]
        if all(r["status"] != "reading" for r in readings):
            return readings
    raise AssertionError("spec 009 T021: a Reading never left `reading`")


def _rigs(db: Session) -> int:
    return db.query(Rack).count()


def _grant(db: Session, user: User, credits: int = 10) -> None:
    db.add(
        CanonicalCreditLedgerEntryRecord(
            id=f"grant-009-{user.id}",
            user_id=user.id,
            delta=credits,
            entry_type="grant",
            idempotency_key=f"grant-009-{user.id}",
            export_id=None,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def _book_module_names(
    client: TestClient, user: User, rig_id: int, monkeypatch: pytest.MonkeyPatch
) -> set[str]:
    """Generate a run for the Rig, export its book with inline fulfilment, and return every
    Module name the book's pages print."""
    import core.config as config_mod

    for name in (
        "enable_canon_export_fulfillment",
        "enable_inline_export_fulfillment",
        "enable_patchbook_design_engine",
    ):
        monkeypatch.setattr(config_mod.settings, name, True)
    headers = bearer_headers(user)
    generated = client.post(f"/api/patches/generate/{rig_id}", json={}, headers=headers)
    assert generated.status_code == 200, generated.text
    run = generated.json()
    assert run["generation_status"] == "OK" and run["generated_count"] > 0, run
    export = client.post(
        "/api/canon/exports",
        json={
            "source_run_id": run["source_run_id"],
            "source_rig_revision_id": run["rig_revision_id"],
            "artifact_manifest_hash": run["artifact_manifest_hash"],
            "formats": ["pdf", "json"],
            "license": "personal",
            "idempotency_key": f"spec-009-book-{rig_id}",
        },
        headers=headers,
    )
    assert export.status_code == 201, export.text
    assert export.json()["status"] == "succeeded", export.json()
    export_id = export.json()["export_id"]
    token = client.post(
        f"/api/canon/exports/{export_id}/download-token", json={"ttl_seconds": 120}, headers=headers
    ).json()["token"]
    pack = client.get(
        f"/api/canon/exports/{export_id}/artifacts/zip", params={"token": token}, headers=headers
    )
    assert pack.status_code == 200
    names: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(pack.content)) as archive:
        for entry in archive.namelist():
            if entry.startswith("pages/json/") and entry.endswith(".json"):
                names.update(json.loads(archive.read(entry)).get("modules", {}).values())
    assert names, "the book printed no Module names"
    return names


def _label(module: Module) -> str:
    return f"{module.brand} {module.name}"


@pytest.fixture
def shelf(sample_vco, sample_vcf, sample_vca, sample_envelope, sample_lfo) -> dict[str, Module]:
    """Catalog Modules the recorded Readings match against."""
    return {
        "vco": sample_vco,
        "vcf": sample_vcf,
        "vca": sample_vca,
        "adsr": sample_envelope,
        "lfo": sample_lfo,
    }


def _rig_photo_sightings(shelf: dict[str, Module]) -> list[dict]:
    """One row, as a whole-rig photo reads: three Modules to keep, the second misread as an LFO,
    an ADSR the owner leaves out, and a Blank Panel."""
    return [
        _sighting(shelf["vco"], 0, 10),
        _sighting(
            None,
            10,
            8,
            candidates=[
                {"module_id": shelf["lfo"].id, "score": 0.55},
                {"module_id": shelf["vcf"].id, "score": 0.40},
            ],
        ),
        _sighting(shelf["vca"], 18, 6),
        _sighting(shelf["adsr"], 24, 8),
        _sighting(None, 32, 4, kind="blank_panel"),
    ]


def _confirm_body(shelf: dict[str, Module], readings: list[dict]) -> dict:
    sightings = readings[0]["sightings"]
    keep = {0: shelf["vco"], 1: shelf["vcf"], 2: shelf["vca"]}
    return {
        "items": [
            {
                "sighting_id": sightings[i]["sighting_id"],
                "module_id": module.id,
                "row_index": sightings[i]["row_index"],
                "start_hp": sightings[i]["start_hp"],
            }
            for i, module in keep.items()
        ],
        "added": [],
        "excluded": [sightings[3]["sighting_id"]],
        "case_id": None,
    }


# --- the capability (T040) -------------------------------------------------------------------


@T040
def test_photo_reading_is_closed_by_default_and_a_closed_host_stores_nothing(
    client: TestClient, db_session: Session, sample_user: User, storage: Path
) -> None:
    answer = client.get("/api/evidence/photo-reading")
    assert answer.status_code == 200, "spec 009 T040: no photo-reading capability route"
    assert answer.json()["available"] is False
    assert answer.json()["reason"]
    rigs = _rigs(db_session)

    refused = _upload(client, sample_user, _photo())

    assert refused.status_code == 409
    assert refused.json()["detail"] == "PHOTO_READING_UNAVAILABLE"
    assert _rigs(db_session) == rigs
    assert db_session.query(ImageAssetRecord).count() == 0


# --- starting a Rig from a photo (T020) ------------------------------------------------------


@T020
def test_a_signed_out_visitor_cannot_upload_a_rig_photo(
    client: TestClient, db_session: Session, storage: Path
) -> None:
    rigs = _rigs(db_session)

    answer = _upload(client, None, _photo())

    assert answer.status_code == 401, f"spec 009 T020: no photo start route ({answer.status_code})"
    assert _rigs(db_session) == rigs


@T020
def test_a_rig_starts_from_a_photo_with_no_case(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    shelf: dict[str, Module],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recordings = storage / "recordings"
    _open_reading(monkeypatch, recordings)
    photo = _photo()
    _record(recordings, photo, _rig_photo_sightings(shelf))

    started = _upload(client, sample_user, photo)

    assert started.status_code == 201, started.text
    body = started.json()
    assert {"rig_id", "photo_id"} <= set(body)
    rig = client.get(f"/api/canon/rigs/{body['rig_id']}", headers=bearer_headers(sample_user))
    assert rig.status_code == 200
    assert rig.json().get("case") is None and rig.json().get("case_id") is None
    images = client.get(
        f"/api/racks/{body['rig_id']}/evidence/images", headers=bearer_headers(sample_user)
    )
    assert images.json()["total"] == 1


# --- Readings and Sightings (T021) -----------------------------------------------------------


@T021
def test_a_reading_replays_its_recorded_answer_as_bounded_sightings(
    client: TestClient,
    sample_user: User,
    shelf: dict[str, Module],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recordings = storage / "recordings"
    _open_reading(monkeypatch, recordings)
    photo = _photo()
    _record(recordings, photo, _rig_photo_sightings(shelf))
    started = _upload(client, sample_user, photo)
    assert started.status_code == 201, f"spec 009 T020: no photo start ({started.status_code})"

    (reading,) = _readings(client, sample_user, started.json()["rig_id"])

    assert reading["status"] == "read"
    assert reading["provider"] == "recorded" and reading["provider_version"] == "recorded-1"
    assert reading["photo_sha256"] == _sha(photo)
    assert reading["policy_version"]
    sightings = reading["sightings"]
    assert [s["start_hp"] for s in sightings] == [0, 10, 18, 24, 32]
    for sighting in sightings:
        assert sighting["sighting_id"]
        assert sighting["kind"] in KINDS
        assert sighting["disposition"] in DISPOSITIONS
        assert len(sighting["candidates"]) <= 5
        box = sighting["box"]
        assert 0 <= box["x"] <= 1 and 0 <= box["y"] <= 1 and 0 < box["w"] <= 1 and 0 < box["h"] <= 1
    assert sightings[4]["kind"] == "blank_panel" and sightings[4]["candidates"] == []
    # The misread one: the policy, not the provider, decides it needs the owner.
    assert sightings[1]["disposition"] != "auto_propose"


@T021
@pytest.mark.parametrize(
    "recording",
    ["missing", "malformed", "too_many_candidates"],
)
def test_a_reading_fails_closed_and_nothing_reaches_inventory(
    client: TestClient,
    sample_user: User,
    shelf: dict[str, Module],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
    recording: str,
) -> None:
    recordings = storage / "recordings"
    _open_reading(monkeypatch, recordings)
    photo = _photo(70)
    if recording == "malformed":
        recordings.mkdir(parents=True, exist_ok=True)
        (recordings / f"{_sha(photo)}.json").write_text("{not json")
    elif recording == "too_many_candidates":
        crowd = [{"module_id": m.id, "score": 0.1} for m in shelf.values()]
        crowd.append({"module_id": shelf["vco"].id, "score": 0.05})
        _record(recordings, photo, [_sighting(None, 0, 10, candidates=crowd)])
    started = _upload(client, sample_user, photo)
    assert started.status_code == 201, f"spec 009 T020: no photo start ({started.status_code})"
    rig_id = started.json()["rig_id"]

    (reading,) = _readings(client, sample_user, rig_id)

    assert reading["status"] == "failed"
    assert reading["reason_code"]
    assert reading["sightings"] == []
    inventory = client.get(
        f"/api/racks/{rig_id}/evidence/inventory", headers=bearer_headers(sample_user)
    ).json()
    assert inventory["latest"] is None or inventory["latest"]["confirmed_count"] == 0


# --- confirming a Reading (T030) -------------------------------------------------------------


def _read_rig(client, user, shelf, storage, monkeypatch) -> tuple[int, list[dict]]:
    recordings = storage / "recordings"
    _open_reading(monkeypatch, recordings)
    photo = _photo()
    _record(recordings, photo, _rig_photo_sightings(shelf))
    started = _upload(client, user, photo)
    assert started.status_code == 201, f"spec 009 T020: no photo start ({started.status_code})"
    rig_id = started.json()["rig_id"]
    return rig_id, _readings(client, user, rig_id)


@T030
def test_confirming_a_reading_counts_its_positions_as_placement(
    client: TestClient,
    sample_user: User,
    shelf: dict[str, Module],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig_id, readings = _read_rig(client, sample_user, shelf, storage, monkeypatch)
    headers = bearer_headers(sample_user)

    confirmed = client.post(
        f"/api/racks/{rig_id}/evidence/readings/confirm",
        json=_confirm_body(shelf, readings),
        headers=headers,
    )

    assert confirmed.status_code == 201, f"spec 009 T030: no confirm ({confirmed.status_code})"
    body = confirmed.json()
    assert body["rig_revision_id"]
    assert body["ready_for_generation"] is True
    expected = [
        (shelf["vco"].id, 0, 0),
        (shelf["vcf"].id, 0, 10),
        (shelf["vca"].id, 0, 18),
    ]
    assert sorted((p["module_id"], p["row_index"], p["start_hp"]) for p in body["placements"]) == expected
    rig = client.get(f"/api/canon/rigs/{rig_id}", headers=headers).json()
    assert sorted((m["module_id"], m["row_index"], m["start_hp"]) for m in rig["modules"]) == expected
    inventory = client.get(f"/api/racks/{rig_id}/evidence/inventory", headers=headers).json()
    assert inventory["modules_to_place"] == []
    assert inventory["latest"]["ready_for_generation"] is True


@T030
def test_confirm_refuses_an_overlap_names_the_modules_and_writes_nothing(
    client: TestClient,
    sample_user: User,
    shelf: dict[str, Module],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig_id, readings = _read_rig(client, sample_user, shelf, storage, monkeypatch)
    headers = bearer_headers(sample_user)
    body = _confirm_body(shelf, readings)
    body["items"][1]["start_hp"] = 4  # the VCF now overlaps the VCO's 10 HP

    refused = client.post(
        f"/api/racks/{rig_id}/evidence/readings/confirm", json=body, headers=headers
    )

    assert refused.status_code == 409, f"spec 009 T030: no confirm ({refused.status_code})"
    assert refused.json()["detail"]["code"] == "POSITIONS_OVERLAP"
    assert sorted(refused.json()["detail"]["modules"]) == sorted([shelf["vco"].id, shelf["vcf"].id])
    assert client.get(f"/api/canon/rigs/{rig_id}", headers=headers).json()["modules"] == []
    inventory = client.get(f"/api/racks/{rig_id}/evidence/inventory", headers=headers).json()
    assert inventory["latest"] is None or inventory["latest"]["confirmed_count"] == 0


@T030
def test_the_journey_ends_in_a_book_of_exactly_the_confirmed_modules(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    shelf: dict[str, Module],
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rig_id, readings = _read_rig(client, sample_user, shelf, storage, monkeypatch)
    confirmed = client.post(
        f"/api/racks/{rig_id}/evidence/readings/confirm",
        json=_confirm_body(shelf, readings),
        headers=bearer_headers(sample_user),
    )
    assert confirmed.status_code == 201, f"spec 009 T030: no confirm ({confirmed.status_code})"
    _grant(db_session, sample_user)

    printed = _book_module_names(client, sample_user, rig_id, monkeypatch)

    kept = {_label(shelf[key]) for key in ("vco", "vcf", "vca")}
    assert printed <= kept
    assert _label(shelf["adsr"]) not in printed and _label(shelf["lfo"]) not in printed


# --- the step the journey ends on, as it works today ----------------------------------------


def test_the_manual_path_book_prints_only_placed_modules(
    client: TestClient,
    db_session: Session,
    sample_user: User,
    sample_rack_basic: Rack,
    sample_envelope: Module,
    storage: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Spec 009 ends where the manual path ends today: a book that prints only the Rig's
    Modules. This guards that end, and the helper the journey test uses to read it."""
    _grant(db_session, sample_user)

    printed = _book_module_names(client, sample_user, sample_rack_basic.id, monkeypatch)

    placed = {_label(rm.module) for rm in sample_rack_basic.modules}
    assert printed and printed <= placed
    assert _label(sample_envelope) not in printed


def test_the_reads_the_journey_checks_answer_today(
    client: TestClient, sample_user: User, sample_rack_basic: Rack
) -> None:
    """The journey tests read placements from the rig detail and readiness from the inventory.
    Both answer today, so a journey test that fails there fails on the behavior, not the read."""
    headers = bearer_headers(sample_user)

    rig = client.get(f"/api/canon/rigs/{sample_rack_basic.id}", headers=headers)
    inventory = client.get(f"/api/racks/{sample_rack_basic.id}/evidence/inventory", headers=headers)

    assert rig.status_code == 200 and "case" in rig.json()
    assert {"module_id", "row_index", "start_hp"} <= set(rig.json()["modules"][0])
    assert inventory.status_code == 200
    assert {"latest", "modules_to_place"} <= set(inventory.json())
