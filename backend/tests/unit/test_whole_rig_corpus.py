"""Spec 009 T070a: spec 007's corpus admits whole-rig photos."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from intelligence.evaluation_corpus import (
    ADMITTED_STATUS,
    CorpusFreezeError,
    freeze_corpus,
    load_pilot_validator,
    verify_corpus_freeze,
)
from intelligence.evaluation_enablement import EnablementError, run_baseline_comparison
from tests.eval007_helpers import (
    HARNESS_SHA,
    POLICY,
    admitted_manifest,
    admitted_rig_manifest,
    assisted_cases,
    baseline_cases,
    image_hash,
)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "vision_eval" / "whole_rig"
validate = load_pilot_validator()


@pytest.fixture
def manifest() -> dict:
    return json.loads((FIXTURES / "manifest.json").read_text())


def test_the_fixture_corpus_passes_every_case_check(manifest) -> None:
    report = validate(manifest)

    assert report["errors"] == []
    assert report["case_count"] == 2
    # Plaits, Maths, Rings and Disting EX; the off-catalog Module isn't a catalog identity.
    assert report["identity_count"] == 4
    # Two photos are far from the 50 identities and eight cohorts admission needs.
    assert report["admission_status"] == "NOT_ADMITTED"


def _label(manifest: dict, index: int) -> dict:
    return manifest["cases"][0]["labels"][index]


@pytest.mark.parametrize(
    "change, error",
    [
        (lambda m: m["cases"][0].pop("labels"), "rig-a:labels_missing"),
        (
            lambda m: m["cases"][0]["image_asset_hashes"].append(image_hash("rig-a2")),
            "rig-a:rig_needs_one_photo",
        ),
        (lambda m: m["cases"][0].update(rows=0), "rig-a:rows_invalid"),
        (lambda m: _label(m, 0).update(kind="cable"), "rig-a:label_invalid:0"),
        (lambda m: _label(m, 0).update(start_hp=-1), "rig-a:label_invalid:0"),
        (lambda m: _label(m, 0).update(hp=0), "rig-a:label_invalid:0"),
        (lambda m: _label(m, 3).update(row_index=2), "rig-a:label_outside_rows:3"),
        (lambda m: _label(m, 1).update(start_hp=11), "rig-a:labels_overlap:1"),
        (lambda m: _label(m, 0).pop("name"), "rig-a:label_identity_missing:0"),
    ],
)
def test_a_label_a_photo_cant_be_scored_on_is_refused(manifest, change, error) -> None:
    change(manifest)

    assert error in validate(manifest)["errors"]


def test_an_open_set_photo_shows_an_off_catalog_module(manifest) -> None:
    case = manifest["cases"][1]
    case["partition"] = "unknown_open_set"

    assert "rig-b:open_set_case_without_open_set_label" in validate(manifest)["errors"]


def test_a_corpus_names_its_unit(manifest) -> None:
    manifest["unit"] = "rack"

    assert "invalid_unit" in validate(manifest)["errors"]


def test_a_whole_rig_corpus_at_size_is_admitted_and_frozen() -> None:
    manifest = admitted_rig_manifest()

    record = freeze_corpus(manifest)

    assert record.admission_status == ADMITTED_STATUS
    assert record.unit == "whole_rig"
    assert record.identity_count == 64
    assert all(case.labels_sha256 and case.expected_choice is None for case in record.cases)
    assert verify_corpus_freeze(record, manifest)
    assert not verify_corpus_freeze(record, {**manifest, "unit": "module"})


@pytest.mark.parametrize(
    "change",
    [
        lambda case: case["labels"][1].update(start_hp=11),
        lambda case: case.update(rows=2),
    ],
    ids=["a moved label", "another row"],
)
def test_what_a_photo_is_scored_on_is_frozen(change) -> None:
    manifest = admitted_rig_manifest()
    record = freeze_corpus(manifest)
    changed = copy.deepcopy(manifest)
    change(changed["cases"][5])

    refrozen = freeze_corpus(changed)

    assert not verify_corpus_freeze(record, changed)
    assert refrozen.case_index()["rig-005"].labels_sha256 != (
        record.case_index()["rig-005"].labels_sha256
    )


def test_a_corpus_of_no_known_unit_is_not_frozen() -> None:
    # Even past a validator that let it through.
    manifest = {**admitted_rig_manifest(), "unit": "rack"}

    def lenient(m: dict) -> dict:
        return {"errors": [], "admission_status": ADMITTED_STATUS, "identity_count": 64}

    with pytest.raises(CorpusFreezeError) as refused:
        freeze_corpus(manifest, validator=lenient)

    assert refused.value.code == "CORPUS_UNIT_INVALID"


def test_spec_007s_single_module_comparison_refuses_a_whole_rig_corpus() -> None:
    manifest = admitted_manifest()
    with pytest.raises(EnablementError) as refused:
        run_baseline_comparison(
            corpus=freeze_corpus(admitted_rig_manifest()),
            baseline_cases=baseline_cases(manifest),
            assisted_cases=assisted_cases(manifest),
            policy=POLICY,
            harness_sha=HARNESS_SHA,
            baseline_provider_id="fixture",
            assisted_provider_id="clef",
        )

    assert refused.value.code == "CORPUS_UNIT_NOT_SUPPORTED"


def test_a_single_module_corpus_freezes_as_it_did_before_whole_rig_photos() -> None:
    record = freeze_corpus(admitted_manifest())

    # Pinned from main before whole-rig cases existed.
    assert record.corpus_sha256 == (
        "1ea0e6da109f1c5e7d2369ddff4044108dbe291accf3ace6e6a112a9df84b48c"
    )
    assert record.record_sha256 == (
        "b5678f57ff79a86a24da0301efe52fd827acb49cde2979c55eaa99849b5abd13"
    )
    assert record.unit == "module"
