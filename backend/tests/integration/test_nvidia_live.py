"""Opt-in live smoke test for the NVIDIA vision provider (spec 005 T086).

Calls the hosted NVIDIA API catalog with one synthetic image for each pinned model (the
NVIDIA default, the NVIDIA nano model, and the Meta Llama 3.2 90B Vision fallback), through
``NvidiaVisionProvider`` with the same request shape the decision route uses. It never runs in
CI: it needs ``RUN_NVIDIA_LIVE=1`` and an ``NVIDIA_API_KEY`` in the environment. The key is read
from the environment only and never printed. This is a wire check, not a 007 evaluation: it
says nothing about accuracy on rig photos.
"""

from __future__ import annotations

import os
import struct
import zlib

import pytest

from intelligence.clef_provider import ClefImage
from intelligence.contracts import ChoiceOption, ChoiceRequest, DecisionPurpose
from intelligence.nvidia_provider import NVIDIA_MODELS, NvidiaVisionProvider

API_KEY = os.environ.get("NVIDIA_API_KEY", "")
pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_NVIDIA_LIVE") != "1" or not API_KEY,
    reason="live NVIDIA call; set RUN_NVIDIA_LIVE=1 and NVIDIA_API_KEY",
)


def _red_square_png(size: int = 128) -> bytes:
    """A solid red square, built without an imaging library."""
    row = b"\x00" + b"\xff\x00\x00" * size
    raw = row * size

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


@pytest.mark.parametrize("model", NVIDIA_MODELS)
def test_each_pinned_model_answers_a_candidate_from_an_image(model: str) -> None:
    image = ClefImage(content_type="image/png", data=_red_square_png())
    provider = NvidiaVisionProvider(
        enabled=True,
        api_key=API_KEY,
        model=model,
        # The first call to a cold model has taken over 20 s; the route default stays 20 s.
        timeout_seconds=90,
        image_loader=lambda _request: [image],
    )
    request = ChoiceRequest(
        request_id=f"live-{model}",
        purpose=DecisionPurpose.module_identity,
        evidence_hash="live-smoke",
        idempotency_key=f"live-{model}",
        context={"note": "synthetic test image"},
        question="Which option describes the image?",
        choices=(
            ChoiceOption(choice_id="red_square", description="a solid red square"),
            ChoiceOption(choice_id="blue_circle", description="a blue circle"),
            ChoiceOption(choice_id="none_of_above"),
        ),
    )

    packet = provider.choose(request)

    assert packet.provider == "nvidia"
    assert packet.provider_version == model
    assert set(packet.probabilities) <= {"red_square", "blue_circle", "none_of_above"}
    assert max(packet.probabilities, key=packet.probabilities.get) == "red_square"
