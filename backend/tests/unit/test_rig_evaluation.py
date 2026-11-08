"""Spec 009 T070a: the whole-rig harness, on the two-photo fixture corpus.

The expected values are worked by hand from `fixtures/vision_eval/whole_rig/`:

- rig-a: Plaits, Maths and a Blank Panel are read where they are (Maths 1 HP off). Disting EX
  is read as Rings. The off-catalog Module is read as unknown, 1 HP off. One Sighting has no
  label under it, and the not-Eurorack Sighting isn't a detection.
- rig-b: Rings and Plaits are read (Plaits 2 HP off), Maths is missed, and one Sighting has no
  label under it.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from evidence.rig_evaluation import RigEvaluationError, evaluate_rig_readings, rig_cases
from intelligence import evaluation
from tests.eval007_helpers import POLICY

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "vision_eval" / "whole_rig"


class FixtureCatalog:
    def __init__(self, rows: list[dict]) -> None:
        self._ids = {(row["maker"], row["name"]): row["module_id"] for row in rows}

    def module_id(self, maker: str, name: str) -> int | None:
        return self._ids.get((maker, name))


@pytest.fixture
def manifest() -> dict:
    return json.loads((FIXTURES / "manifest.json").read_text())


@pytest.fixture
def recorded() -> dict:
    return json.loads((FIXTURES / "answers.json").read_text())


def _evaluate(manifest: dict, recorded: dict, answers: dict | None = None):
    return evaluate_rig_readings(
        rig_cases(manifest),
        recorded["answers"] if answers is None else answers,
        catalog=FixtureCatalog(recorded["catalog"]),
        policy=POLICY,
    )


def test_the_fixture_corpus_scores_as_worked_by_hand(manifest, recorded) -> None:
    metrics = _evaluate(manifest, recorded)

    assert metrics.photo_count == 2
    assert metrics.failed_photos == {}
    assert metrics.label_count == 8
    assert metrics.sighting_count == 9
    assert metrics.matched_count == 7
    assert metrics.detection_recall == pytest.approx(7 / 8)
    assert metrics.detection_precision == pytest.approx(7 / 9)
    assert metrics.identity_accuracy == pytest.approx(6 / 7)
    assert metrics.position_error_hp_mean == pytest.approx(4 / 7)
    assert metrics.position_error_hp_max == 2
    assert metrics.false_canonicalization_count == 0


def test_false_canonicalization_is_replayed_for_every_sighting(
    manifest, recorded, monkeypatch
) -> None:
    # The count comes from the resolution machine, not a constant: a machine that let the
    # policy write canon on its own would count every Sighting of both photos.
    monkeypatch.setattr(evaluation, "canon_write_permitted", lambda _machine: True)

    assert _evaluate(manifest, recorded).false_canonicalization_count == 10


def test_a_photo_with_no_answer_misses_every_label(manifest, recorded) -> None:
    answers = {**recorded["answers"], "rig-a": None}

    metrics = _evaluate(manifest, recorded, answers)

    assert metrics.failed_photos == {"rig-a": "NO_ANSWER"}
    assert metrics.label_count == 8
    assert metrics.sighting_count == 3
    assert metrics.matched_count == 2
    assert metrics.detection_recall == pytest.approx(2 / 8)
    assert metrics.detection_precision == pytest.approx(2 / 3)
    assert metrics.identity_accuracy == pytest.approx(1.0)
    assert metrics.position_error_hp_mean == pytest.approx(1.0)
    assert metrics.position_error_hp_max == 2


def test_an_answer_a_reading_would_refuse_fails_its_photo(manifest, recorded) -> None:
    outside = copy.deepcopy(recorded["answers"]["rig-b"])
    outside["sightings"][0]["row_index"] = 1
    answers = {"rig-a": {"sightings": "none"}, "rig-b": outside}

    metrics = _evaluate(manifest, recorded, answers)

    assert metrics.failed_photos == {"rig-a": "ANSWER_MALFORMED", "rig-b": "ROW_OUTSIDE_PHOTO"}
    assert metrics.sighting_count == metrics.matched_count == 0
    assert metrics.detection_recall == 0
    assert metrics.detection_precision is None
    assert metrics.identity_accuracy is None
    assert metrics.position_error_hp_mean is None
    assert metrics.position_error_hp_max is None


def test_one_sighting_matches_one_label(manifest, recorded) -> None:
    # A second Sighting over rig-b's Rings finds no label left to match, so it is a false
    # detection rather than a second hit.
    answers = copy.deepcopy(recorded["answers"])
    answers["rig-b"]["sightings"].append(copy.deepcopy(answers["rig-b"]["sightings"][0]))

    metrics = _evaluate(manifest, recorded, answers)

    assert metrics.sighting_count == 10
    assert metrics.matched_count == 7
    assert metrics.detection_precision == pytest.approx(7 / 10)


def test_a_sighting_matches_only_in_its_own_row(manifest, recorded) -> None:
    # rig-a's Blank Panel read a row lower, where nothing is labelled at 32 HP.
    answers = copy.deepcopy(recorded["answers"])
    answers["rig-a"]["sightings"][2]["row_index"] = 1

    metrics = _evaluate(manifest, recorded, answers)

    assert metrics.sighting_count == 9
    assert metrics.matched_count == 6


def test_answers_must_be_for_exactly_the_corpus(manifest, recorded) -> None:
    with pytest.raises(RigEvaluationError) as missing:
        _evaluate(manifest, recorded, {"rig-a": recorded["answers"]["rig-a"]})
    with pytest.raises(RigEvaluationError) as extra:
        _evaluate(manifest, recorded, {**recorded["answers"], "rig-c": None})

    assert missing.value.code == extra.value.code == "ANSWERS_NOT_FOR_CORPUS"


def test_a_label_the_catalog_cannot_name_is_refused(manifest, recorded) -> None:
    catalog = [row for row in recorded["catalog"] if row["name"] != "Disting EX"]

    with pytest.raises(RigEvaluationError) as refused:
        _evaluate(manifest, {**recorded, "catalog": catalog})

    assert refused.value.code == "LABEL_NOT_IN_CATALOG"
    assert "rig-a" in str(refused.value)


def test_only_a_whole_rig_corpus_is_read_as_rig_cases(manifest) -> None:
    with pytest.raises(RigEvaluationError) as refused:
        rig_cases({**manifest, "unit": None})

    assert refused.value.code == "NOT_A_WHOLE_RIG_CORPUS"


def test_a_corpus_the_validator_refuses_is_not_scored(manifest) -> None:
    # Maths moved over Plaits: two labels in one span can't both be scored.
    manifest["cases"][0]["labels"][1]["start_hp"] = 11

    with pytest.raises(RigEvaluationError) as refused:
        rig_cases(manifest)

    assert refused.value.code == "RIG_CORPUS_INVALID"
    assert "rig-a:labels_overlap:1" in str(refused.value)


@pytest.mark.parametrize("field, value", [("open_set", "yes"), ("row_index", True), ("hp", 12.0)])
def test_a_label_is_read_as_strictly_as_the_validator_reads_it(manifest, field, value) -> None:
    # The validator takes only a real true and real whole numbers; read loosely, "yes"
    # would score a catalog Module as off-catalog.
    manifest["cases"][0]["labels"][0][field] = value

    with pytest.raises(RigEvaluationError) as refused:
        rig_cases(manifest, validator=lambda _m: {"errors": []})

    assert refused.value.code == "RIG_CASE_INVALID"
