"""Regression tests for governed vision-pilot admission."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "validate_vision_pilot.py"
SPEC = importlib.util.spec_from_file_location("validate_vision_pilot", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
validate = module.validate


def _case(case_id: str = "case-1", *, partition: str = "development") -> dict:
    return {
        "case_id": case_id,
        "partition": partition,
        "cohort": "clear_front_panel",
        "rights_and_consent": {
            "rights_status": "RIGHTS_CONFIRMED",
            "source_url": "https://example.invalid/evidence",
        },
        "image_asset_hashes": ["sha256:" + "a" * 64],
        "scene_conditions": ["front_panel"],
        "ground_truth_inventory": ["manufacturer:model:revision"],
        "ground_truth_status": "OPERATOR_VERIFIED",
        "annotation_status": "REVIEWED",
        "reviewers": ["operator-1"],
        "candidate_set_hash": "candidate-set-v1",
        "expected_choice": "manufacturer:model:revision",
        "none_of_above_allowed": True,
        "contamination": {"used_for_tuning": False, "notes": None},
    }


def _manifest(case: dict) -> dict:
    return {"pilot_version": "test", "cases": [case]}


def test_missing_rights_source_fails_closed() -> None:
    case = _case()
    case["rights_and_consent"]["source_url"] = ""
    result = validate(_manifest(case))
    assert "case-1:rights_source_url_missing" in result["errors"]
    assert result["admission_status"] == "NOT_ADMITTED"


def test_invalid_asset_hash_fails_closed() -> None:
    case = _case()
    case["image_asset_hashes"] = ["not-a-sha"]
    result = validate(_manifest(case))
    assert "case-1:invalid_image_hash" in result["errors"]


def test_open_set_requires_none_of_above_ground_truth() -> None:
    case = _case(partition="unknown_open_set")
    result = validate(_manifest(case))
    assert "case-1:open_set_must_expect_none_of_above" in result["errors"]


def test_locked_test_rejects_tuning_contamination() -> None:
    case = _case(partition="locked_test")
    case["contamination"]["used_for_tuning"] = True
    result = validate(_manifest(case))
    assert "case-1:locked_test_contaminated" in result["errors"]


def test_missing_contamination_declaration_fails_closed() -> None:
    case = _case()
    case.pop("contamination")
    result = validate(_manifest(case))
    assert "case-1:contamination_status_missing" in result["errors"]


def test_manifest_digest_is_order_independent_for_object_keys() -> None:
    case = _case()
    left = {"pilot_version": "test", "cases": [case]}
    right = {"cases": [case], "pilot_version": "test"}
    assert validate(left)["manifest_sha256"] == validate(right)["manifest_sha256"]


def test_expected_choice_must_match_verified_ground_truth() -> None:
    case = _case()
    case["expected_choice"] = "different:module"
    result = validate(_manifest(case))
    assert "case-1:expected_choice_not_in_ground_truth" in result["errors"]


def test_same_image_hash_cannot_cross_partitions() -> None:
    first = _case("case-1", partition="development")
    second = _case("case-2", partition="locked_test")
    result = validate({"pilot_version": "test", "cases": [first, second]})
    assert any("cross_partition_image_leakage" in error for error in result["errors"])
    assert result["admission_status"] == "NOT_ADMITTED"
