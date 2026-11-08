"""Spec 009 T022: NVIDIA reads a whole-Rig photo through the Clef adapter, in one answer.

The model names each candidate by maker and name, and PatchHive resolves those names to
catalog Modules. No test calls the network: every answer is a recorded chat completion
served through an ``httpx.MockTransport``.
"""

from __future__ import annotations

import base64
import io
import json
from typing import Any

import httpx
import pytest
from PIL import Image
from sqlalchemy.orm import Session

from evidence.nvidia_reading import NvidiaRigReader
from evidence.readings import (
    MAX_CANDIDATES,
    MAX_SIGHTINGS,
    CatalogNames,
    ReadingFailed,
    check_answer,
)
from intelligence.clef_provider import ClefAdapterState
from intelligence.nvidia_provider import DEFAULT_MODEL
from modules.models import Module

SHA = "c" * 64


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), (40, 30, 60)).save(buf, format="JPEG")
    return buf.getvalue()


def _completion(content: Any, *, finish: str = "stop") -> dict:
    text = content if isinstance(content, str) else json.dumps(content)
    return {
        "id": "chatcmpl-rig",
        "object": "chat.completion",
        "model": DEFAULT_MODEL,
        "choices": [
            {"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": text}}
        ],
    }


def _sighting(*candidates: tuple[str, str, float], kind: str = "module", start_hp: int = 0):
    return {
        "box": {"x": start_hp / 84, "y": 0.1, "w": 10 / 84, "h": 0.8},
        "kind": kind,
        "row_index": 0,
        "start_hp": start_hp,
        "hp": 10,
        "candidates": [{"maker": m, "name": n, "score": s} for m, n, s in candidates],
    }


def _reader(answer: Any = None, *, seen: list | None = None, status: int = 200, **kwargs):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        body = answer if isinstance(answer, dict) and "choices" in answer else _completion(answer)
        return httpx.Response(status, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    options = {"enabled": True, "api_key": "nvapi-test", "client": client, **kwargs}
    return NvidiaRigReader(**options)


def _module(db: Session, brand: str, name: str) -> Module:
    module = Module(brand=brand, name=name, module_type="VCO", hp=10, io_ports=[], source="test")
    db.add(module)
    db.commit()
    return module


# --- one call, every Sighting ----------------------------------------------------------------


def test_one_call_sends_the_photo_with_a_bounded_schema_and_names_become_catalog_modules(
    db_session: Session, sample_vco: Module, sample_vcf: Module
) -> None:
    seen: list[httpx.Request] = []
    reader = _reader(
        {
            "sightings": [
                # Case, spaces and punctuation don't matter to a name.
                _sighting(("test mfg", "Test VCO", 0.7), ("Test-Mfg", "test vcf", 0.2)),
                _sighting(kind="blank_panel", start_hp=10),
            ]
        },
        seen=seen,
    )

    answer = reader.answer(SHA, _jpeg(), rows=2, catalog=CatalogNames(db_session))

    assert len(seen) == 1
    sent = json.loads(seen[0].content)
    assert sent["model"] == DEFAULT_MODEL
    assert seen[0].headers["authorization"] == "Bearer nvapi-test"
    user = sent["messages"][1]["content"]
    assert "2 rows" in user[0]["text"]
    assert user[1]["image_url"]["url"] == (
        "data:image/jpeg;base64," + base64.b64encode(_jpeg()).decode()
    )
    schema = sent["response_format"]["json_schema"]["schema"]
    sightings = schema["properties"]["sightings"]
    assert sightings["maxItems"] == MAX_SIGHTINGS
    assert sightings["items"]["properties"]["candidates"]["maxItems"] == MAX_CANDIDATES
    assert answer["provider_version"] == DEFAULT_MODEL
    first, panel = answer["sightings"]
    assert first["candidates"] == [
        {"module_id": sample_vco.id, "score": 0.7},
        {"module_id": sample_vcf.id, "score": 0.2},
    ]
    assert (panel["kind"], panel["candidates"]) == ("blank_panel", [])
    check_answer(answer, rows=2)
    assert reader.last_state is ClefAdapterState.SUCCESS


def test_a_name_the_catalog_lacks_or_two_modules_share_is_dropped_never_guessed(
    db_session: Session, sample_vco: Module
) -> None:
    _module(db_session, "Twin Mfg", "Twin")
    _module(db_session, "Twin Mfg", "TWIN")
    reader = _reader(
        {
            "sightings": [
                _sighting(
                    ("Test Mfg", "Test VCO", 0.5),
                    ("Nobody", "Not In The Catalog", 0.3),
                    ("Twin Mfg", "Twin", 0.1),
                ),
                _sighting(("Nobody", "Nothing", 0.9), start_hp=10),
            ]
        }
    )

    answer = reader.answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))

    named, unnamed = answer["sightings"]
    assert named["candidates"] == [{"module_id": sample_vco.id, "score": 0.5}]
    # A Sighting left with no candidates stays a module the policy can't name.
    assert (unnamed["kind"], unnamed["candidates"]) == ("module", [])


def test_letters_in_any_script_count_and_punctuation_alone_names_nothing(
    db_session: Session,
) -> None:
    micro = _module(db_session, "Intellijel", "µScale")
    _module(db_session, "Intellijel", "Scale")
    _module(db_session, "Punct", "--")
    reader = _reader(
        {
            "sightings": [
                _sighting(("INTELLIJEL", "μ scale", 0.6)),
                _sighting(("Punct", "!!", 0.6), start_hp=10),
            ]
        }
    )

    micro_seen, punct = reader.answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))[
        "sightings"
    ]

    assert micro_seen["candidates"] == [{"module_id": micro.id, "score": 0.6}]
    assert punct["candidates"] == []


def test_a_maker_named_by_the_start_of_its_brand_is_found_unless_two_modules_fit(
    db_session: Session,
) -> None:
    plaits = _module(db_session, "Mutable Instruments", "Plaits")
    scale = _module(db_session, "Intellijel", "Quadrax")
    _module(db_session, "Twin Labs", "Twin")
    _module(db_session, "Twin Works", "Twin")
    reader = _reader(
        {
            "sightings": [
                _sighting(("Mutable", "Plaits", 0.6)),
                _sighting(("Intellijel Designs", "Quadrax", 0.6), start_hp=10),
                _sighting(("Twin", "Twin", 0.6), start_hp=20),
                _sighting(("Mutable Instruments", "Quadrax", 0.6), start_hp=30),
            ]
        }
    )

    found = reader.answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))["sightings"]

    assert [s["candidates"] for s in found] == [
        [{"module_id": plaits.id, "score": 0.6}],
        [{"module_id": scale.id, "score": 0.6}],
        [],
        [],
    ]


def test_two_names_for_one_module_add_up(db_session: Session, sample_vco: Module) -> None:
    reader = _reader(
        {"sightings": [_sighting(("Test Mfg", "Test VCO", 0.4), ("TEST MFG", "test-vco", 0.3))]}
    )

    (sighting,) = reader.answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))["sightings"]

    ((candidate),) = sighting["candidates"]
    assert candidate["module_id"] == sample_vco.id
    assert candidate["score"] == pytest.approx(0.7)


def test_a_retired_module_is_not_a_candidate(db_session: Session, sample_vco: Module) -> None:
    sample_vco.status = "tombstoned"
    db_session.commit()
    reader = _reader({"sightings": [_sighting(("Test Mfg", "Test VCO", 0.9))]})

    (sighting,) = reader.answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))["sightings"]

    assert sighting["candidates"] == []


# --- fail closed -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        _completion("not json"),
        _completion(["a", "list"]),
        _completion({"sightings": [{"kind": "module"}]}),
        _completion({"sightings": [_sighting(kind="cable")]}),
        _completion({"sightings": [_sighting(("A", "B", 0.7), ("C", "D", 0.6))]}),
        _completion({"sightings": [_sighting(("Test Mfg", "Test VCO", 0.9), kind="blank_panel")]}),
        _completion({"sightings": [], "disposition": "auto_propose"}),
        _completion({"sightings": []}, finish="length"),
        {"choices": []},
    ],
    ids=[
        "not-json",
        "not-an-object",
        "sighting-missing-fields",
        "unknown-kind",
        "scores-past-one",
        "panel-with-candidates",
        "provider-sets-a-disposition",
        "cut-off",
        "no-choice",
    ],
)
def test_a_malformed_answer_fails_the_reading(db_session: Session, body: dict) -> None:
    reader = _reader(body)

    with pytest.raises(ReadingFailed) as failed:
        reader.answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))

    assert failed.value.code == "ANSWER_MALFORMED"
    assert reader.last_state is ClefAdapterState.MALFORMED


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ({"sightings": [_sighting()] * (MAX_SIGHTINGS + 1)}, "TOO_MANY_SIGHTINGS"),
        (
            {"sightings": [_sighting(*[("M", f"N{i}", 0.1) for i in range(MAX_CANDIDATES + 1)])]},
            "TOO_MANY_CANDIDATES",
        ),
    ],
    ids=["sightings", "candidates"],
)
def test_an_oversized_answer_fails_the_reading(
    db_session: Session, answer: dict, code: str
) -> None:
    with pytest.raises(ReadingFailed) as failed:
        _reader(answer).answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))

    assert failed.value.code == code


def test_a_box_at_the_photos_edge_is_trimmed_and_one_far_past_it_fails(
    db_session: Session,
) -> None:
    edge = _sighting()
    edge["box"] = {"x": 0.92, "y": 0.0, "w": 0.09, "h": 1.0}
    past = _sighting()
    past["box"] = {"x": 0.92, "y": 0.0, "w": 0.2, "h": 1.0}

    (trimmed,) = _reader({"sightings": [edge]}).answer(
        SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session)
    )["sightings"]
    with pytest.raises(ReadingFailed) as failed:
        _reader({"sightings": [past]}).answer(
            SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session)
        )

    assert trimmed["box"]["w"] == pytest.approx(0.08)
    assert failed.value.code == "ANSWER_MALFORMED"


def test_a_disabled_reader_sends_nothing(db_session: Session) -> None:
    seen: list[httpx.Request] = []
    reader = _reader({"sightings": []}, seen=seen, enabled=False, api_key="")

    with pytest.raises(ReadingFailed) as failed:
        reader.answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))

    assert failed.value.code == "PROVIDER_DISABLED" and seen == []


def test_a_photo_past_the_adapters_size_is_never_sent(db_session: Session) -> None:
    seen: list[httpx.Request] = []

    with pytest.raises(ReadingFailed) as failed:
        _reader({"sightings": []}, seen=seen).answer(
            SHA, b"\xff" * (4 * 1024 * 1024 + 1), rows=1, catalog=CatalogNames(db_session)
        )

    assert failed.value.code == "PHOTO_TOO_LARGE" and seen == []


def test_an_empty_photo_is_unreadable_not_too_large(db_session: Session) -> None:
    with pytest.raises(ReadingFailed) as failed:
        _reader({"sightings": []}).answer(SHA, b"", rows=1, catalog=CatalogNames(db_session))

    assert failed.value.code == "PHOTO_UNREADABLE"


@pytest.mark.parametrize(
    ("error", "code", "state"),
    [
        (httpx.ReadTimeout("slow"), "PROVIDER_TIMED_OUT", ClefAdapterState.TIMEOUT),
        (httpx.ConnectError("down"), "PROVIDER_ERROR", ClefAdapterState.UNAVAILABLE),
        (RuntimeError("anything else"), "PROVIDER_ERROR", ClefAdapterState.UNAVAILABLE),
    ],
)
def test_a_transport_failure_fails_the_reading_with_only_a_code(
    db_session: Session, error: Exception, code: str, state: ClefAdapterState
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    client = httpx.Client(transport=httpx.MockTransport(handler))
    reader = NvidiaRigReader(enabled=True, api_key="nvapi-secret", client=client)

    with pytest.raises(ReadingFailed) as failed:
        reader.answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))

    assert failed.value.code == code and reader.last_state is state
    assert failed.value.__cause__ is None and "nvapi-secret" not in str(failed.value)


def test_a_refused_call_fails_the_reading(db_session: Session) -> None:
    with pytest.raises(ReadingFailed) as failed:
        _reader({"error": "unauthorized"}, status=401).answer(
            SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session)
        )

    assert failed.value.code == "PROVIDER_ERROR"


def test_construction_refuses_unpinned_models_and_missing_keys() -> None:
    with pytest.raises(ValueError):
        NvidiaRigReader(enabled=True, api_key="k", model="someone/else")
    with pytest.raises(ValueError):
        NvidiaRigReader(enabled=True, api_key="")


# --- a Reading, through the reader -----------------------------------------------------------


def _asset(db: Session, user, *, consent: bool):
    from datetime import datetime, timedelta, timezone

    from canon.models import ImageAssetRecord
    from racks.models import Rack

    rack = Rack(user_id=user.id, case_id=None, name="From a photo", tags=[])
    db.add(rack)
    db.flush()
    now = datetime.now(timezone.utc)
    asset = ImageAssetRecord(
        id=f"img-nvidia-rig-{consent}",
        rack_id=rack.id,
        user_id=user.id,
        content_sha256="d" * 64,
        media_type="image/jpeg",
        width=160,
        height=90,
        byte_length=100,
        storage_path="/dev/null",
        retention_days=30,
        retention_expires_at=now + timedelta(days=30),
        consent_provider_processing=consent,
        created_at=now,
    )
    db.add(asset)
    db.flush()
    return asset


def test_a_reading_through_nvidia_keeps_catalog_candidates_and_the_policys_dispositions(
    db_session: Session, sample_user, sample_vco: Module
) -> None:
    from canon.models import PhotoSightingRecord
    from evidence.readings import read_photo

    asset = _asset(db_session, sample_user, consent=True)
    reader = _reader(
        {
            "sightings": [
                _sighting(("Test Mfg", "Test VCO", 0.97)),
                _sighting(("Nobody", "Nothing", 0.9), start_hp=10),
            ]
        }
    )

    reading = read_photo(
        db_session, asset=asset, photo_sha256=SHA, image=_jpeg(), rows=(1, 1), provider=reader
    )

    assert (reading.status, reading.provider, reading.provider_version) == (
        "read",
        "nvidia",
        DEFAULT_MODEL,
    )
    sightings = (
        db_session.query(PhotoSightingRecord)
        .filter(PhotoSightingRecord.reading_id == reading.id)
        .order_by(PhotoSightingRecord.position)
        .all()
    )
    assert [(s.row_index, s.disposition) for s in sightings] == [
        (1, "auto_propose"),
        (1, "unresolved"),
    ]
    assert sightings[0].candidates == [{"module_id": sample_vco.id, "score": 0.97}]


def test_a_photo_the_owner_kept_from_providers_is_never_sent(
    db_session: Session, sample_user
) -> None:
    from evidence.readings import read_photo

    seen: list[httpx.Request] = []
    asset = _asset(db_session, sample_user, consent=False)

    reading = read_photo(
        db_session,
        asset=asset,
        photo_sha256=SHA,
        image=_jpeg(),
        rows=(0, 0),
        provider=_reader({"sightings": []}, seen=seen),
    )

    assert (reading.status, reading.reason_code) == ("failed", "CONSENT_NOT_GRANTED")
    assert seen == []


def test_the_configured_reader_uses_the_hosts_model_address_and_photo_timeout(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import core.config as config_mod
    import evidence.nvidia_reading as nvidia_reading
    from evidence.readings import configured_provider
    from intelligence.nvidia_provider import NVIDIA_MODELS

    for name, value in {
        "photo_reading_provider": "nvidia",
        "enable_nvidia_provider": True,
        "nvidia_api_key": "nvapi-host",
        "nvidia_model": NVIDIA_MODELS[-1],
        "nvidia_base_url": "https://nvidia.example/v1",
        "nvidia_timeout_seconds": 20.0,
        "photo_reading_timeout_seconds": 150.0,
    }.items():
        monkeypatch.setattr(config_mod.settings, name, value)
    sent: dict = {}

    def post_chat(client, **call):
        sent.update(call)
        return _completion({"sightings": []})

    monkeypatch.setattr(nvidia_reading, "post_chat", post_chat)

    answer = configured_provider().answer(SHA, _jpeg(), rows=1, catalog=CatalogNames(db_session))

    assert answer == {"provider_version": NVIDIA_MODELS[-1], "sightings": []}
    assert (sent["base_url"], sent["api_key"], sent["timeout"]) == (
        "https://nvidia.example/v1",
        "nvapi-host",
        150.0,
    )
    assert sent["payload"]["model"] == NVIDIA_MODELS[-1]
