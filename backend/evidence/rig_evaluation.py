"""Whole-rig evaluation (spec 009 T070a): how well answers read labelled Rig photos.

A corpus whose ``unit`` is ``whole_rig`` labels each photo with every Module's identity,
``row_index`` and ``start_hp``, plus its Blank Panels. The harness is handed each photo's
answer, as a provider gave it, and never calls a provider. Each answer is checked as a Reading
checks it, and each Sighting's identity is put to the DecisionPolicy as a Reading puts it.

It measures identity accuracy per Sighting, detection recall and precision, position error in
HP, and false canonicalization, which must stay zero. A detection is any Sighting but a
``not_eurorack`` one. It matches a label in the same row whose span it overlaps, one to one,
the largest overlap first. Admitting a corpus stays with spec 007's validator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Mapping, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
    model_validator,
)

from evidence.readings import (
    NONE_OF_ABOVE,
    ReadingFailed,
    SightingAnswer,
    check_answer,
    sighting_decision,
)
from intelligence.contracts import ChoiceOption, DecisionPacket
from intelligence.evaluation_corpus import WHOLE_RIG_UNIT, Validator, load_pilot_validator
from intelligence.evaluation import structural_false_canonicalizations
from intelligence.policy import DecisionPolicy

BLANK_PANEL = "blank_panel"
# A photo the harness was handed no answer for: the provider gave none.
NO_ANSWER = "NO_ANSWER"
# A replayed decision needs a time; no measure depends on it.
_REPLAYED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class RigEvaluationError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class RigLabel(BaseModel):
    """One thing on a labelled photo: a Module or a Blank Panel, and where it is."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Strict, as the validator reads a label: a loosely read "yes" would score a catalog
    # Module as off-catalog.
    kind: Literal["module", "blank_panel"]
    row_index: StrictInt = Field(ge=0)
    start_hp: StrictInt = Field(ge=0)
    hp: StrictInt = Field(ge=1)
    maker: StrictStr | None = None
    name: StrictStr | None = None
    # A Module the catalog doesn't have, so the right answer is none of its candidates.
    open_set: StrictBool = False

    @model_validator(mode="after")
    def _module_is_named(self) -> "RigLabel":
        if self.kind == "module" and not self.open_set and not (self.maker and self.name):
            raise ValueError("a catalog Module's label names its maker and name")
        return self


class RigCase(BaseModel):
    """A labelled whole-rig photo, read from a corpus manifest's case."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    case_id: str = Field(min_length=1)
    image_asset_hashes: tuple[str, ...] = Field(min_length=1, max_length=1)
    rows: StrictInt = Field(ge=1)
    labels: tuple[RigLabel, ...] = Field(min_length=1)

    @property
    def photo_sha256(self) -> str:
        return self.image_asset_hashes[0].removeprefix("sha256:")


class ModuleNames(Protocol):
    """Names a catalog Module, as ``CatalogNames`` does."""

    def module_id(self, maker: str, name: str) -> int | None: ...


@dataclass(frozen=True)
class RigMetrics:
    photo_count: int
    # Each photo whose answer a Reading would fail, with the Reading's reason code.
    failed_photos: dict[str, str]
    label_count: int
    sighting_count: int
    matched_count: int
    identity_accuracy: float | None
    detection_recall: float
    detection_precision: float | None
    position_error_hp_mean: float | None
    position_error_hp_max: int | None
    false_canonicalization_count: int


@dataclass(frozen=True)
class _ReplayedSighting:
    """A Sighting's decision, in the shape ``structural_false_canonicalizations`` replays."""

    case_id: str
    packet: DecisionPacket
    candidate_options: tuple[ChoiceOption, ...]
    candidate_ids: None = None


def rig_cases(
    manifest: Mapping[str, Any], *, validator: Validator | None = None
) -> tuple[RigCase, ...]:
    """The labelled photos of a whole-rig corpus manifest, once spec 007's validator finds
    nothing wrong with any of them. A corpus too small to admit, like a fixture, still
    scores."""
    if manifest.get("unit") != WHOLE_RIG_UNIT:
        raise RigEvaluationError("NOT_A_WHOLE_RIG_CORPUS")
    errors = (validator or load_pilot_validator())(dict(manifest)).get("errors") or []
    if errors:
        raise RigEvaluationError("RIG_CORPUS_INVALID", ";".join(map(str, errors)))
    try:
        return tuple(RigCase.model_validate(case) for case in manifest.get("cases") or [])
    except ValidationError as exc:
        raise RigEvaluationError("RIG_CASE_INVALID", str(exc)) from exc


def _label_identity(case: RigCase, label: RigLabel, catalog: ModuleNames) -> str:
    if label.kind == "blank_panel":
        return BLANK_PANEL
    if label.open_set:
        return NONE_OF_ABOVE
    module_id = catalog.module_id(label.maker or "", label.name or "")
    if module_id is None:
        # A label the catalog can't name would score a right answer as wrong.
        raise RigEvaluationError(
            "LABEL_NOT_IN_CATALOG", f"{case.case_id}: {label.maker} {label.name}"
        )
    return str(module_id)


def _overlap(label: RigLabel, sighting: SightingAnswer) -> int:
    if label.row_index != sighting.row_index:
        return 0
    end = min(label.start_hp + label.hp, sighting.start_hp + sighting.hp)
    return max(0, end - max(label.start_hp, sighting.start_hp))


def _matches(
    labels: tuple[RigLabel, ...], detections: list[SightingAnswer]
) -> list[tuple[int, int]]:
    """(label, detection) index pairs, one to one, the largest overlap first, then the
    closest start."""
    ranked = sorted(
        (-overlap, abs(sighting.start_hp - label.start_hp), li, di)
        for li, label in enumerate(labels)
        for di, sighting in enumerate(detections)
        if (overlap := _overlap(label, sighting)) > 0
    )
    used_labels: set[int] = set()
    used_detections: set[int] = set()
    pairs = []
    for _, _, li, di in ranked:
        if li not in used_labels and di not in used_detections:
            used_labels.add(li)
            used_detections.add(di)
            pairs.append((li, di))
    return pairs


def evaluate_rig_readings(
    cases: Iterable[RigCase],
    answers: Mapping[str, object],
    *,
    catalog: ModuleNames,
    policy: DecisionPolicy,
) -> RigMetrics:
    """Score each photo's answer, by case id, against its labels. ``None`` is a photo the
    provider gave no answer for."""
    rows = tuple(cases)
    if not rows:
        raise RigEvaluationError("CORPUS_EMPTY")
    ids = [case.case_id for case in rows]
    if len(ids) != len(set(ids)):
        raise RigEvaluationError("DUPLICATE_CASE_ID")
    if set(answers) != set(ids):
        raise RigEvaluationError("ANSWERS_NOT_FOR_CORPUS")
    expected = {
        case.case_id: [_label_identity(case, label, catalog) for label in case.labels]
        for case in rows
    }

    failed: dict[str, str] = {}
    replayed: list[_ReplayedSighting] = []
    detection_count = correct = 0
    errors: list[int] = []
    for case in rows:
        payload = answers[case.case_id]
        try:
            if payload is None:
                raise ReadingFailed(NO_ANSWER)
            answer = check_answer(payload, rows=case.rows)
        except ReadingFailed as failure:
            failed[case.case_id] = failure.code
            continue
        detections: list[SightingAnswer] = []
        identities: list[str] = []
        for position, sighting in enumerate(answer.sightings):
            key = f"{case.case_id}:{position}"
            packet, request = sighting_decision(
                sighting,
                key=key,
                provider="evaluation",
                provider_version=answer.provider_version,
                photo_sha256=case.photo_sha256,
                now=_REPLAYED_AT,
            )
            replayed.append(_ReplayedSighting(key, packet, request.choices))
            if sighting.kind != "not_eurorack":
                detections.append(sighting)
                # A Sighting's identity is the choice its decision selects, as the Reading
                # screen shows it; a Blank Panel's is its kind.
                identities.append(
                    BLANK_PANEL
                    if sighting.kind == "blank_panel"
                    else packet.selected_choice or NONE_OF_ABOVE
                )
        detection_count += len(detections)
        for li, di in _matches(case.labels, detections):
            correct += identities[di] == expected[case.case_id][li]
            errors.append(abs(detections[di].start_hp - case.labels[li].start_hp))

    label_count = sum(len(case.labels) for case in rows)
    matched = len(errors)
    return RigMetrics(
        photo_count=len(rows),
        failed_photos=failed,
        label_count=label_count,
        sighting_count=detection_count,
        matched_count=matched,
        identity_accuracy=correct / matched if matched else None,
        detection_recall=matched / label_count,
        detection_precision=matched / detection_count if detection_count else None,
        position_error_hp_mean=sum(errors) / matched if matched else None,
        position_error_hp_max=max(errors) if errors else None,
        false_canonicalization_count=structural_false_canonicalizations(replayed, policy),
    )
