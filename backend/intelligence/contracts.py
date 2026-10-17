"""Immutable contracts for bounded, non-canonical decisions."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DECISION_SCHEMA_VERSION = "patchhive.decision.v1"


class DecisionPurpose(str, Enum):
    module_identity = "module_identity"
    module_family = "module_family"
    capability = "capability"
    port_semantics = "port_semantics"
    evidence_conflict = "evidence_conflict"
    routing = "routing"


class DecisionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python", exclude_none=True))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        instant = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return instant.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        )
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("decision contracts do not permit non-finite numbers")
        return 0.0 if value == 0 else value
    if isinstance(value, dict):
        return {str(key): _normalize(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


class ChoiceOption(DecisionContract):
    choice_id: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class DecisionRequest(DecisionContract):
    request_id: str = Field(min_length=1)
    schema_version: str = DECISION_SCHEMA_VERSION
    purpose: DecisionPurpose
    evidence_hash: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
    context: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)


class ChoiceRequest(DecisionRequest):
    question: str = Field(min_length=1, max_length=2000)
    choices: tuple[ChoiceOption, ...]

    @model_validator(mode="after")
    def validate_choices(self) -> "ChoiceRequest":
        ids = [item.choice_id for item in self.choices]
        if not ids:
            raise ValueError("choice request requires at least one option")
        if len(ids) > 255:
            raise ValueError("choice request supports at most 255 options")
        if len(ids) != len(set(ids)):
            raise ValueError("choice IDs must be unique")
        if self.purpose is DecisionPurpose.module_identity and "none_of_above" not in ids:
            raise ValueError("module identity choices must include none_of_above")
        return self

    def candidate_set_hash(self) -> str:
        return stable_sha256(self.choices)


class ScoreRequest(DecisionRequest):
    question: str = Field(min_length=1, max_length=2000)
    levels: tuple[str, ...]

    @model_validator(mode="after")
    def validate_levels(self) -> "ScoreRequest":
        if not 2 <= len(self.levels) <= 10:
            raise ValueError("score request requires 2 to 10 ordered levels")
        if len(self.levels) != len(set(self.levels)):
            raise ValueError("score levels must be unique")
        return self

    def rubric_hash(self) -> str:
        return stable_sha256(self.levels)


class ProbabilityRequest(DecisionRequest):
    question: str = Field(min_length=1, max_length=2000)
    true_criteria: str = Field(min_length=1, max_length=2000)
    false_criteria: str = Field(min_length=1, max_length=2000)


class DecisionPacket(DecisionContract):
    decision_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    schema_version: str = DECISION_SCHEMA_VERSION
    provider: str = Field(min_length=1)
    provider_version: str = Field(min_length=1)
    evidence_hash: str = Field(min_length=1)
    answer_type: Literal["choice", "score", "probability"]
    selected_choice: str | None = None
    score: float | None = None
    probability_yes: float | None = Field(default=None, ge=0, le=1)
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0, le=1)
    candidate_set_hash: str | None = None
    rubric_hash: str | None = None
    provider_status: Literal["succeeded", "failed", "timed_out"] = "succeeded"
    error_code: str | None = None
    created_at: datetime
    raw_payload_hash: str | None = None

    @model_validator(mode="after")
    def validate_answer(self) -> "DecisionPacket":
        if self.provider_status != "succeeded":
            if any(
                value is not None
                for value in (self.selected_choice, self.score, self.probability_yes, self.confidence)
            ) or self.probabilities:
                raise ValueError("failed/timed-out packets cannot carry an answer")
            return self

        if self.answer_type == "choice":
            if self.selected_choice is None or self.score is not None or self.probability_yes is not None:
                raise ValueError("choice packet requires only selected_choice")
            if self.selected_choice not in self.probabilities:
                raise ValueError("selected choice must be present in probabilities")
        elif self.answer_type == "score":
            if self.score is None or self.selected_choice is not None or self.probability_yes is not None:
                raise ValueError("score packet requires only score")
        elif self.answer_type == "probability":
            if self.probability_yes is None or self.selected_choice is not None or self.score is not None:
                raise ValueError("probability packet requires only probability_yes")

        if self.probabilities:
            if any(value < 0 or value > 1 for value in self.probabilities.values()):
                raise ValueError("probabilities must be between 0 and 1")
            if abs(sum(self.probabilities.values()) - 1.0) > 0.001:
                raise ValueError("probability distribution must sum to 1")
        return self

    def result_hash(self) -> str:
        return stable_sha256(self)
