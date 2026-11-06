"""A patch's title and intent say what its cables do, and no more.

The first three tests are the patches that exposed this, from a book seeded at v0.3.0-alpha.14:
"First Sample-Loop", "Clean Reset Bloom" and "Pocket Sample-Loop". The checks across seeds read the
final cables on their own terms, so they do not share a line with the code that writes the words.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Set

import pytest
from sqlalchemy.orm import Session

from core.ir import PatchGraphIR
from modules.models import Module
from patches.engine import PatchEngineConfig, generate_patches_for_rack, generate_patches_with_ir
from patches.models import Patch
from racks.models import Rack, RackModule

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("seed_golden_demo_intent", ROOT / "scripts" / "seed_golden_demo.py")
seed = importlib.util.module_from_spec(spec)
sys.modules["seed_golden_demo_intent"] = seed
spec.loader.exec_module(seed)

GOLDEN_SEED = json.loads((ROOT / "fixtures" / "golden_demo_seed.json").read_text())["seed"]
SEEDS = range(GOLDEN_SEED, GOLDEN_SEED + 30)


def _seeded_rack(db: Session) -> Rack:
    result = seed.seed_golden_demo(db, environment="test")
    return db.get(Rack, result.rig_id)


def _golden_patch(db: Session, seed_offset: int) -> Patch:
    _seeded_rack(db)
    return db.query(Patch).filter(Patch.generation_seed == GOLDEN_SEED + seed_offset).one()


def _cables(db: Session, patch: Patch) -> List[tuple]:
    def name(module_id: int) -> str:
        return db.get(Module, module_id).name

    return [
        (name(c["from_module_id"]), c["from_port"], name(c["to_module_id"]), c["to_port"])
        for c in patch.connections
    ]


def test_a_sequencer_into_a_pitch_input_says_only_that(db_session: Session) -> None:
    """Was "First Sample-Loop": "Self-evolving generative patch with modulation"."""
    patch = _golden_patch(db_session, 1000)

    assert _cables(db_session, patch) == [("Rene 2", "CV X", "Plaits", "V/Oct")]
    assert patch.name == "First Control Line"
    assert patch.description == "Rene 2 into Plaits pitch. No audio is patched."


def test_a_mixer_into_an_effect_says_nothing_feeds_the_mixer(db_session: Session) -> None:
    """Was "Clean Reset Bloom": "Texture-FX processing chain using Clouds"."""
    patch = _golden_patch(db_session, 3000)

    assert _cables(db_session, patch) == [("Mixup", "Mix Out", "Clouds", "In L")]
    assert patch.name == "Clean Effect Send"
    assert patch.description == "Mixup into Clouds. Nothing is patched into Mixup."


def test_a_voice_through_an_effect_names_the_vca_and_its_empty_cv(db_session: Session) -> None:
    """Was "Pocket Sample-Loop": "Even VCO through Clouds"."""
    patch = _golden_patch(db_session, 9000)

    assert _cables(db_session, patch) == [
        ("Even VCO", "Audio Out", "Quad VCA", "In 1"),
        ("Quad VCA", "Out 1", "Clouds", "In L"),
    ]
    assert patch.name == "Pocket Effect Send"
    assert patch.description == "Even VCO through Quad VCA into Clouds. No CV is patched into Quad VCA."


def test_a_patch_with_nothing_open_keeps_its_rule_sentence_alone(db_session: Session) -> None:
    patch = _golden_patch(db_session, 5001)

    assert patch.name == "Offset Gate-Choir"
    assert patch.description == "Rene 2 sequences A-110-1"


def test_the_seeded_rig_keeps_all_fourteen_patches(db_session: Session) -> None:
    """Saying less about a thin patch is not dropping it. Whether it stays is the owner's call."""
    assert seed.seed_golden_demo(db_session, environment="test").patch_count == 14


# --- Across seeds, on the seeded rig -----------------------------------------------------


def _kind(module: Module) -> str:
    module_type = module.module_type.upper()
    return next((k for k in ("VCO", "NOISE", "VCF", "VCA", "ENV", "LFO", "SEQ", "MIX", "FX") if k in module_type), "?")


def _graphs_across_seeds(db: Session) -> Iterator[tuple]:
    rack = _seeded_rack(db)
    modules = {m.id: m for m in db.query(Module).all()}
    config = PatchEngineConfig(allow_feedback=True)
    for generation_seed in SEEDS:
        for graph in generate_patches_with_ir(db, rack, seed=generation_seed, config=config)[1]:
            yield graph, modules


def _open_on_the_cables(graph: PatchGraphIR, modules: Dict[int, Module]) -> Set[str]:
    """Each sentence these cables call for, worked out from the cables alone."""
    audio = [c for c in graph.connections if c.cable_type == "audio"]
    audio_in = {c.to_module_id for c in audio}
    cv_in = {c.to_module_id for c in graph.connections if c.cable_type == "cv"}
    gate_in = {c.to_module_id for c in graph.connections if c.cable_type == "gate"}

    expected: Set[str] = set() if audio else {"No audio is patched"}
    for cable in audio:
        sender, receiver = modules[cable.from_module_id], modules[cable.to_module_id]
        if _kind(sender) not in ("VCO", "NOISE") and sender.id not in audio_in:
            expected.add(f"Nothing is patched into {sender.name}")
        if _kind(receiver) == "VCA" and receiver.id not in cv_in:
            expected.add(f"No CV is patched into {receiver.name}")
    for cable in graph.connections:
        sender = modules[cable.from_module_id]
        if _kind(sender) == "ENV" and sender.id not in gate_in:
            expected.add(f"No gate is patched into {sender.name}")
    return expected


def _stated_in_the_intent(description: str) -> Set[str]:
    openers = ("No audio", "Nothing is patched", "No CV is patched", "No gate is patched")
    return {s.rstrip(".") for s in description.split(". ") if s.startswith(openers)}


def test_the_intent_states_exactly_what_the_cables_leave_open(db_session: Session) -> None:
    for graph, modules in _graphs_across_seeds(db_session):
        assert _stated_in_the_intent(graph.description) == _open_on_the_cables(graph, modules), graph.description


def test_the_intent_names_only_modules_on_the_cables(db_session: Session) -> None:
    for graph, modules in _graphs_across_seeds(db_session):
        wired = {c.from_module_id for c in graph.connections} | {c.to_module_id for c in graph.connections}
        named = {m.id for m in modules.values() if m.name in graph.description}
        assert named <= wired, graph.description


def _has(graph: PatchGraphIR, modules: Dict[int, Module], source: str, destination: str = "") -> bool:
    return any(
        _kind(modules[c.from_module_id]) == source and (not destination or _kind(modules[c.to_module_id]) == destination)
        for c in graph.connections
    )


TITLE_WORDS: Dict[str, Callable[[PatchGraphIR, Dict[int, Module]], bool]] = {
    "Gate-Choir": lambda g, m: any(c.cable_type == "gate" for c in g.connections),
    "Control Line": lambda g, m: not any(c.cable_type == "audio" for c in g.connections),
    "Effect Send": lambda g, m: any(c.cable_type == "audio" and _kind(m[c.to_module_id]) == "FX" for c in g.connections),
    "Filter Pluck": lambda g, m: _has(g, m, "ENV", "VCF"),
    "Filter Sweep": lambda g, m: _has(g, m, "LFO", "VCF"),
    "Drift Engine": lambda g, m: _has(g, m, "LFO"),
    "Noise Voice": lambda g, m: _has(g, m, "NOISE"),
    "Envelope Voice": lambda g, m: _has(g, m, "ENV"),
    "Signal Blend": lambda g, m: sum(c.cable_type == "audio" for c in g.connections) > len({c.to_module_id for c in g.connections if c.cable_type == "audio"}),
    "Signal Path": lambda g, m: any(c.cable_type == "audio" for c in g.connections),
}


def test_every_title_word_is_earned_by_the_cables(db_session: Session) -> None:
    for graph, modules in _graphs_across_seeds(db_session):
        word = next((w for w in TITLE_WORDS if graph.patch_name.endswith(w)), None)
        assert word is not None, f"{graph.patch_name}: a word no test can check"
        assert TITLE_WORDS[word](graph, modules), f"{graph.patch_name}: {graph.description}"


# --- Templates thinned by what the rack lacks ----------------------------------------------


def _rack_of(db: Session, rack: Rack, *module_types: str) -> Rack:
    for index, module_type in enumerate(module_types):
        module = Module(
            brand="Test", name=f"{module_type} {index}", hp=4, module_type=module_type, source="test",
            power_12v_ma=10, power_neg12v_ma=10,
        )
        db.add(module)
        db.flush()
        db.add(RackModule(rack_id=rack.id, module_id=module.id, row_index=0, start_hp=index * 4))
    db.commit()
    return rack


def _only_patch(db: Session, rack: Rack, *module_types: str) -> str:
    patches = generate_patches_for_rack(db, _rack_of(db, rack, *module_types), seed=1)
    assert len(patches) == 1
    return patches[0].description


@pytest.mark.parametrize(
    "module_types, expected",
    [
        # No filter, so nothing is subtracted.
        (("VCO", "VCA"), "VCO 0 into VCA 1. No CV is patched into VCA 1."),
        (("VCO", "VCA", "ENV"), "VCO 0 into VCA 1, ENV 2 into VCA 1 CV. No gate is patched into ENV 2."),
        # No envelope, so nothing shapes the noise.
        (("NOISE", "VCA"), "NOISE 0 into VCA 1. No CV is patched into VCA 1."),
        (("NOISE", "VCA", "ENV"), "Noise voice shaped by ENV 2. No gate is patched into ENV 2."),
        (("SEQ", "VCO"), "SEQ 0 into VCO 1 pitch. No audio is patched."),
        (("MIX", "FX"), "MIX 0 into FX 1. Nothing is patched into MIX 0."),
    ],
)
def test_a_thin_patch_says_what_it_has(
    db_session: Session, sample_rack_empty: Rack, module_types: tuple, expected: str
) -> None:
    assert _only_patch(db_session, sample_rack_empty, *module_types) == expected


def test_two_lfos_are_named_but_a_rack_with_every_module_still_patches_no_audio(
    db_session: Session, sample_rack_empty: Rack
) -> None:
    """The generative rule never wires audio on any rack, so lacking a module is not the cause."""
    rack = _rack_of(db_session, sample_rack_empty, "SEQ", "VCO", "VCF", "LFO", "LFO")

    generative = next(p for p in generate_patches_for_rack(db_session, rack, seed=1) if p.category == "Generative")

    assert len(generative.connections) == 3
    assert generative.description == (
        "SEQ 0 into VCO 1 pitch, LFO 3 into VCO 1 FM, LFO 4 into VCF 2 cutoff. No audio is patched."
    )


def test_a_longer_audio_route_names_every_stop(db_session: Session, sample_rack_empty: Rack) -> None:
    from patches.engine import Connection, ModuleAnalyzer, PatchGenerator

    rack = _rack_of(db_session, sample_rack_empty, "VCO", "VCF", "VCA", "FX")
    generator = PatchGenerator(ModuleAnalyzer(db_session, rack), 1, PatchEngineConfig())
    vco, vcf, vca, fx = generator.analyzer.vcos[0], generator.analyzer.vcfs[0], generator.analyzer.vcas[0], generator.analyzer.effects[0]

    route = generator._route(
        [
            Connection(vco.id, "Audio Out", vcf.id, "Audio In", "audio"),
            Connection(vcf.id, "Audio Out", vca.id, "Audio In", "audio"),
            Connection(vca.id, "Audio Out", fx.id, "FX In", "audio"),
        ]
    )

    assert route == "VCO 0 through VCF 1 and VCA 2 into FX 3"
