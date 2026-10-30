"""Canonical contract and persistence invariant tests."""

from datetime import datetime, timezone

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from canon.contracts import (
    PatchEdge,
    PatchGraph,
    PatchNode,
    PatchPlan,
    PatchPort,
    PatchStep,
    RigMetricsPacket,
    ValidationIssue,
    ValidationReport,
    canonical_json,
    canonical_sha256,
)
from canon.models import (
    GeneratedPatchRecord,
    GenerationRunRecord,
    PatchLibraryRecord,
    RigRevisionRecord,
    UserPatchAnnotationRecord,
)
from canon.repository import create_run_with_library
from cases.models import Case
from community.models import User
from racks.models import Rack

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _artifact_fields(artifact_id: str = "artifact-1") -> dict[str, object]:
    return {
        "artifact_id": artifact_id,
        "entity_id": "entity-1",
        "generator_version": "1.0.0",
        "generation_seed": 7,
        "source_run_id": "run-1",
        "source_rig_revision_id": "rig-rev-1",
        "created_at": NOW,
    }


@given(st.dictionaries(st.text(min_size=1), st.integers(), max_size=20))
def test_canonical_json_is_independent_of_mapping_insertion_order(payload: dict[str, int]) -> None:
    reversed_payload = dict(reversed(list(payload.items())))
    assert canonical_json(payload) == canonical_json(reversed_payload)
    assert canonical_sha256(payload) == canonical_sha256(reversed_payload)


@given(st.floats(allow_nan=False, allow_infinity=False, width=64))
def test_canonical_numeric_encoding_is_stable(value: float) -> None:
    encoded = canonical_json({"value": value})
    assert encoded == canonical_json({"value": value})
    if value == 0:
        assert encoded == '{"value":0.0}'


def test_canonical_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"value": float("nan")})


def test_rig_metrics_packet_roundtrip_byte_identical() -> None:
    """Canon RigMetricsPacket seals and round-trips without historical patchhive schemas."""
    sealed = RigMetricsPacket(
        artifact_id="metrics-test-1",
        entity_id="rig-rev-test",
        generator_version="canon-metrics.1.0.0",
        generation_seed=7,
        source_run_id="gen-run-test",
        source_rig_revision_id="rig-rev-test",
        created_at=NOW,
        module_count=1,
        total_hp=12,
        routing_flex_score=2.5,
        confidence_notes=("fixture",),
    ).seal()

    j1 = sealed.canonical_json()
    restored = RigMetricsPacket.model_validate_json(j1)
    j2 = restored.canonical_json()
    assert j1 == j2
    assert restored.canonical_hash == sealed.canonical_hash
    assert restored.computed_hash() == sealed.canonical_hash


def test_patch_plan_requires_all_five_phases() -> None:
    with pytest.raises(ValidationError, match="seal"):
        PatchPlan(
            **_artifact_fields(),
            title="Open loop",
            intent="Demonstrate mandatory closure",
            steps=tuple(
                PatchStep(position=i, phase=phase, instruction=phase)
                for i, phase in enumerate(("prep", "threshold", "peak", "release"))
            ),
        )


def test_patch_graph_rejects_unknown_ports() -> None:
    output = PatchPort(
        port_id="osc.out",
        module_instance_id="osc",
        module_port_id="out",
        label="OUT",
        direction="output",
        signal_type="audio",
    )
    with pytest.raises(ValidationError, match="unknown port"):
        PatchGraph(
            **_artifact_fields(),
            nodes=(
                PatchNode(node_id="osc", module_instance_id="osc", label="VCO", ports=(output,)),
            ),
            edges=(
                PatchEdge(
                    edge_id="cable-1",
                    source_port_id="osc.out",
                    target_port_id="missing.in",
                    signal_type="audio",
                ),
            ),
        )


def test_validation_report_must_match_blocking_findings() -> None:
    with pytest.raises(ValidationError, match="valid must be false"):
        ValidationReport(
            **_artifact_fields(),
            valid=True,
            issues=(
                ValidationIssue(code="PORT_MISSING", severity="error", message="Missing port"),
            ),
        )


def _persist_hierarchy(db_session: Session) -> tuple[User, GeneratedPatchRecord]:
    user = User(username="canon-user", email="canon@example.com", password_hash="hash")
    case = Case(
        brand="PatchHive",
        name="Test Case",
        total_hp=84,
        rows=1,
        hp_per_row=[84],
        source="test",
    )
    db_session.add_all((user, case))
    db_session.flush()
    rack = Rack(user_id=user.id, case_id=case.id, name="Canon Rig")
    db_session.add(rack)
    db_session.flush()
    revision = RigRevisionRecord(
        id="rig-rev-1",
        rig_id=rack.id,
        schema_version="patchhive.canon.v1",
        canonical_rig={"modules": []},
        canonical_hash="a" * 64,
    )
    run = GenerationRunRecord(
        id="run-1",
        user_id=user.id,
        rig_revision_id=revision.id,
        schema_version="patchhive.canon.v1",
        generator_version="1.0.0",
        generation_seed=7,
        normalized_input_hash="b" * 64,
    )
    library = PatchLibraryRecord(
        id="library-1",
        run_id=run.id,
        artifact_manifest_hash="c" * 64,
        canonical_hash="d" * 64,
    )
    patch = GeneratedPatchRecord(
        id="patch-1",
        patch_library_id=library.id,
        position=0,
        name="Stable Current",
        patch_graph={},
        patch_plan={},
        validation_report={},
        variations=[],
        canonical_hash="e" * 64,
    )
    db_session.add_all((revision, run, library, patch))
    db_session.commit()
    return user, patch


def test_generated_patch_is_immutable_but_annotation_is_mutable(db_session: Session) -> None:
    user, patch = _persist_hierarchy(db_session)
    patch.name = "Mutated"
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    annotation = UserPatchAnnotationRecord(
        id="annotation-1", user_id=user.id, patch_id=patch.id, notes="First pass"
    )
    db_session.add(annotation)
    db_session.commit()
    annotation.notes = "Second pass"
    annotation.favorite = True
    db_session.commit()
    assert annotation.notes == "Second pass"
    assert annotation.favorite is True


def test_run_can_own_only_one_patch_library(db_session: Session) -> None:
    _user, _patch = _persist_hierarchy(db_session)
    db_session.add(
        PatchLibraryRecord(
            id="library-2",
            run_id="run-1",
            artifact_manifest_hash="f" * 64,
            canonical_hash="0" * 64,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert db_session.get(PatchLibraryRecord, "library-1") is not None


def test_regeneration_creates_a_new_run_without_mutating_prior_run(db_session: Session) -> None:
    user, _patch = _persist_hierarchy(db_session)
    first_run = db_session.get(GenerationRunRecord, "run-1")
    first_hash = first_run.normalized_input_hash
    second_run, second_library = create_run_with_library(
        db_session,
        run_id="run-2",
        library_id="library-2",
        user_id=user.id,
        rig_revision_id="rig-rev-1",
        generator_version="1.0.0",
        generation_seed=8,
        normalized_input={"rig_revision_id": "rig-rev-1", "seed": 8},
        artifact_manifest_hash="f" * 64,
        library_hash="0" * 64,
    )
    db_session.commit()
    assert second_run.id != first_run.id
    assert second_library.run_id == second_run.id
    assert db_session.get(GenerationRunRecord, "run-1").normalized_input_hash == first_hash


def test_rig_metrics_packet_sealed_before_fr027_keeps_its_hash() -> None:
    """Hashes below were sealed by the schema before rig_id, category_counts and the five
    extra scores existed (main at 3faaa63). They must still verify and round-trip."""
    from datetime import datetime, timezone

    common = dict(
        entity_id="rev-1",
        generator_version="canon-metrics.1.0.0",
        generation_seed=7,
        source_run_id="run-1",
        source_rig_revision_id="rev-1",
        created_at=datetime(2025, 12, 21, tzinfo=timezone.utc),
        routing_flex_score=0.5,
    )
    with_hp = RigMetricsPacket(
        artifact_id="metrics-legacy", module_count=2, total_hp=20, confidence_notes=("n",), **common
    ).seal()
    no_hp = RigMetricsPacket(artifact_id="metrics-legacy2", module_count=2, **common).seal()
    assert with_hp.canonical_hash == "dba520d94b6528dc4ecc4273b477dc7fd5239544f5a7f696ba99247a60eaa0cc"
    assert no_hp.canonical_hash == "19c9a4710a02b2764fe596330cb2ef83501ceac5ae307f7beb5282eae65f3d46"
    restored = RigMetricsPacket.model_validate_json(with_hp.canonical_json())
    assert restored.computed_hash() == with_hp.canonical_hash
    # A packet that sets the new fields hashes differently.
    assert RigMetricsPacket(
        artifact_id="metrics-legacy", module_count=2, total_hp=20, confidence_notes=("n",),
        rig_id="1", **common,
    ).seal().canonical_hash != with_hp.canonical_hash
