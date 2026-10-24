"""Synthetic, in-test builders for Spec 007 evaluation/enablement tests.

These manifests and packets are synthetic test data only. They are not a
representative corpus and must never be committed as pilot evidence.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace

from core.config import Settings
from intelligence.clef_evaluation import LabeledCorpusCase, Modality
from intelligence.contracts import DecisionPacket
from intelligence.policy import DecisionPolicy, PolicyThresholds

COHORTS = (
    "clear_front_panel",
    "installed_rack",
    "partial_occlusion",
    "cable_obscured",
    "low_light_or_glare",
    "revision_or_panel_variant",
    "hard_negative",
    "unknown_open_set",
)
PARTITIONS = ("development", "validation", "locked_test")
CASE_COUNT = 64
HARNESS_SHA = "1" * 40
SOURCE_SHA = "2" * 40
APPROVED_AT = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)

POLICY = DecisionPolicy(
    PolicyThresholds(
        policy_version="test-policy-v1",
        auto_propose_at=0.9,
        user_review_at=0.65,
        probability_margin=0.1,
    )
)


def image_hash(case_id: str) -> str:
    return "sha256:" + hashlib.sha256(case_id.encode("ascii")).hexdigest()


def pilot_case(index: int) -> dict:
    case_id = f"case-{index:03d}"
    cohort = COHORTS[index % len(COHORTS)]
    open_set = cohort == "unknown_open_set"
    identity = f"maker:model-{index:03d}:rev-a"
    return {
        "case_id": case_id,
        "partition": "unknown_open_set" if open_set else PARTITIONS[index % len(PARTITIONS)],
        "cohort": cohort,
        "rights_and_consent": {
            "rights_status": "RIGHTS_CONFIRMED",
            "source_url": f"https://example.invalid/evidence/{case_id}",
        },
        "image_asset_hashes": [image_hash(case_id)],
        "scene_conditions": ["front_panel"],
        "ground_truth_inventory": [] if open_set else [identity],
        "ground_truth_status": "OPERATOR_VERIFIED",
        "annotation_status": "REVIEWED",
        "reviewers": ["operator-1"],
        "candidate_set_hash": f"candidate-set-{case_id}",
        "expected_choice": "none_of_above" if open_set else identity,
        "none_of_above_allowed": True,
        "contamination": {"used_for_tuning": False, "notes": None},
    }


def admitted_manifest() -> dict:
    return {
        "pilot_version": "patchhive.vision-pilot.test",
        "status": "SYNTHETIC_TEST_ONLY",
        "cases": [pilot_case(index) for index in range(CASE_COUNT)],
    }


def _packet(case_id: str, provider: str, selected: str, probabilities: dict[str, float]) -> DecisionPacket:
    return DecisionPacket(
        decision_id=f"{provider}-{case_id}",
        request_id=f"req-{case_id}",
        provider=provider,
        provider_version=f"{provider}-test",
        evidence_hash=f"evidence-{case_id}",
        answer_type="choice",
        selected_choice=selected,
        probabilities=probabilities,
        confidence=probabilities[selected],
        created_at=datetime(2026, 10, 24, tzinfo=timezone.utc),
    )


def _labeled(case: dict, packet: DecisionPacket) -> LabeledCorpusCase:
    text = int(case["case_id"].split("-")[1]) % 5 == 0
    return LabeledCorpusCase(
        case_id=case["case_id"],
        cohort=case["cohort"],
        modality=Modality.text if text else Modality.vision,
        expected_choice=case["expected_choice"],
        licensed_source="synthetic-test",
        packet=packet,
        image_sha256=None if text else case["image_asset_hashes"][0].split(":", 1)[1],
    )


def baseline_cases(manifest: dict) -> tuple[LabeledCorpusCase, ...]:
    """Abstaining baseline: always none_of_above at modest confidence."""
    rows = []
    for case in manifest["cases"]:
        other = case["expected_choice"] if case["expected_choice"] != "none_of_above" else "maker:other"
        probs = {"none_of_above": 0.6, other: 0.4}
        rows.append(_labeled(case, _packet(case["case_id"], "fixture", "none_of_above", probs)))
    return tuple(rows)


def assisted_cases(manifest: dict, provider: str = "clef", *, degrade: bool = False) -> tuple[LabeledCorpusCase, ...]:
    """Assisted condition. With degrade=True it is worse than the baseline."""
    rows = []
    for case in manifest["cases"]:
        expected = case["expected_choice"]
        if degrade:
            selected = "maker:wrong"
            probs = {selected: 0.95, expected: 0.05}
        else:
            alt = "none_of_above" if expected != "none_of_above" else "maker:other"
            probs = {expected: 0.95, alt: 0.05}
            selected = expected
        rows.append(_labeled(case, _packet(case["case_id"], provider, selected, probs)))
    return tuple(rows)


def staging_settings(**overrides) -> Settings:
    values = {"environment": "staging", "allow_production_payments": False}
    values.update(overrides)
    return Settings(**values)


def settings_namespace(**overrides) -> SimpleNamespace:
    values = {
        "environment": "staging",
        "allow_production_payments": False,
        "stripe_test_mode": True,
        "enable_clef_provider": False,
        "cors_origins": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)
