"""Spec 009 T010, Seam 2: the staging walkthrough's receipt records the photo it started from.

The walkthrough will start from a fixture Rig Photo instead of the seeded Rig (spec 009 T060a).
So its receipt must carry the Reading: the photo's hash, the provider, how many Sightings it
found, and the Rig revision and run that came of confirming it. A receipt without one is refused.
These are strict xfails until T060a builds them. Each fails on an assertion that the contract is
missing, never on a setup error.

The contract they set: `core.ops.f5_cutover.PhotoReadingEvidence` has `photo_sha256`,
`reading_id`, `provider` (`recorded` or `nvidia`), `provider_version`, `sighting_count`,
`rig_revision_id` and `run_id`. `capture_walkthrough_receipt` takes it as `reading=`, refuses
`READING_MISSING` when it's absent and `READING_NOT_CONFIRMED` when it names no revision, and
seals it into the receipt. The walkthrough's required steps add `upload_photo`, `read_photo`,
`confirm_reading` and `generate`.
"""

from __future__ import annotations

import json

import pytest

import core.ops.f5_cutover as cutover
from core.ops.f5_cutover import CutoverError
from tests.f5008_helpers import f5008_approver_allowlist  # noqa: F401  (autouse)
from tests.f5008_helpers import WALKTHROUGH_SHA, chain, enablement_receipt, health, outcome, seed_auth

T060A = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="spec 009 T060a: the walkthrough receipt records the Reading",
)
PHOTO_STEPS = ("upload_photo", "read_photo", "confirm_reading", "generate")


@pytest.fixture(scope="module")
def art():
    return chain(enablement_receipt())


def _evidence_type():
    evidence = getattr(cutover, "PhotoReadingEvidence", None)
    assert evidence is not None, "spec 009 T060a: no PhotoReadingEvidence in core.ops.f5_cutover"
    return evidence


def _reading(**overrides):
    values = dict(
        photo_sha256="e" * 64,
        reading_id="reading-synthetic",
        provider="recorded",
        provider_version="recorded-1",
        sighting_count=5,
        rig_revision_id="rig-rev-synthetic",
        run_id=1,
    )
    values.update(overrides)
    return _evidence_type()(**values)


def _capture(art, **overrides):
    kwargs = dict(
        start=art["start"],
        seed_auth=seed_auth(),
        health=health(),
        outcome=outcome(),
        source_commit_sha=WALKTHROUGH_SHA,
        reading=_reading(),
    )
    kwargs.update(overrides)
    return cutover.capture_walkthrough_receipt(**kwargs)


@T060A
def test_the_walkthrough_starts_from_a_photo() -> None:
    _evidence_type()
    missing = [step for step in PHOTO_STEPS if step not in cutover.REQUIRED_WALKTHROUGH_STEPS]
    assert missing == [], f"spec 009 T060a: required steps lack {missing}"
    required = cutover.REQUIRED_WALKTHROUGH_STEPS
    assert required.index("confirm_reading") < required.index("generate") < required.index(
        "export_debit"
    )


@T060A
def test_the_receipt_seals_the_reading_it_started_from(art) -> None:
    receipt = _capture(art)

    assert receipt.intact()
    assert receipt.reading.photo_sha256 == "e" * 64
    assert receipt.reading.rig_revision_id == "rig-rev-synthetic"
    tampered = receipt.model_copy(
        update={"reading": receipt.reading.model_copy(update={"sighting_count": 9})}
    )
    assert not tampered.intact()


@T060A
@pytest.mark.parametrize(
    ("reading", "code"),
    [
        (None, "READING_MISSING"),
        ({"rig_revision_id": ""}, "READING_NOT_CONFIRMED"),
    ],
)
def test_a_receipt_without_a_confirmed_reading_is_refused(art, reading, code) -> None:
    _evidence_type()
    value = None if reading is None else _reading(**reading)

    with pytest.raises(CutoverError) as refused:
        _capture(art, reading=value)

    assert refused.value.code == code


@T060A
def test_the_receipt_holds_the_photo_hash_never_the_photo(art) -> None:
    receipt = _capture(art)
    text = json.dumps(receipt.model_dump(mode="json"))

    assert "e" * 64 in text
    for forbidden in ("base64", "data:image", "/9j/"):
        assert forbidden not in text
