"""Spec 001 FR-001 (research R3): the IR hash covers inputs, not run identity."""

from dataclasses import replace

from core.ir import ModuleIR, PatchGenerationIR, PatchGenerationParams, RackStateIR


def _ir(**changes) -> PatchGenerationIR:
    rack = RackStateIR(
        rack_id=1,
        rack_name="Rig",
        case_hp=84,
        case_rows=2,
        modules=[ModuleIR(1, "VCO", "vco", 0, 0), ModuleIR(2, "VCA", "vca", 10, 0)],
    )
    ir = PatchGenerationIR(
        run_id="run-a",
        rack_state=rack,
        seed=42,
        params=PatchGenerationParams(),
        engine_version="1.0.0",
        abx_core_version="1.3",
        created_at="2026-10-29T00:00:00+00:00",
        git_commit="abc123",
        host="host-a",
    )
    return replace(ir, **changes)


def test_hash_is_32_characters_and_repeatable():
    first = _ir().get_canonical_hash()
    assert len(first) == 32
    assert first == _ir().get_canonical_hash()


def test_changed_inventory_changes_the_hash():
    other = _ir()
    other.rack_state.modules.append(ModuleIR(3, "VCF", "vcf", 18, 0))
    assert other.get_canonical_hash() != _ir().get_canonical_hash()


def test_changed_params_seed_or_versions_change_the_hash():
    base = _ir().get_canonical_hash()
    assert _ir(seed=43).get_canonical_hash() != base
    assert _ir(params=PatchGenerationParams(prefer_simple=True)).get_canonical_hash() != base
    assert _ir(engine_version="1.1.0").get_canonical_hash() != base
    assert _ir(abx_core_version="1.4").get_canonical_hash() != base


def test_run_id_time_commit_and_host_do_not_change_the_hash():
    moved = _ir(
        run_id="run-b", created_at="2027-01-01T00:00:00+00:00", git_commit="def456", host="host-b"
    )
    assert moved.get_canonical_hash() == _ir().get_canonical_hash()
