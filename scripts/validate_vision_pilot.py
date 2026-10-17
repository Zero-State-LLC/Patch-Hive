#!/usr/bin/env python3
"""Validate the governed real-world vision pilot intake.

This validator deliberately reports NOT_COMPUTABLE until admitted cases satisfy
the corpus contract. It never promotes a case or chooses production thresholds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ALLOWED_PARTITIONS = {
    "development", "validation", "locked_test", "adversarial_degraded", "unknown_open_set"
}
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

REQUIRED_COHORTS = {
    "clear_front_panel", "installed_rack", "partial_occlusion", "cable_obscured",
    "low_light_or_glare", "revision_or_panel_variant", "hard_negative", "unknown_open_set"
}


def stable_sha(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def validate(manifest: dict) -> dict:
    errors: list[str] = []
    cases = manifest.get("cases", [])
    seen: set[str] = set()
    partitions = Counter()
    cohorts = Counter()
    identities: set[str] = set()
    image_hash_partition: dict[str, str] = {}

    for case in cases:
        cid = case.get("case_id")
        if not cid or cid in seen:
            errors.append(f"invalid_or_duplicate_case_id:{cid}")
        seen.add(cid)
        partition = case.get("partition")
        if partition not in ALLOWED_PARTITIONS:
            errors.append(f"{cid}:invalid_partition")
        else:
            partitions[partition] += 1
        cohort = case.get("cohort")
        if cohort:
            cohorts[cohort] += 1
        rights = case.get("rights_and_consent", {})
        if rights.get("rights_status") != "RIGHTS_CONFIRMED":
            errors.append(f"{cid}:rights_not_confirmed")
        if not str(rights.get("source_url", "")).strip():
            errors.append(f"{cid}:rights_source_url_missing")
        if case.get("annotation_status") != "REVIEWED":
            errors.append(f"{cid}:annotation_not_reviewed")
        if case.get("ground_truth_status") not in {"OPERATOR_VERIFIED", "TWO_SOURCE_VERIFIED"}:
            errors.append(f"{cid}:ground_truth_not_verified")
        if not case.get("reviewers"):
            errors.append(f"{cid}:missing_reviewer")
        if case.get("none_of_above_allowed") is not True:
            errors.append(f"{cid}:none_of_above_missing")
        if not case.get("candidate_set_hash"):
            errors.append(f"{cid}:candidate_set_hash_missing")
        expected_choice = case.get("expected_choice")
        if not expected_choice:
            errors.append(f"{cid}:expected_choice_missing")
        elif partition != "unknown_open_set" and expected_choice not in set(case.get("ground_truth_inventory", [])):
            errors.append(f"{cid}:expected_choice_not_in_ground_truth")
        hashes = case.get("image_asset_hashes", [])
        if not hashes:
            errors.append(f"{cid}:image_hash_missing")
        elif any(not isinstance(value, str) or not SHA256_RE.fullmatch(value) for value in hashes):
            errors.append(f"{cid}:invalid_image_hash")
        else:
            for image_hash in hashes:
                prior_partition = image_hash_partition.get(image_hash)
                if prior_partition is not None and prior_partition != partition:
                    errors.append(f"{cid}:cross_partition_image_leakage:{image_hash}")
                image_hash_partition.setdefault(image_hash, partition)
        if partition == "unknown_open_set" and expected_choice != "none_of_above":
            errors.append(f"{cid}:open_set_must_expect_none_of_above")
        contamination = case.get("contamination")
        if not isinstance(contamination, dict) or "used_for_tuning" not in contamination:
            errors.append(f"{cid}:contamination_status_missing")
        identities.update(case.get("ground_truth_inventory", []))
        if partition == "locked_test" and case.get("contamination", {}).get("used_for_tuning"):
            errors.append(f"{cid}:locked_test_contaminated")

    missing_cohorts = sorted(REQUIRED_COHORTS - set(cohorts))
    admitted = (
        not errors
        and 50 <= len(identities) <= 100
        and not missing_cohorts
        and partitions["validation"] > 0
        and partitions["locked_test"] > 0
        and partitions["unknown_open_set"] > 0
    )
    return {
        "pilot_version": manifest.get("pilot_version"),
        "manifest_sha256": stable_sha(manifest),
        "case_count": len(cases),
        "identity_count": len(identities),
        "partitions": dict(sorted(partitions.items())),
        "cohorts": dict(sorted(cohorts.items())),
        "missing_required_cohorts": missing_cohorts,
        "errors": errors,
        "admission_status": "ADMITTED_FOR_BASELINE" if admitted else "NOT_ADMITTED",
        "production_thresholds": "NOT_COMPUTABLE",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", default="fixtures/vision_eval/pilot-manifest.json")
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    print(json.dumps(validate(manifest), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
