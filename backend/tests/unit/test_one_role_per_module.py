"""Owner decision 36: a Module fills one role in a Patch. Spec 001 D9: loops through other modules."""

from __future__ import annotations

import random

import pytest
from sqlalchemy.orm import Session

from core.ir import ConnectionIR
from modules.models import Module
from patches.engine import ModuleAnalyzer, PatchEngineConfig, PatchGenerator
from patches.validation import _route_loops_through_other_modules
from racks.models import Rack, RackModule

SEEDS = range(0, 60)


def _place(db: Session, rack: Rack, module_type: str, start_hp: int) -> Module:
    module = Module(
        brand="Test", name=f"{module_type} {start_hp}", hp=4, module_type=module_type, source="test",
        power_12v_ma=10, power_neg12v_ma=10,
    )
    db.add(module)
    db.flush()
    db.add(RackModule(rack_id=rack.id, module_id=module.id, row_index=0, start_hp=start_hp))
    db.flush()
    return module


def _patches(db: Session, rack: Rack, seed: int):
    return PatchGenerator(ModuleAnalyzer(db, rack), seed, PatchEngineConfig(max_patches=50)).generate_patches()


@pytest.mark.parametrize("seed", SEEDS)
def test_a_module_that_is_both_an_oscillator_and_an_lfo_never_does_both_in_one_patch(
    db_session: Session, sample_rack_empty: Rack, seed: int
) -> None:
    both = _place(db_session, sample_rack_empty, "VCO LFO", 0)
    _place(db_session, sample_rack_empty, "VCA", 4)
    _place(db_session, sample_rack_empty, "VCF", 8)
    _place(db_session, sample_rack_empty, "ENV", 12)
    for patch in _patches(db_session, sample_rack_empty, seed):
        ports = {c.from_port for c in patch.connections if c.from_module_id == both.id}
        assert not {"Audio Out", "LFO Out"} <= ports, patch.name


def test_such_a_module_can_still_fill_each_role_in_separate_patches(
    db_session: Session, sample_rack_empty: Rack
) -> None:
    both = _place(db_session, sample_rack_empty, "VCO LFO", 0)
    _place(db_session, sample_rack_empty, "VCO", 4)
    _place(db_session, sample_rack_empty, "VCA", 8)
    _place(db_session, sample_rack_empty, "VCF", 12)
    used = {
        c.from_port
        for seed in SEEDS
        for patch in _patches(db_session, sample_rack_empty, seed)
        for c in patch.connections
        if c.from_module_id == both.id
    }
    assert {"Audio Out", "LFO Out"} <= used


@pytest.mark.parametrize("seed", SEEDS)
def test_the_two_module_loop_the_t001_probe_found_is_gone(
    db_session: Session, sample_rack_empty: Rack, seed: int
) -> None:
    """A module that was both VCO and VCA, with a filter, used to wire 1 -> 2 -> 1."""
    _place(db_session, sample_rack_empty, "VCO VCA", 0)
    _place(db_session, sample_rack_empty, "VCF", 4)
    for patch in _patches(db_session, sample_rack_empty, seed):
        cables = [
            ConnectionIR(
                from_module_id=c.from_module_id, from_port=c.from_port, to_module_id=c.to_module_id,
                to_port=c.to_port, cable_type=c.cable_type,
            )
            for c in patch.connections
        ]
        assert not _route_loops_through_other_modules(cables), patch.name


@pytest.mark.parametrize("seed", [0, 7, 42])
def test_a_rack_of_single_class_modules_keeps_its_patches(
    db_session: Session, sample_rack_full: Rack, seed: int
) -> None:
    """The role check draws what rng.choice would, so these modules' patches don't change."""
    first = _patches(db_session, sample_rack_full, seed)
    assert first
    analyzer = ModuleAnalyzer(db_session, sample_rack_full)
    generator = PatchGenerator(analyzer, seed, PatchEngineConfig(max_patches=50))
    assert generator._pick(generator.rng, analyzer.all_modules, "x", {}).id == (
        random.Random(seed).choice(analyzer.all_modules).id
    )
    assert [p.name for p in first] == [p.name for p in _patches(db_session, sample_rack_full, seed)]


def _cable(source: int, target: int) -> ConnectionIR:
    return ConnectionIR(from_module_id=source, from_port="Out", to_module_id=target, to_port="In", cable_type="audio")


@pytest.mark.parametrize(
    "cables,looped",
    [
        ([_cable(1, 2), _cable(2, 3)], False),
        ([_cable(1, 2), _cable(2, 1)], True),
        ([_cable(1, 2), _cable(2, 3), _cable(3, 1)], True),
        ([_cable(1, 2), _cable(1, 3), _cable(2, 4), _cable(3, 4)], False),
        ([_cable(1, 1)], False),
    ],
)
def test_a_loop_means_a_route_through_other_modules(cables, looped) -> None:
    assert _route_loops_through_other_modules(cables) is looped
