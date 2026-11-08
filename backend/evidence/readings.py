"""Reading a Rig photo (spec 009): one provider answer, bounded, with each Sighting's
disposition from the DecisionPolicy (spec 005).

A provider answers with every Sighting in a photo at once. The answer is checked against
``ProviderAnswer`` and its bounds before anything is kept. An answer that is missing,
malformed or past a bound, a timeout, or a provider that is off ends the Reading ``failed``
with a reason code and no Sightings. The provider never sets a disposition.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from canon.models import ImageAssetRecord, PhotoReadingRecord, PhotoSightingRecord
from core import settings
from intelligence.contracts import ChoiceOption, ChoiceRequest, DecisionPacket, DecisionPurpose
from intelligence.policy import DecisionDisposition, DecisionPolicy, PolicyThresholds
from modules.models import Module

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 5
MAX_SIGHTINGS = 200
NONE_OF_ABOVE = "none_of_above"

# A Reading is ``reading``, then ``read`` or ``failed``, then ``confirmed`` or ``superseded``.
# A confirmation applies to the current ones; the other two are done.
CURRENT_STATUSES = ("reading", "read", "failed")
# A Retake replaces a Reading in one of these, and a Retry reads a failed one again.
REPLACEABLE_STATUSES = ("read", "failed")
RETRYABLE_STATUSES = ("failed",)
# The policy's other dispositions (UNRESOLVED, ESCALATE, REJECT) all read as "unresolved".
DISPOSITIONS = {
    DecisionDisposition.AUTO_PROPOSE: "auto_propose",
    DecisionDisposition.USER_REVIEW: "user_review",
}


class ReadingFailed(Exception):
    """The photo could not be read; ``code`` is the Reading's reason code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _Answer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Box(_Answer):
    """A Sighting's bounds, normalised to the photo."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def _inside_the_photo(self) -> "Box":
        if self.x + self.w > 1 + 1e-6 or self.y + self.h > 1 + 1e-6:
            raise ValueError("box reaches past the photo")
        return self


class Candidate(_Answer):
    module_id: int = Field(ge=1)
    score: float = Field(ge=0, le=1)


class SightingAnswer(_Answer):
    box: Box
    kind: Literal["module", "blank_panel", "unknown", "not_eurorack"]
    row_index: int = Field(ge=0)
    start_hp: int = Field(ge=0)
    hp: int = Field(ge=1)
    candidates: list[Candidate] = Field(default_factory=list)

    def is_distribution(self) -> bool:
        """Candidates are distinct, their scores add up to at most 1, and only a module
        Sighting names any."""
        ids = [c.module_id for c in self.candidates]
        return (
            len(ids) == len(set(ids))
            and sum(c.score for c in self.candidates) <= 1 + 1e-6
            and (self.kind == "module" or not self.candidates)
        )


class ProviderAnswer(_Answer):
    """Every Sighting in one photo, as a provider answers (and as a recording keeps it)."""

    provider_version: str = Field(min_length=1, max_length=64)
    sightings: list[SightingAnswer]


class PhotoProvider(Protocol):
    name: str

    def answer(self, photo_sha256: str, image: bytes) -> object: ...


class RecordedProvider:
    """Replays answers saved as ``<photo sha256>.json`` in a directory, with no network."""

    name = "recorded"

    def __init__(self, directory: str) -> None:
        if not directory or not Path(directory).is_dir():
            raise ReadingFailed("RECORDINGS_NOT_CONFIGURED")
        self.directory = directory

    def answer(self, photo_sha256: str, image: bytes) -> object:
        path = Path(self.directory) / f"{photo_sha256}.json"
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ReadingFailed("RECORDING_MISSING") from None
        except OSError:
            raise ReadingFailed("RECORDING_UNREADABLE") from None
        try:
            return json.loads(text)
        except ValueError:
            raise ReadingFailed("ANSWER_MALFORMED") from None


def configured_provider() -> PhotoProvider:
    """The provider ``photo_reading_provider`` names, or the reason there is none."""
    name = settings.photo_reading_provider
    if name == "recorded":
        return RecordedProvider(settings.photo_reading_recordings_dir)
    if name == "nvidia":
        # T022 wires NVIDIA's whole-rig answer through the Clef adapter.
        raise ReadingFailed("PROVIDER_UNAVAILABLE")
    raise ReadingFailed("PROVIDER_DISABLED")


def photo_reading_closed_reason() -> str | None:
    """Why this host reads no photos, as a reason code, or None when it reads them."""
    try:
        configured_provider()
    except ReadingFailed as closed:
        return closed.code
    return None


def check_answer(payload: object, *, rows: int) -> ProviderAnswer:
    """The answer, if it parses and every Sighting is inside its bounds."""
    try:
        answer = ProviderAnswer.model_validate(payload)
    except ValidationError:
        raise ReadingFailed("ANSWER_MALFORMED") from None
    if len(answer.sightings) > MAX_SIGHTINGS:
        raise ReadingFailed("TOO_MANY_SIGHTINGS")
    if any(len(s.candidates) > MAX_CANDIDATES for s in answer.sightings):
        raise ReadingFailed("TOO_MANY_CANDIDATES")
    if not all(s.is_distribution() for s in answer.sightings):
        raise ReadingFailed("ANSWER_MALFORMED")
    if any(s.row_index >= rows for s in answer.sightings):
        raise ReadingFailed("ROW_OUTSIDE_PHOTO")
    return answer


def _check_catalog(db: Session, answer: ProviderAnswer) -> None:
    named = {c.module_id for s in answer.sightings for c in s.candidates}
    if not named:
        return
    known = {module_id for (module_id,) in db.query(Module.id).filter(Module.id.in_(named))}
    if named - known:
        raise ReadingFailed("CANDIDATE_NOT_IN_CATALOG")


def _policy() -> DecisionPolicy:
    return DecisionPolicy(
        PolicyThresholds(
            policy_version=settings.decision_policy_version,
            auto_propose_at=settings.decision_auto_propose_at,
            user_review_at=settings.decision_user_review_at,
            probability_margin=settings.decision_probability_margin,
        )
    )


def _disposition(
    policy: DecisionPolicy,
    sighting: SightingAnswer,
    *,
    key: str,
    provider: str,
    provider_version: str,
    photo_sha256: str,
    now: datetime,
) -> tuple[str, str]:
    """The policy's disposition for a Sighting's identity, as a choice among its candidates
    or none of them. A Sighting with no candidates abstains, so it stays unresolved."""
    ranked = sorted(sighting.candidates, key=lambda c: (-c.score, c.module_id))
    request = ChoiceRequest(
        request_id=key,
        purpose=DecisionPurpose.module_identity,
        evidence_hash=photo_sha256,
        idempotency_key=key,
        question="Which catalog Module is this Sighting?",
        choices=tuple(ChoiceOption(choice_id=str(c.module_id)) for c in ranked)
        + (ChoiceOption(choice_id=NONE_OF_ABOVE),),
    )
    probabilities = {str(c.module_id): c.score for c in ranked}
    probabilities[NONE_OF_ABOVE] = max(0.0, 1.0 - sum(probabilities.values()))
    top = ranked[0] if ranked else None
    packet = DecisionPacket(
        decision_id=key,
        request_id=key,
        provider=provider,
        provider_version=provider_version,
        evidence_hash=photo_sha256,
        answer_type="choice",
        selected_choice=str(top.module_id) if top else NONE_OF_ABOVE,
        probabilities=probabilities,
        confidence=top.score if top else None,
        candidate_set_hash=request.candidate_set_hash(),
        created_at=now,
    )
    result = policy.evaluate(packet, request)
    return DISPOSITIONS.get(result.disposition, "unresolved"), result.reason_codes[0]


def move_readings(
    db: Session, reading_ids: list[str], *, from_statuses: tuple[str, ...], to: str
) -> int:
    """Move the Readings still in ``from_statuses`` to ``to``, and say how many moved.

    The update is conditional, so when two requests race for one Reading (a confirm and a
    Retake, or two Retries) only one moves it, and the other sees it already moved.
    """
    return (
        db.query(PhotoReadingRecord)
        .filter(
            PhotoReadingRecord.id.in_(reading_ids),
            PhotoReadingRecord.status.in_(from_statuses),
        )
        .update({PhotoReadingRecord.status: to}, synchronize_session="fetch")
    )


def read_photo(
    db: Session,
    *,
    asset: ImageAssetRecord,
    photo_sha256: str,
    image: bytes,
    rows: tuple[int, int],
    provider: PhotoProvider | None = None,
) -> PhotoReadingRecord:
    """Read one stored photo and keep its Reading, ``read`` or ``failed``.

    ``photo_sha256`` is the file as uploaded, ``image`` its stored copy, and ``rows`` the
    first and last Rig rows it covers. A provider failure fails the Reading; it never raises.
    """
    now = datetime.now(timezone.utc)
    reading = PhotoReadingRecord(
        id=f"read-{uuid.uuid4().hex[:20]}",
        rack_id=asset.rack_id,
        image_asset_id=asset.id,
        user_id=asset.user_id,
        status="reading",
        provider=provider.name if provider else settings.photo_reading_provider,
        photo_sha256=photo_sha256,
        policy_version=settings.decision_policy_version,
        first_row=rows[0],
        last_row=rows[1],
        created_at=now,
    )
    db.add(reading)
    db.flush()

    try:
        source = provider or configured_provider()
        answer = check_answer(source.answer(photo_sha256, image), rows=rows[1] - rows[0] + 1)
        _check_catalog(db, answer)
    except ReadingFailed as failure:
        reading.status, reading.reason_code = "failed", failure.code
    except TimeoutError:
        reading.status, reading.reason_code = "failed", "PROVIDER_TIMED_OUT"
    except Exception:  # a provider bug fails the Reading closed, never the upload
        logger.exception("photo reading %s failed", reading.id)
        reading.status, reading.reason_code = "failed", "PROVIDER_ERROR"
    else:
        policy = _policy()
        for position, sighting in enumerate(answer.sightings):
            sighting_id = f"sight-{uuid.uuid4().hex[:20]}"
            disposition, reason = _disposition(
                policy,
                sighting,
                key=sighting_id,
                provider=reading.provider,
                provider_version=answer.provider_version,
                photo_sha256=photo_sha256,
                now=now,
            )
            db.add(
                PhotoSightingRecord(
                    id=sighting_id,
                    reading_id=reading.id,
                    position=position,
                    box=sighting.box.model_dump(),
                    kind=sighting.kind,
                    row_index=rows[0] + sighting.row_index,
                    start_hp=sighting.start_hp,
                    hp=sighting.hp,
                    candidates=[c.model_dump() for c in sighting.candidates],
                    disposition=disposition,
                    policy_reason=reason,
                )
            )
        reading.status, reading.provider_version = "read", answer.provider_version
    reading.completed_at = datetime.now(timezone.utc)
    db.flush()
    return reading
