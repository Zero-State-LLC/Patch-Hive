"""Spec 009 T021: a Reading keeps a provider's answer only when it is bounded, and the
DecisionPolicy, not the provider, sets each Sighting's disposition."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from canon.models import ImageAssetRecord, PhotoReadingRecord, PhotoSightingRecord
from community.models import User
from evidence.readings import ReadingFailed, move_readings, read_photo
from modules.models import Module
from racks.models import Rack

SHA = "a" * 64


class _Answers:
    """A provider that gives one fixed answer, or raises."""

    name = "recorded"

    def __init__(self, answer: object = None, raises: BaseException | None = None) -> None:
        self._answer, self._raises = answer, raises

    def answer(self, photo_sha256: str, image: bytes) -> object:
        if self._raises:
            raise self._raises
        return self._answer


@pytest.fixture
def asset(db_session: Session, sample_user: User) -> ImageAssetRecord:
    rack = Rack(user_id=sample_user.id, case_id=None, name="From a photo", tags=[])
    db_session.add(rack)
    db_session.flush()
    now = datetime.now(timezone.utc)
    record = ImageAssetRecord(
        id="img-reading-test",
        rack_id=rack.id,
        user_id=sample_user.id,
        content_sha256="b" * 64,
        media_type="image/jpeg",
        width=160,
        height=90,
        byte_length=100,
        storage_path="/dev/null",
        retention_days=30,
        retention_expires_at=now + timedelta(days=30),
        consent_provider_processing=False,
        created_at=now,
    )
    db_session.add(record)
    db_session.flush()
    return record


def _sighting(
    start_hp: int = 0, hp: int = 10, *, kind: str = "module", candidates=(), row=0, box=None
):
    return {
        "box": box or {"x": start_hp / 84, "y": 0.1, "w": hp / 84, "h": 0.8},
        "kind": kind,
        "row_index": row,
        "start_hp": start_hp,
        "hp": hp,
        "candidates": list(candidates),
    }


def _read(db: Session, asset: ImageAssetRecord, provider, rows=(0, 0)) -> PhotoReadingRecord:
    return read_photo(db, asset=asset, photo_sha256=SHA, image=b"", rows=rows, provider=provider)


def _sightings(db: Session, reading: PhotoReadingRecord) -> list[PhotoSightingRecord]:
    return (
        db.query(PhotoSightingRecord)
        .filter(PhotoSightingRecord.reading_id == reading.id)
        .order_by(PhotoSightingRecord.position)
        .all()
    )


# --- dispositions come from the policy -------------------------------------------------------


def test_the_policy_sets_each_disposition_from_the_candidates(
    db_session: Session, asset: ImageAssetRecord, sample_vco: Module, sample_vcf: Module
) -> None:
    answer = {
        "provider_version": "recorded-1",
        "sightings": [
            _sighting(0, candidates=[{"module_id": sample_vco.id, "score": 0.95}]),
            _sighting(10, candidates=[{"module_id": sample_vcf.id, "score": 0.70}]),
            _sighting(20, candidates=[{"module_id": sample_vco.id, "score": 0.30}]),
            _sighting(30, hp=4, kind="blank_panel"),
            _sighting(34, kind="unknown"),
        ],
    }

    reading = _read(db_session, asset, _Answers(answer))

    assert reading.status == "read" and reading.reason_code is None
    assert reading.provider_version == "recorded-1"
    assert [s.disposition for s in _sightings(db_session, reading)] == [
        "auto_propose",
        "user_review",
        "unresolved",
        "unresolved",
        "unresolved",
    ]


def test_a_photo_of_later_rows_counts_its_rows_in_the_rigs(
    db_session: Session, asset: ImageAssetRecord, sample_vco: Module
) -> None:
    answer = {
        "provider_version": "recorded-1",
        "sightings": [_sighting(0, row=0), _sighting(0, row=1)],
    }

    reading = _read(db_session, asset, _Answers(answer), rows=(1, 2))

    assert [s.row_index for s in _sightings(db_session, reading)] == [1, 2]
    assert (reading.first_row, reading.last_row) == (1, 2)


# --- what fails a Reading closed -------------------------------------------------------------


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ({"sightings": []}, "ANSWER_MALFORMED"),
        ({"provider_version": "r", "sightings": [{"kind": "module"}]}, "ANSWER_MALFORMED"),
        ({"provider_version": "r", "sightings": [], "extra": 1}, "ANSWER_MALFORMED"),
        ("not an object", "ANSWER_MALFORMED"),
        (
            {
                "provider_version": "r",
                "sightings": [_sighting(80, hp=10, box={"x": 0.95, "y": 0, "w": 0.1, "h": 1})],
            },
            "ANSWER_MALFORMED",
        ),
        ({"provider_version": "r", "sightings": [_sighting(row=1)]}, "ROW_OUTSIDE_PHOTO"),
        ({"provider_version": "r", "sightings": [_sighting()] * 201}, "TOO_MANY_SIGHTINGS"),
    ],
)
def test_an_answer_past_its_bounds_fails_the_reading_and_keeps_no_sightings(
    db_session: Session, asset: ImageAssetRecord, answer: object, code: str
) -> None:
    reading = _read(db_session, asset, _Answers(answer))

    assert (reading.status, reading.reason_code) == ("failed", code)
    assert _sightings(db_session, reading) == []


def test_candidates_must_be_a_bounded_distribution_of_catalog_modules(
    db_session: Session, asset: ImageAssetRecord, sample_vco: Module, sample_vcf: Module
) -> None:
    vco, vcf = sample_vco.id, sample_vcf.id
    cases = {
        "TOO_MANY_CANDIDATES": [{"module_id": vco + i, "score": 0.1} for i in range(6)],
        "ANSWER_MALFORMED": [{"module_id": vco, "score": 0.6}, {"module_id": vcf, "score": 0.6}],
        "CANDIDATE_NOT_IN_CATALOG": [{"module_id": 999_999, "score": 0.9}],
    }
    for code, candidates in cases.items():
        answer = {"provider_version": "r", "sightings": [_sighting(candidates=candidates)]}
        assert _read(db_session, asset, _Answers(answer)).reason_code == code
    repeated = [{"module_id": vco, "score": 0.4}, {"module_id": vco, "score": 0.4}]
    answer = {"provider_version": "r", "sightings": [_sighting(candidates=repeated)]}
    assert _read(db_session, asset, _Answers(answer)).reason_code == "ANSWER_MALFORMED"
    panel = [{"module_id": vco, "score": 0.9}]
    answer = {
        "provider_version": "r",
        "sightings": [_sighting(kind="blank_panel", candidates=panel)],
    }
    assert _read(db_session, asset, _Answers(answer)).reason_code == "ANSWER_MALFORMED"


@pytest.mark.parametrize(
    ("raises", "code"),
    [
        (ReadingFailed("RECORDING_MISSING"), "RECORDING_MISSING"),
        (TimeoutError(), "PROVIDER_TIMED_OUT"),
        (RuntimeError("bug"), "PROVIDER_ERROR"),
    ],
)
def test_a_provider_that_cannot_answer_fails_the_reading(
    db_session: Session, asset: ImageAssetRecord, raises: BaseException, code: str
) -> None:
    reading = _read(db_session, asset, _Answers(raises=raises))

    assert (reading.status, reading.reason_code) == ("failed", code)
    assert reading.completed_at is not None


@pytest.mark.parametrize(
    ("setting", "code"),
    [("disabled", "PROVIDER_DISABLED"), ("nvidia", "PROVIDER_UNAVAILABLE")],
)
def test_a_provider_that_is_off_or_not_wired_fails_the_reading(
    db_session: Session,
    asset: ImageAssetRecord,
    monkeypatch: pytest.MonkeyPatch,
    setting: str,
    code: str,
) -> None:
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "photo_reading_provider", setting)

    reading = read_photo(db_session, asset=asset, photo_sha256=SHA, image=b"", rows=(0, 0))

    assert (reading.status, reading.reason_code, reading.provider) == ("failed", code, setting)


def test_the_recorded_provider_without_a_directory_fails_the_reading(
    db_session: Session, asset: ImageAssetRecord, monkeypatch: pytest.MonkeyPatch
) -> None:
    import core.config as config_mod

    monkeypatch.setattr(config_mod.settings, "photo_reading_provider", "recorded")
    monkeypatch.setattr(config_mod.settings, "photo_reading_recordings_dir", "")

    reading = read_photo(db_session, asset=asset, photo_sha256=SHA, image=b"", rows=(0, 0))

    assert reading.reason_code == "RECORDINGS_NOT_CONFIGURED"


# --- Sightings are evidence, kept as read ----------------------------------------------------


def test_a_sighting_cannot_be_changed_once_kept(
    db_session: Session, asset: ImageAssetRecord, sample_vco: Module
) -> None:
    answer = {
        "provider_version": "r",
        "sightings": [_sighting(candidates=[{"module_id": sample_vco.id, "score": 0.95}])],
    }
    reading = _read(db_session, asset, _Answers(answer))
    db_session.commit()
    (sighting,) = _sightings(db_session, reading)

    sighting.disposition = (
        "auto_propose" if sighting.disposition != "auto_propose" else "unresolved"
    )
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()


# --- moving a Reading on ----------------------------------------------------------------------


def test_only_a_reading_still_in_the_named_status_moves(
    db_session: Session, asset: ImageAssetRecord
) -> None:
    failed = _read(db_session, asset, _Answers(raises=TimeoutError()))
    read = _read(db_session, asset, _Answers({"provider_version": "r1", "sightings": []}))

    # A Retry wins the failed one; a second Retry of it, a moment later, finds it moved.
    assert move_readings(db_session, [failed.id], from_statuses=("failed",), to="superseded") == 1
    assert move_readings(db_session, [failed.id], from_statuses=("failed",), to="superseded") == 0
    # A confirmation of both moves only the one still read.
    assert (
        move_readings(db_session, [failed.id, read.id], from_statuses=("read",), to="confirmed")
        == 1
    )
    assert (failed.status, read.status) == ("superseded", "confirmed")
