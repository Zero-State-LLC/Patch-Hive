"""Clef DecisionProvider adapter for Cloudflare Workers AI System One.

The adapter is inert unless explicitly enabled. It fails closed on any
timeout, malformed response, or unavailability. Clef never mutates canon;
disposition is owned entirely by the Spec 005 DecisionPolicy and the
existing confirmation path. No Clef wire types (raw answer dicts, images)
escape this module - only DecisionPacket or ClefProviderError cross the
boundary.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Mapping, NoReturn, Sequence

import httpx
from pydantic import ValidationError

from intelligence.contracts import (
    ChoiceRequest,
    DecisionPacket,
    DecisionRequest,
    ProbabilityRequest,
    ScoreRequest,
)

DEFAULT_BASE_URL = "https://api.cloudflare.com/client/v4"
CLEF_MODELS = ("clef", "clef-flash")

_QUESTION_ID = "q0"
_ALLOWED_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})
_MAX_IMAGES = 4
_MAX_IMAGE_BYTES = 4 * 1024 * 1024
_MAX_TOTAL_BYTES = 8 * 1024 * 1024

__all__ = [
    "ClefAdapterState",
    "ClefAdapterEvent",
    "ClefDecisionProvider",
    "ClefProviderError",
    "adapter_transition",
    "FAIL_STATES",
    "ADAPTER_TRANSITIONS",
    "InvalidAdapterTransition",
    "CLEF_MODELS",
    "DEFAULT_BASE_URL",
]


class ClefAdapterState(str, Enum):
    IDLE = "IDLE"
    INVOKING = "INVOKING"
    SUCCESS = "SUCCESS"
    TIMEOUT = "TIMEOUT"
    MALFORMED = "MALFORMED"
    UNAVAILABLE = "UNAVAILABLE"


class ClefAdapterEvent(str, Enum):
    INVOKE = "invoke"
    RESPONSE_OK = "response_ok"
    TIMEOUT = "timeout"
    MALFORMED = "malformed"
    UNAVAILABLE = "unavailable"
    RESET = "reset"


FAIL_STATES = frozenset(
    {
        ClefAdapterState.TIMEOUT,
        ClefAdapterState.MALFORMED,
        ClefAdapterState.UNAVAILABLE,
    }
)


class InvalidAdapterTransition(ValueError):
    """Raised when a (state, event) pair is not part of the adapter table."""


class ClefProviderError(RuntimeError):
    """Fail-closed adapter error carrying a stable public code and last state."""

    def __init__(self, code: str, *, state: ClefAdapterState | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.state = state


_TransitionSpec = tuple[str | None, ClefAdapterState, ClefAdapterState | None]

_ADAPTER_TRANSITION_SPECS: dict[tuple[ClefAdapterState, ClefAdapterEvent], _TransitionSpec] = {
    (ClefAdapterState.IDLE, ClefAdapterEvent.INVOKE): (
        "invoke",
        ClefAdapterState.INVOKING,
        ClefAdapterState.IDLE,
    ),
    (ClefAdapterState.INVOKING, ClefAdapterEvent.RESPONSE_OK): (
        "response_ok",
        ClefAdapterState.SUCCESS,
        ClefAdapterState.MALFORMED,
    ),
    (ClefAdapterState.INVOKING, ClefAdapterEvent.TIMEOUT): (
        None,
        ClefAdapterState.TIMEOUT,
        None,
    ),
    (ClefAdapterState.INVOKING, ClefAdapterEvent.MALFORMED): (
        None,
        ClefAdapterState.MALFORMED,
        None,
    ),
    (ClefAdapterState.INVOKING, ClefAdapterEvent.UNAVAILABLE): (
        None,
        ClefAdapterState.UNAVAILABLE,
        None,
    ),
    (ClefAdapterState.SUCCESS, ClefAdapterEvent.RESET): (None, ClefAdapterState.IDLE, None),
    (ClefAdapterState.TIMEOUT, ClefAdapterEvent.RESET): (None, ClefAdapterState.IDLE, None),
    (ClefAdapterState.MALFORMED, ClefAdapterEvent.RESET): (None, ClefAdapterState.IDLE, None),
    (ClefAdapterState.UNAVAILABLE, ClefAdapterEvent.RESET): (None, ClefAdapterState.IDLE, None),
}

ADAPTER_TRANSITIONS: Mapping[
    tuple[ClefAdapterState, ClefAdapterEvent], _TransitionSpec
] = MappingProxyType(_ADAPTER_TRANSITION_SPECS)


def adapter_transition(
    state: ClefAdapterState,
    event: ClefAdapterEvent,
    *,
    flag_on: bool = False,
    request_valid: bool = False,
    maps_to_packet: bool = False,
) -> ClefAdapterState:
    """Pure guarded transition function for the Clef adapter state machine."""
    spec = ADAPTER_TRANSITIONS.get((state, event))
    if spec is None:
        raise InvalidAdapterTransition(
            f"invalid transition {state.value} + {event.value}"
        )
    guard_name, on_pass, on_fail = spec
    if guard_name is None:
        return on_pass
    if guard_name == "invoke":
        passed = flag_on and request_valid
    elif guard_name == "response_ok":
        passed = maps_to_packet
    else:
        raise InvalidAdapterTransition(f"unknown guard {guard_name}")
    if passed:
        return on_pass
    if on_fail is None:
        raise InvalidAdapterTransition(
            f"guard failed without fallback {state.value} + {event.value}"
        )
    return on_fail


@dataclass(frozen=True)
class ClefImage:
    """Internal image payload; never placed in DecisionPacket."""

    content_type: str
    data: bytes


ImageLoader = Callable[[DecisionRequest], Sequence[ClefImage]]


class _ClefMalformed(Exception):
    """Internal marker for malformed Clef responses."""


def _finite_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected numeric value")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite numeric value")
    return parsed


def _optional_float(answer: dict[str, Any], key: str) -> float | None:
    if key not in answer:
        return None
    value = answer[key]
    if value is None:
        return None
    return _finite_float(value)


def _encode_images(images: Sequence[ClefImage]) -> list[str]:
    if len(images) > _MAX_IMAGES:
        raise ValueError("too many images")
    encoded: list[str] = []
    total = 0
    for image in images:
        if not isinstance(image, ClefImage):
            raise ValueError("image type invalid")
        if image.content_type not in _ALLOWED_CONTENT_TYPES:
            raise ValueError("image content type invalid")
        if not image.data:
            raise ValueError("image data empty")
        size = len(image.data)
        if size > _MAX_IMAGE_BYTES:
            raise ValueError("image too large")
        total += size
        if total > _MAX_TOTAL_BYTES:
            raise ValueError("images exceed total budget")
        b64 = base64.b64encode(image.data).decode("ascii")
        encoded.append(f"data:{image.content_type};base64,{b64}")
    return encoded


def _decision_id(request_id: str, raw_hash: str) -> str:
    return hashlib.sha256(f"{request_id}:{raw_hash}".encode()).hexdigest()[:64]


class ClefDecisionProvider:
    """Spec 005 DecisionProvider backed by Cloudflare Workers AI Clef."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        account_id: str = "",
        api_token: str = "",
        model: str = "clef",
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
        image_loader: ImageLoader | None = None,
    ) -> None:
        if model not in CLEF_MODELS:
            raise ValueError("clef model must be a pinned Clef selector")
        if enabled and (not account_id or not api_token):
            raise ValueError("clef requires account_id and api_token when enabled")
        if timeout_seconds <= 0:
            raise ValueError("clef timeout_seconds must be positive")
        self._enabled = enabled
        self._account_id = account_id
        self._api_token = api_token
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client
        self._image_loader = image_loader
        self._last_state: ClefAdapterState = ClefAdapterState.IDLE
        self._state_trace: list[ClefAdapterState] = []

    @property
    def provider_version(self) -> str:
        return f"@cf/cloudflare/{self._model}"

    @property
    def last_state(self) -> ClefAdapterState:
        return self._last_state

    @property
    def state_trace(self) -> tuple[ClefAdapterState, ...]:
        return tuple(self._state_trace)

    def choose(self, request: ChoiceRequest) -> DecisionPacket:
        request_valid = (
            2 <= len(request.choices) <= 255
            and len({item.choice_id for item in request.choices})
            == len(request.choices)
        )
        question = {
            "type": "choice",
            "instructions": request.question,
            "criteria": {item.choice_id: item.description for item in request.choices},
        }
        return self._execute(
            request,
            request_valid=request_valid,
            question=question,
            mapper=lambda answer, raw_hash: self._map_choice(request, answer, raw_hash),
        )

    def score(self, request: ScoreRequest) -> DecisionPacket:
        request_valid = 2 <= len(request.levels) <= 10
        question = {
            "type": "score",
            "instructions": request.question,
            "criteria": list(request.levels),
        }
        return self._execute(
            request,
            request_valid=request_valid,
            question=question,
            mapper=lambda answer, raw_hash: self._map_score(request, answer, raw_hash),
        )

    def probability(self, request: ProbabilityRequest) -> DecisionPacket:
        question = {
            "type": "noul",
            "instructions": request.question,
            "criteria": {"true": request.true_criteria, "false": request.false_criteria},
        }
        return self._execute(
            request,
            request_valid=True,
            question=question,
            mapper=lambda answer, raw_hash: self._map_probability(
                request, answer, raw_hash
            ),
        )

    # internals ---------------------------------------------------------

    def _execute(
        self,
        request: DecisionRequest,
        *,
        request_valid: bool,
        question: dict[str, Any],
        mapper: Callable[[dict[str, Any], str], DecisionPacket],
    ) -> DecisionPacket:
        self._state_trace = [ClefAdapterState.IDLE]
        self._last_state = ClefAdapterState.IDLE

        images: list[str] = []
        # Images are loaded only when the flag is on; a disabled adapter touches nothing.
        if self._enabled and request_valid and self._image_loader is not None:
            try:
                images = _encode_images(tuple(self._image_loader(request)))
            except Exception:
                request_valid = False
                images = []

        invoked = adapter_transition(
            ClefAdapterState.IDLE,
            ClefAdapterEvent.INVOKE,
            flag_on=self._enabled,
            request_valid=request_valid,
        )
        self._last_state = invoked
        if invoked != ClefAdapterState.INVOKING:
            if not self._enabled:
                raise ClefProviderError("CLEF_DISABLED", state=invoked)
            raise ClefProviderError("CLEF_INVALID_REQUEST", state=invoked)
        self._state_trace.append(invoked)

        try:
            body = self._post(request=request, question=question, images=images)
        except httpx.TimeoutException as exc:
            self._fail(ClefAdapterEvent.TIMEOUT, "CLEF_TIMEOUT", exc)
        except httpx.HTTPError as exc:
            self._fail(ClefAdapterEvent.UNAVAILABLE, "CLEF_UNAVAILABLE", exc)
        except _ClefMalformed as exc:
            self._fail(ClefAdapterEvent.MALFORMED, "CLEF_MALFORMED", exc)

        try:
            packet = self._build_packet(body=body, mapper=mapper)
        except _ClefMalformed as exc:
            self._fail(ClefAdapterEvent.MALFORMED, "CLEF_MALFORMED", exc)
        except (ValueError, TypeError, KeyError, ValidationError) as exc:
            self._fail(ClefAdapterEvent.MALFORMED, "CLEF_MALFORMED", exc)

        succeeded = adapter_transition(
            ClefAdapterState.INVOKING,
            ClefAdapterEvent.RESPONSE_OK,
            maps_to_packet=True,
        )
        self._last_state = succeeded
        self._state_trace.append(succeeded)
        self._state_trace.append(adapter_transition(succeeded, ClefAdapterEvent.RESET))
        return packet

    def _fail(
        self,
        event: ClefAdapterEvent,
        code: str,
        cause: BaseException,
    ) -> NoReturn:
        failed = adapter_transition(ClefAdapterState.INVOKING, event)
        self._last_state = failed
        self._state_trace.append(failed)
        self._state_trace.append(adapter_transition(failed, ClefAdapterEvent.RESET))
        # Suppress the transport/body chain so no URL, payload, or header crosses the boundary.
        del cause
        raise ClefProviderError(code, state=failed) from None

    def _post(
        self,
        *,
        request: DecisionRequest,
        question: dict[str, Any],
        images: list[str],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "state": request.context,
            "questions": {_QUESTION_ID: question},
        }
        if images:
            payload["images"] = images
        url = (
            f"{self._base_url}/accounts/{self._account_id}/ai/run/"
            f"@cf/cloudflare/{self._model}"
        )
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
            "Idempotency-Key": request.idempotency_key,
        }
        owns_client = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            response = client.post(
                url, headers=headers, json=payload, timeout=self._timeout
            )
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError as exc:
                raise _ClefMalformed("invalid json") from exc
        finally:
            if owns_client:
                client.close()
        if not isinstance(body, dict):
            raise _ClefMalformed("non-object response")
        return body

    def _build_packet(
        self,
        *,
        body: dict[str, Any],
        mapper: Callable[[dict[str, Any], str], DecisionPacket],
    ) -> DecisionPacket:
        if body.get("success") is not True:
            raise _ClefMalformed("response marked failure")
        result = body.get("result")
        if not isinstance(result, dict):
            raise _ClefMalformed("missing result envelope")
        answers = result.get("answers")
        if not isinstance(answers, dict):
            raise _ClefMalformed("missing answers")
        answer = answers.get(_QUESTION_ID)
        if not isinstance(answer, dict):
            raise _ClefMalformed("missing answer")
        raw_hash = hashlib.sha256(
            json.dumps(
                body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest()
        return mapper(answer, raw_hash)

    def _map_choice(
        self,
        request: ChoiceRequest,
        answer: dict[str, Any],
        raw_hash: str,
    ) -> DecisionPacket:
        if answer.get("type") != "choice":
            raise ValueError("wrong answer type")
        choice = answer.get("choice")
        if not isinstance(choice, str):
            raise ValueError("choice missing")
        allowed = {item.choice_id for item in request.choices}
        if choice not in allowed:
            raise ValueError("choice outside candidate set")
        raw_probs = answer.get("probabilities", {})
        if not isinstance(raw_probs, dict):
            raise ValueError("probabilities invalid")
        cleaned: dict[str, float] = {}
        for key, value in raw_probs.items():
            if not isinstance(key, str) or key not in allowed:
                raise ValueError("probability key outside candidate set")
            cleaned[key] = _finite_float(value)
        if choice not in cleaned:
            raise ValueError("selected choice absent from probabilities")
        return DecisionPacket(
            decision_id=_decision_id(request.request_id, raw_hash),
            request_id=request.request_id,
            provider="clef",
            provider_version=self.provider_version,
            evidence_hash=request.evidence_hash,
            answer_type="choice",
            selected_choice=choice,
            probabilities=cleaned,
            confidence=_optional_float(answer, "confidence"),
            candidate_set_hash=request.candidate_set_hash(),
            created_at=datetime.now(timezone.utc),
            raw_payload_hash=raw_hash,
        )

    def _map_score(
        self,
        request: ScoreRequest,
        answer: dict[str, Any],
        raw_hash: str,
    ) -> DecisionPacket:
        if answer.get("type") != "score":
            raise ValueError("wrong answer type")
        score = _finite_float(answer.get("score"))
        max_score = float(len(request.levels) - 1)
        if score < 0.0 or score > max_score:
            raise ValueError("score outside rubric range")
        raw_probs = answer.get("probabilities", {})
        if not isinstance(raw_probs, dict):
            raise ValueError("probabilities invalid")
        cleaned: dict[str, float] = {}
        for key, value in raw_probs.items():
            if not isinstance(key, str):
                raise ValueError("probability key invalid")
            try:
                idx = int(key)
            except (TypeError, ValueError) as exc:
                raise ValueError("probability key not a level index") from exc
            if idx < 0 or idx >= len(request.levels):
                raise ValueError("level index outside rubric")
            cleaned[str(idx)] = _finite_float(value)
        return DecisionPacket(
            decision_id=_decision_id(request.request_id, raw_hash),
            request_id=request.request_id,
            provider="clef",
            provider_version=self.provider_version,
            evidence_hash=request.evidence_hash,
            answer_type="score",
            score=score,
            probabilities=cleaned,
            confidence=_optional_float(answer, "confidence"),
            rubric_hash=request.rubric_hash(),
            created_at=datetime.now(timezone.utc),
            raw_payload_hash=raw_hash,
        )

    def _map_probability(
        self,
        request: ProbabilityRequest,
        answer: dict[str, Any],
        raw_hash: str,
    ) -> DecisionPacket:
        if answer.get("type") != "noul":
            raise ValueError("wrong answer type")
        noul = _finite_float(answer.get("noul"))
        if noul < 0.0 or noul > 1.0:
            raise ValueError("noul outside [0, 1]")
        return DecisionPacket(
            decision_id=_decision_id(request.request_id, raw_hash),
            request_id=request.request_id,
            provider="clef",
            provider_version=self.provider_version,
            evidence_hash=request.evidence_hash,
            answer_type="probability",
            probability_yes=noul,
            created_at=datetime.now(timezone.utc),
            raw_payload_hash=raw_hash,
        )
