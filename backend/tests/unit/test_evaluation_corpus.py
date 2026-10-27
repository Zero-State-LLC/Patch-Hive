"""Spec 007 T010: corpus freeze, admission, and cross-partition leakage."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from intelligence.evaluation_corpus import (
    ADMITTED_STATUS,
    CorpusFreezeError,
    corpus_manifest_sha256,
    cross_partition_leakage,
    freeze_corpus,
    load_pilot_validator,
    verify_corpus_freeze,
)
from tests.eval007_helpers import admitted_manifest, image_hash

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_admitted_manifest_freezes_with_recorded_sha() -> None:
    manifest = admitted_manifest()
    record = freeze_corpus(manifest)
    assert record.admission_status == ADMITTED_STATUS
    assert len(record.corpus_sha256) == 64
    assert record.corpus_sha256 == corpus_manifest_sha256(manifest)
    assert len(record.record_sha256) == 64
    assert record.case_count == len(manifest["cases"])
    assert verify_corpus_freeze(record)
    assert verify_corpus_freeze(record, manifest)


def test_corpus_sha_is_order_and_annotation_independent() -> None:
    manifest = admitted_manifest()
    shuffled = copy.deepcopy(manifest)
    shuffled["cases"] = list(reversed(shuffled["cases"]))
    shuffled["status"] = "ANNOTATION_CHANGED"
    shuffled["notes"] = ["extra"]
    assert freeze_corpus(shuffled).corpus_sha256 == freeze_corpus(manifest).corpus_sha256


def test_frozen_record_is_immutable_and_tamper_evident() -> None:
    manifest = admitted_manifest()
    record = freeze_corpus(manifest)
    with pytest.raises(ValidationError):
        record.corpus_sha256 = "0" * 64  # type: ignore[misc]
    tampered = record.model_copy(update={"case_count": record.case_count + 1})
    assert not verify_corpus_freeze(tampered)
    swapped = record.model_copy(update={"corpus_sha256": "0" * 64})
    assert not verify_corpus_freeze(swapped)


def test_manifest_change_after_freeze_is_detected() -> None:
    manifest = admitted_manifest()
    record = freeze_corpus(manifest)
    changed = copy.deepcopy(manifest)
    changed["cases"][0]["expected_choice"] = "maker:other:rev-a"
    assert not verify_corpus_freeze(record, changed)


def test_cross_partition_image_leakage_is_rejected() -> None:
    manifest = admitted_manifest()
    dev = next(c for c in manifest["cases"] if c["partition"] == "development")
    locked = next(c for c in manifest["cases"] if c["partition"] == "locked_test")
    locked["image_asset_hashes"] = list(dev["image_asset_hashes"])
    assert cross_partition_leakage(manifest)
    with pytest.raises(CorpusFreezeError) as exc:
        freeze_corpus(manifest)
    assert exc.value.code == "CROSS_PARTITION_LEAKAGE"


def test_cross_partition_case_id_leakage_is_rejected() -> None:
    manifest = admitted_manifest()
    dup = copy.deepcopy(manifest["cases"][1])
    dup["partition"] = "locked_test" if dup["partition"] != "locked_test" else "validation"
    dup["image_asset_hashes"] = [image_hash("other-image")]
    manifest["cases"].append(dup)
    with pytest.raises(CorpusFreezeError) as exc:
        freeze_corpus(manifest)
    assert exc.value.code == "CROSS_PARTITION_LEAKAGE"


def test_validator_reported_leakage_is_rejected_even_if_local_check_passes() -> None:
    def fake_validator(_: dict) -> dict:
        return {"errors": ["case-001:cross_partition_image_leakage:x"], "admission_status": "NOT_ADMITTED"}

    with pytest.raises(CorpusFreezeError) as exc:
        freeze_corpus(admitted_manifest(), validator=fake_validator)
    assert exc.value.code == "CROSS_PARTITION_LEAKAGE"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rights_and_consent", {"rights_status": "RIGHTS_UNKNOWN", "source_url": "https://example.invalid/x"}),
        ("annotation_status", "DISCOVERED"),
        ("ground_truth_status", "UNVERIFIED"),
        ("reviewers", []),
    ],
)
def test_unadmitted_cases_are_not_frozen(field: str, value: object) -> None:
    manifest = admitted_manifest()
    manifest["cases"][0][field] = value
    with pytest.raises(CorpusFreezeError) as exc:
        freeze_corpus(manifest)
    assert exc.value.code == "ADMISSION_REJECTED"


def test_missing_or_empty_corpus_fails_closed() -> None:
    with pytest.raises(CorpusFreezeError) as exc:
        freeze_corpus(None)
    assert exc.value.code == "CORPUS_MISSING"
    with pytest.raises(CorpusFreezeError) as exc:
        freeze_corpus({"pilot_version": "x", "cases": []})
    assert exc.value.code == "CORPUS_EMPTY"
    assert not verify_corpus_freeze(None)


def test_shipped_pilot_intake_shell_cannot_be_frozen() -> None:
    shell = json.loads((REPO_ROOT / "fixtures/vision_eval/pilot-manifest.json").read_text())
    with pytest.raises(CorpusFreezeError) as exc:
        freeze_corpus(shell)
    assert exc.value.code == "CORPUS_EMPTY"


def test_missing_validator_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(CorpusFreezeError) as exc:
        load_pilot_validator(tmp_path / "missing.py")
    assert exc.value.code == "CORPUS_VALIDATOR_UNAVAILABLE"


def test_frozen_record_carries_hashes_not_rights_payloads() -> None:
    record = freeze_corpus(admitted_manifest())
    dumped = json.dumps(record.model_dump(mode="json"))
    assert "source_url" not in dumped
    assert "rights_and_consent" not in dumped
    assert "reviewers" not in dumped


def test_verify_rejects_duplicate_or_miscounted_cases() -> None:
    from intelligence.evaluation_corpus import freeze_corpus, verify_corpus_freeze
    from tests.eval007_helpers import admitted_manifest

    record = freeze_corpus(admitted_manifest())
    dup = record.model_copy(update={"cases": record.cases + record.cases[:1]})
    dup = dup.model_copy(update={"record_sha256": dup.content_sha256()})
    assert not verify_corpus_freeze(dup)
    miscount = record.model_copy(update={"case_count": record.case_count + 1})
    miscount = miscount.model_copy(update={"record_sha256": miscount.content_sha256()})
    assert not verify_corpus_freeze(miscount)
