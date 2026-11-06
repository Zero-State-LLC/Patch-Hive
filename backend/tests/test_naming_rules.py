import re

from core.naming import name_patch_v2


class DummyModule:
    def __init__(self, module_type: str, name: str = ""):
        self.module_type = module_type
        self.name = name


def test_patch_name_is_deterministic():
    modules = {1: DummyModule("VCO"), 2: DummyModule("VCA")}
    connections = [
        {
            "from_module_id": 1,
            "from_port": "Audio Out",
            "to_module_id": 2,
            "to_port": "Audio In",
            "cable_type": "audio",
        }
    ]

    name_a = name_patch_v2(123, modules, connections)
    name_b = name_patch_v2(123, modules, connections)

    assert name_a == name_b


def test_patch_name_humor_gate():
    modules = {
        1: DummyModule("VCO"),
        2: DummyModule("ENV"),
    }
    connections = [
        {
            "from_module_id": 1,
            "from_port": "Audio Out",
            "to_module_id": 2,
            "to_port": "CV In",
            "cable_type": "cv",
        },
        {
            "from_module_id": 2,
            "from_port": "Env Out",
            "to_module_id": 1,
            "to_port": "FM In",
            "cable_type": "cv",
        },
    ]

    name = name_patch_v2(777, modules, connections)

    assert re.search(r"\(.+\)$", name)


def _cable(cable_type="audio", from_port="Audio Out", to_port="Audio In", from_id=1, to_id=2):
    return {
        "from_module_id": from_id,
        "from_port": from_port,
        "to_module_id": to_id,
        "to_port": to_port,
        "cable_type": cable_type,
    }


STRUCTURE_WORDS = (
    "Cross-Mod",
    "Clock-Lattice",
    "Gate-Choir",
    "Slew-Pulse",
    "Sample-Loop",
    "Reset Bloom",
    "Feedback Lace",
    "Accent Stack",
)


def test_no_seed_titles_a_plain_cable_with_a_structure_it_lacks():
    modules = {1: DummyModule("VCO"), 2: DummyModule("VCA")}

    for patch_id in range(300):
        name = name_patch_v2(patch_id, modules, [_cable()])
        assert not any(word in name for word in STRUCTURE_WORDS), name
        assert name.endswith("Signal Path")


def test_a_structure_word_needs_the_port_or_cable_that_earns_it():
    modules = {1: DummyModule("SEQ"), 2: DummyModule("VCO")}

    assert name_patch_v2(1, modules, [_cable("cv", "Sample Out", "CV In")]).endswith("Sample-Loop")
    assert name_patch_v2(1, modules, [_cable("cv", "CV Out", "Reset")]).endswith("Reset Bloom")
    assert name_patch_v2(1, modules, [_cable("cv", "Slew Out", "CV In")]).endswith("Slew-Pulse")
    assert name_patch_v2(1, modules, [_cable("gate", "Gate Out", "Gate In")]).endswith("Gate-Choir")


def test_accent_stack_needs_the_accent_module_on_the_cables_not_only_in_the_rack():
    modules = {1: DummyModule("VCO"), 2: DummyModule("VCA"), 3: DummyModule("ACCENT")}

    assert name_patch_v2(1, modules, [_cable()]).endswith("Signal Path")
    assert name_patch_v2(1, modules, [_cable("cv", "Out", "CV In", 3, 2)]).endswith("Accent Stack")


def test_the_plain_word_follows_the_shape_of_the_cables():
    modules = {
        1: DummyModule("VCO"),
        2: DummyModule("VCA"),
        3: DummyModule("VCF"),
        4: DummyModule("ENV"),
        5: DummyModule("LFO"),
        6: DummyModule("FX"),
        7: DummyModule("NOISE"),
        8: DummyModule("VCO"),
        9: DummyModule("MIX"),
    }
    audio = _cable(from_id=1, to_id=2)
    cases = {
        "Control Line": [_cable("cv", "CV Out", "V/Oct", 5, 1)],
        "Effect Send": [_cable(from_id=2, to_id=6)],
        "Filter Pluck": [audio, _cable("cv", "Out", "Cutoff CV", 4, 3)],
        "Filter Sweep": [audio, _cable("cv", "Out", "Cutoff CV", 5, 3)],
        "Drift Engine": [audio, _cable("cv", "Out", "V/Oct", 5, 1)],
        "Noise Voice": [_cable(from_id=7, to_id=2)],
        "Envelope Voice": [audio, _cable("cv", "Out", "CV In", 4, 2)],
        "Signal Blend": [_cable(from_id=1, to_id=9), _cable(from_id=8, to_id=9)],
        "Signal Path": [audio],
    }

    for word, cables in cases.items():
        assert name_patch_v2(1, modules, cables).endswith(word), word
