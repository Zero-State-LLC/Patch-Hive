"""Jev adapter for the provider-neutral DecisionProvider contract.

The adapter is inert unless the application explicitly enables Decision Intelligence.
It sends normalized JSON state only; callers must not pass image/audio/video bytes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from intelligence.contracts import (
    ChoiceRequest,
    DecisionPacket,
    ProbabilityRequest,
    ScoreRequest,
)

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = ""
MOVING_MODEL_ALIASES = {"jev-latest", "jev-preview", "latest", "preview"}


class JevProviderError(RuntimeError):
    """Fail-closed provider boundary error with a stable public code."""


class JevDecisionProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Jev API key is required")
        normalized_model = model.strip().lower()
        if not normalized_model:
            raise ValueError("Jev model must be explicitly configured")
        if (
            normalized_model in MOVING_MODEL_ALIASES
            or normalized_model.endswith("-latest")
            or normalized_model.endswith("-preview")
        ):
            raise ValueError("Jev model must be pinned; moving aliases are not allowed")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._client = client

    def choose(self, request: ChoiceRequest) -> DecisionPacket:
        criteria = {item.choice_id: item.description for item in request.choices}
        answer, raw_hash = self._call(
            state=request.context,
            question_id=request.request_id,
            idempotency_key=request.idempotency_key,
            question={
                "type": "choice",
                "instructions": request.question,
                "criteria": criteria,
            },
        )
        probabilities = {str(k): float(v) for k, v in answer.get("probabilities", {}).items()}
        return DecisionPacket(
            decision_id=self._decision_id(request.request_id, raw_hash),
            request_id=request.request_id,
            provider="jev",
            provider_version=self._model,
            evidence_hash=request.evidence_hash,
            answer_type="choice",
            selected_choice=answer.get("choice"),
            probabilities=probabilities,
            confidence=answer.get("confidence"),
            candidate_set_hash=request.candidate_set_hash(),
            created_at=datetime.now(timezone.utc),
            raw_payload_hash=raw_hash,
        )

    def score(self, request: ScoreRequest) -> DecisionPacket:
        answer, raw_hash = self._call(
            state=request.context,
            question_id=request.request_id,
            idempotency_key=request.idempotency_key,
            question={
                "type": "score",
                "instructions": request.question,
                "criteria": list(request.levels),
            },
        )
        return DecisionPacket(
            decision_id=self._decision_id(request.request_id, raw_hash),
            request_id=request.request_id,
            provider="jev",
            provider_version=self._model,
            evidence_hash=request.evidence_hash,
            answer_type="score",
            score=float(answer["score"]),
            probabilities={str(k): float(v) for k, v in answer.get("probabilities", {}).items()},
            confidence=answer.get("confidence"),
            rubric_hash=request.rubric_hash(),
            created_at=datetime.now(timezone.utc),
            raw_payload_hash=raw_hash,
        )

    def probability(self, request: ProbabilityRequest) -> DecisionPacket:
        answer, raw_hash = self._call(
            state=request.context,
            question_id=request.request_id,
            idempotency_key=request.idempotency_key,
            question={
                "type": "noul",
                "instructions": request.question,
                "criteria": {
                    "true": request.true_criteria,
                    "false": request.false_criteria,
                },
            },
        )
        return DecisionPacket(
            decision_id=self._decision_id(request.request_id, raw_hash),
            request_id=request.request_id,
            provider="jev",
            provider_version=self._model,
            evidence_hash=request.evidence_hash,
            answer_type="probability",
            probability_yes=float(answer["noul"]),
            created_at=datetime.now(timezone.utc),
            raw_payload_hash=raw_hash,
        )

    def _call(
        self,
        *,
        state: dict[str, Any],
        question_id: str,
        idempotency_key: str,
        question: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        payload = {"model": self._model, "state": state, "questions": {question_id: question}}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }
        owns_client = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            try:
                response = client.post(
                    f"{self._base_url}/v1/systemone",
                    headers=headers,
                    json=payload,
                    timeout=self._timeout,
                )
                response.raise_for_status()
                body = response.json()
            except httpx.TimeoutException as exc:
                raise JevProviderError("JEV_TIMEOUT") from exc
            except httpx.HTTPStatusError as exc:
                raise JevProviderError("JEV_HTTP_ERROR") from exc
            except httpx.HTTPError as exc:
                raise JevProviderError("JEV_TRANSPORT_ERROR") from exc
        finally:
            if owns_client:
                client.close()

        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        raw_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        answers = body.get("result", body).get("answers", {})
        answer = answers.get(question_id)
        if not isinstance(answer, dict):
            raise ValueError("Jev response omitted the requested answer")
        return answer, raw_hash

    @staticmethod
    def _decision_id(request_id: str, raw_hash: str) -> str:
        return hashlib.sha256(f"{request_id}:{raw_hash}".encode()).hexdigest()[:64]
