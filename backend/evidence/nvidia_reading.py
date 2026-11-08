"""NVIDIA reads a whole-Rig photo (spec 009 T022), through the Clef adapter (spec 006).

One call answers with every Sighting in the photo. The model can't know catalog ids, so it
names each candidate by maker and name, and PatchHive resolves those names against the
catalog (``CatalogNames``): a name the catalog lacks, or one two Modules share, is dropped,
never guessed, and two names for one Module add up.

The reader is inert unless enabled, and fails closed. A timeout, a transport error, or an
answer that is malformed or past a bound fails the Reading with a reason code, and no URL,
key, payload or model text leaves this module. The provider never sets a disposition: that
stays with the spec 005 DecisionPolicy.
"""

from __future__ import annotations

from typing import Any, NoReturn, get_args

import httpx
from evidence.readings import (
    MAX_CANDIDATES,
    MAX_SIGHTINGS,
    CatalogNames,
    ReadingFailed,
    SightingKind,
    resolve_named_answer,
)
from intelligence.clef_provider import (
    _MAX_IMAGE_BYTES,
    ClefAdapterEvent,
    ClefAdapterState,
    ClefImage,
    _ClefMalformed,
    _encode_images,
    adapter_transition,
)
from intelligence.nvidia_provider import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    NVIDIA_MODELS,
    answer_object,
    post_chat,
)

# Room for a full answer: about 150 tokens a Sighting, for up to 200 of them.
_MAX_TOKENS = 32768

SYSTEM_PROMPT = (
    "You read photos of Eurorack synthesizer cases for a documentation app. List everything "
    "in the case, row by row from the top and left to right in each row, only through the "
    "required JSON schema. Name a module only as its maker and model are printed on its "
    "panel. When you can't read a panel, say unknown and name no candidates rather than "
    "guess, and report probabilities that are calibrated, not hopeful."
)

__all__ = ["NvidiaRigReader", "rig_schema"]


def rig_schema(rows: int) -> dict[str, Any]:
    """The JSON schema the model fills for a photo of ``rows`` Rig rows."""
    number = {"type": "number", "minimum": 0, "maximum": 1}
    candidate = {
        "type": "object",
        "properties": {
            "maker": {"type": "string"},
            "name": {"type": "string"},
            "score": number,
        },
        "required": ["maker", "name", "score"],
        "additionalProperties": False,
    }
    sighting = {
        "type": "object",
        "properties": {
            "box": {
                "type": "object",
                "properties": {side: number for side in ("x", "y", "w", "h")},
                "required": ["x", "y", "w", "h"],
                "additionalProperties": False,
            },
            "kind": {"enum": list(get_args(SightingKind))},
            "row_index": {"type": "integer", "minimum": 0, "maximum": rows - 1},
            "start_hp": {"type": "integer", "minimum": 0},
            "hp": {"type": "integer", "minimum": 1},
            "candidates": {
                "type": "array",
                "maxItems": MAX_CANDIDATES,
                "items": candidate,
            },
        },
        "required": ["box", "kind", "row_index", "start_hp", "hp", "candidates"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "sightings": {"type": "array", "maxItems": MAX_SIGHTINGS, "items": sighting}
        },
        "required": ["sightings"],
        "additionalProperties": False,
    }


def _instructions(rows: int) -> str:
    return (
        f"This photo shows {rows} row{'s' if rows != 1 else ''} of a Eurorack case. For each "
        "thing in it give: its box as fractions of the photo's width and height; its kind "
        "(module, blank_panel, unknown, or not_eurorack for anything that isn't Eurorack); its "
        "row, 0 for the top row in this photo; its start HP from the left end of its row; and "
        f"its width in HP. For a module, name at most {MAX_CANDIDATES} candidates by maker and "
        "model, each with a probability, adding up to at most 1."
    )


class NvidiaRigReader:
    """Spec 009's photo provider, backed by an NVIDIA vision-language model."""

    name = "nvidia"
    sends_photo = True

    def __init__(
        self,
        *,
        enabled: bool = False,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        if model not in NVIDIA_MODELS:
            raise ValueError("nvidia model must be one of the pinned NVIDIA_MODELS")
        if enabled and not api_key:
            raise ValueError("nvidia requires api_key when enabled")
        self._enabled = enabled
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client
        self.last_state = ClefAdapterState.IDLE

    @property
    def provider_version(self) -> str:
        return self._model

    def answer(
        self, photo_sha256: str, image: bytes, *, rows: int, catalog: CatalogNames
    ) -> dict[str, Any]:
        try:
            (photo,) = _encode_images([ClefImage(content_type="image/jpeg", data=image)])
        except ValueError:
            photo = ""
        self.last_state = adapter_transition(
            ClefAdapterState.IDLE,
            ClefAdapterEvent.INVOKE,
            flag_on=self._enabled,
            request_valid=bool(photo),
        )
        if self.last_state is not ClefAdapterState.INVOKING:
            if not self._enabled:
                raise ReadingFailed("PROVIDER_DISABLED")
            too_large = len(image) > _MAX_IMAGE_BYTES
            raise ReadingFailed("PHOTO_TOO_LARGE" if too_large else "PHOTO_UNREADABLE")
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _instructions(rows)},
                        {"type": "image_url", "image_url": {"url": photo}},
                    ],
                },
            ],
            "temperature": 0,
            "max_tokens": _MAX_TOKENS,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "rig",
                    "schema": rig_schema(rows),
                    "strict": True,
                },
            },
        }
        try:
            body = post_chat(
                self._client,
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=self._timeout,
                payload=payload,
            )
            raw = answer_object(body)
        except httpx.TimeoutException:
            self._fail(ClefAdapterEvent.TIMEOUT, "PROVIDER_TIMED_OUT")
        except httpx.HTTPError:
            self._fail(ClefAdapterEvent.UNAVAILABLE, "PROVIDER_ERROR")
        except _ClefMalformed:
            self._fail(ClefAdapterEvent.MALFORMED, "ANSWER_MALFORMED")
        except Exception:  # anything else, such as a bad base URL, fails closed too
            self._fail(ClefAdapterEvent.UNAVAILABLE, "PROVIDER_ERROR")
        try:
            answer = resolve_named_answer(raw, catalog, version=self._model)
        except ReadingFailed as failed:
            self._fail(ClefAdapterEvent.MALFORMED, failed.code)
        self.last_state = adapter_transition(
            ClefAdapterState.INVOKING, ClefAdapterEvent.RESPONSE_OK, maps_to_packet=True
        )
        return answer

    def _fail(self, event: ClefAdapterEvent, code: str) -> NoReturn:
        self.last_state = adapter_transition(ClefAdapterState.INVOKING, event)
        # Only the code leaves: no URL, header, payload or model text.
        raise ReadingFailed(code) from None
