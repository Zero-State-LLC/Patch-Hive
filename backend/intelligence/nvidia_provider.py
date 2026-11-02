"""NVIDIA vision DecisionProvider (NVIDIA API catalog, OpenAI-compatible chat).

A second vision provider beside Clef: it identifies a module from the evidence images
with an NVIDIA vision-language model and answers through a JSON schema that names only
the request's candidates. It reuses the Clef adapter machine (spec 006): inert unless
enabled, fail closed on timeout, transport error, malformed output or a loader failure,
and nothing but a ``DecisionPacket`` or a ``ClefProviderError`` (codes ``NVIDIA_*``)
leaves this module. Disposition stays with the spec 005 DecisionPolicy; a model's
self-reported probabilities are calibrated by the 007 evaluation, not trusted here.

Models are pinned to NVIDIA vision models on ``integrate.api.nvidia.com``
(``NVIDIA_MODELS``). The key comes from ``NVIDIA_API_KEY`` only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

import httpx

from intelligence.clef_provider import (
    ClefDecisionProvider,
    ImageLoader,
    _ClefMalformed,
)
from intelligence.contracts import DecisionPacket, DecisionRequest

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
# NVIDIA-built vision models in the API catalog (checked 2026-11-01). The first is the
# default: its model card lists structured output and function calling as supported.
NVIDIA_MODELS = (
    "nvidia/nemotron-3.5-super-vl-120b-a12b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
)
_MAX_TOKENS = 512

SYSTEM_PROMPT = (
    "You identify Eurorack synthesizer modules from rig photos for a documentation app. "
    "Answer only the question asked, using only the options given, and only through the "
    "required JSON schema. Report calibrated probabilities that sum to 1; when the images "
    "do not show enough to tell, spread probability rather than guess."
)

__all__ = ["NvidiaVisionProvider", "NVIDIA_MODELS", "DEFAULT_BASE_URL", "answer_schema"]


def answer_schema(question: dict[str, Any]) -> dict[str, Any]:
    """The JSON schema the model must fill for one Clef-style question."""
    kind = question["type"]
    if kind == "choice":
        ids = list(question["criteria"])
        return {
            "type": "object",
            "properties": {
                "type": {"const": "choice"},
                "choice": {"enum": ids},
                "probabilities": {
                    "type": "object",
                    "properties": {i: {"type": "number", "minimum": 0, "maximum": 1} for i in ids},
                    "additionalProperties": False,
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["type", "choice", "probabilities"],
            "additionalProperties": False,
        }
    if kind == "score":
        levels = [str(i) for i in range(len(question["criteria"]))]
        return {
            "type": "object",
            "properties": {
                "type": {"const": "score"},
                "score": {"type": "integer", "minimum": 0, "maximum": len(levels) - 1},
                "probabilities": {
                    "type": "object",
                    "properties": {i: {"type": "number", "minimum": 0, "maximum": 1} for i in levels},
                    "additionalProperties": False,
                },
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["type", "score"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": {
            "type": {"const": "noul"},
            "noul": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["type", "noul"],
        "additionalProperties": False,
    }


def _question_text(context: Any, question: dict[str, Any]) -> str:
    rendered = context if isinstance(context, str) else json.dumps(context, sort_keys=True, ensure_ascii=False)
    lines = [f"Context: {rendered}", f"Question: {question['instructions']}"]
    criteria = question["criteria"]
    if question["type"] == "choice":
        lines.append("Options (answer with the option id):")
        lines += [f"- {key}: {text or key}" for key, text in criteria.items()]
    elif question["type"] == "score":
        lines.append("Levels (answer with the level index, lowest first):")
        lines += [f"- {index}: {text}" for index, text in enumerate(criteria)]
    else:
        lines.append(f"Yes means: {criteria['true']}")
        lines.append(f"No means: {criteria['false']}")
        lines.append("Answer with the probability that the answer is yes.")
    return "\n".join(lines)


class NvidiaVisionProvider(ClefDecisionProvider):
    """Spec 005 DecisionProvider backed by an NVIDIA vision-language model."""

    PROVIDER_NAME = "nvidia"
    ERROR_PREFIX = "NVIDIA"

    def __init__(
        self,
        *,
        enabled: bool = False,
        api_key: str = "",
        model: str = NVIDIA_MODELS[0],
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
        image_loader: ImageLoader | None = None,
    ) -> None:
        if model not in NVIDIA_MODELS:
            raise ValueError("nvidia model must be a pinned NVIDIA vision model")
        if enabled and not api_key:
            raise ValueError("nvidia requires api_key when enabled")
        # The Clef base validates a Cloudflare account and a Clef model, which NVIDIA
        # does not have; placeholders satisfy it and the pinned NVIDIA model is set after.
        super().__init__(
            enabled=enabled,
            account_id="nvidia",
            api_token=api_key,
            model="clef",
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            client=client,
            image_loader=image_loader,
        )
        self._model = model

    @property
    def provider_version(self) -> str:
        return self._model

    def _post(
        self,
        *,
        request: DecisionRequest,
        question: dict[str, Any],
        images: list[str],
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": _question_text(request.context, question)}
        ]
        content += [{"type": "image_url", "image_url": {"url": image}} for image in images]
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0,
            "max_tokens": _MAX_TOKENS,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "decision", "schema": answer_schema(question), "strict": True},
            },
        }
        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        owns_client = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout)
        try:
            response = client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload, timeout=self._timeout
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
        choices = body.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise _ClefMalformed("expected one choice")
        if choices[0].get("finish_reason") not in (None, "stop"):
            raise _ClefMalformed("generation did not finish")
        message = choices[0].get("message")
        text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(text, str):
            raise _ClefMalformed("missing content")
        try:
            answer = json.loads(text)
        except ValueError as exc:
            raise _ClefMalformed("content is not json") from exc
        if not isinstance(answer, dict):
            raise _ClefMalformed("answer is not an object")
        raw_hash = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return mapper(answer, raw_hash)
