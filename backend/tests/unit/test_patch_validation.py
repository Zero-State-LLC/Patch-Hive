"""Port resolution and validation of generated patches (spec 001 FR-016/017/019, OQ-04)."""

from types import SimpleNamespace

import pytest

from core.ir import ConnectionIR, PatchGraphIR
from patches.validation import drop_feedback_patches, resolve_and_validate


def _module(module_id: int, name: str, ports: list[tuple[str, str]] | None = None):
    return SimpleNamespace(
        id=module_id, name=name, io_ports=[{"name": n, "type": t} for n, t in (ports or [])]
    )


def _patch(*cables: tuple[int, str, int, str]) -> PatchGraphIR:
    return PatchGraphIR(
        patch_name="P",
        category="Voice",
        connections=[ConnectionIR(a, fp, b, tp, "audio") for a, fp, b, tp in cables],
    )


VCO = _module(1, "VCO", [("V/Oct", "cv_in"), ("FM", "cv_in"), ("Out", "audio_out")])
VCF = _module(2, "VCF", [("In", "audio_in"), ("Cutoff CV", "cv_in"), ("LP Out", "audio_out")])
LFO = _module(3, "LFO", [("LFO 1 Out", "cv_out")])
BARE = _module(4, "Bare")  # no jacks on file
MODULES = {m.id: m for m in (VCO, VCF, LFO, BARE)}


def test_generic_roles_resolve_to_declared_jacks():
    patches, report = resolve_and_validate(
        [_patch((1, "Audio Out", 2, "Audio In"), (3, "LFO Out", 2, "Cutoff CV"), (3, "LFO Out", 1, "FM In"))],
        MODULES,
    )
    cables = [(c.from_port, c.to_port, c.port_status) for c in patches[0].connections]
    assert cables == [
        ("Out", "In", "declared"),
        ("LFO 1 Out", "Cutoff CV", "declared"),
        ("LFO 1 Out", "FM", "declared"),
    ]
    assert not report.blocking and report.findings == []


def test_keyword_preference_picks_the_pitch_input():
    patches, _ = resolve_and_validate([_patch((3, "LFO Out", 1, "V/Oct"))], MODULES)
    assert patches[0].connections[0].to_port == "V/Oct"


def _audio_leaves_from(outputs: list[str]) -> str:
    multimode = _module(5, "Multimode", [("In", "audio_in"), *((n, "audio_out") for n in outputs)])
    patches, _ = resolve_and_validate(
        [_patch((5, "Audio Out", 2, "Audio In"))], {**MODULES, multimode.id: multimode}
    )
    return patches[0].connections[0].from_port


@pytest.mark.parametrize(
    "outputs",
    [
        ["Highpass Output", "Bandpass Output", "Lowpass Output"],
        ["HIGH-PASS", "BAND-PASS", "LOW-PASS"],
        ["Band Out", "Low Pass Out"],
        ["OUT BP", "OUT LP"],
    ],
)
def test_an_audio_cable_leaves_a_multimode_filter_from_its_lowpass_jack(outputs):
    assert _audio_leaves_from(outputs) == outputs[-1]


def test_a_word_that_only_contains_low_is_not_a_lowpass_jack():
    assert _audio_leaves_from(["Highpass Output", "below 630Hz filter output"]) == "Audio Out"


def _input_end(role: str, inputs: list[str], jack_type: str = "cv_in"):
    source = _module(1, "Source", [("Out", "cv_out"), ("Audio", "audio_out"), ("Gate", "gate_out")])
    target = _module(2, "Target", [(name, jack_type) for name in inputs])
    from_port = {"cv_in": "Out", "audio_in": "Audio", "gate_in": "Gate"}[jack_type]
    patches, report = resolve_and_validate([_patch((1, from_port, 2, role))], {1: source, 2: target})
    return patches[0].connections[0], report


def _output_end(role: str, outputs: list[str], jack_type: str = "cv_out"):
    source = _module(1, "Source", [(name, jack_type) for name in outputs])
    target = _module(2, "Target", [("In", jack_type.replace("_out", "_in"))])
    patches, report = resolve_and_validate([_patch((1, role, 2, "In"))], {1: source, 2: target})
    return patches[0].connections[0], report


def test_a_cable_keeps_its_role_when_no_name_settles_the_jack():
    cable, report = _input_end("FM In", ["Damp CV", "Decay CV", "Timbre CV"])
    assert (cable.to_port, cable.port_status) == ("FM In", "generic")
    assert "SEVERAL_JACKS_FIT" in [f.code for f in report.findings]
    assert not report.blocking


@pytest.mark.parametrize(
    "role, inputs, expected",
    [
        ("V/Oct", ["Rise CV Input", "1 V/O Input"], "1 V/O Input"),
        ("V/Oct", ["Decay CV", "1v/Octave Input"], "1v/Octave Input"),
        ("FM In", ["Timbre CV", "Linear Thru-zero FM input"], "Linear Thru-zero FM input"),
        ("FM In", ["Timbre CV", "TZFM INPUT"], "TZFM INPUT"),
        ("CV In", ["ATK CV", "DEC CV", "VCA CV"], "VCA CV"),
        ("CV In", ["CHannel 1 DAMP CV INput", "CHannel 1 CONTROL INput"], "CHannel 1 CONTROL INput"),
        ("CV In", ["WIDTH CV", "LEVEL CV"], "LEVEL CV"),
        ("Cutoff CV", ["Resonance CV", "CVF"], "CVF"),
    ],
)
def test_a_name_settles_which_input_takes_the_cable(role, inputs, expected):
    cable, _ = _input_end(role, inputs)
    assert (cable.to_port, cable.port_status) == (expected, "declared")


@pytest.mark.parametrize(
    "role, outputs, jack_type, expected",
    [
        ("Envelope Out", ["Mirrored Contour Output", "Contour Output"], "cv_out", "Contour Output"),
        ("Envelope Out", ["Inverted Signal Output", "Non-Inverted Signal Output"], "cv_out", "Non-Inverted Signal Output"),
        ("Envelope Out", ["Inverted ADSR Output", "ADSR Output"], "cv_out", "ADSR Output"),
        ("LFO Out", ["Inverted LFO1 Output", "ADSR Output"], "cv_out", "Inverted LFO1 Output"),
        ("Audio Out", ["Out", "Aux"], "audio_out", "Out"),
        ("CV Out", ["Channel 1 Pressure Output", "Tuned Voltage Out X"], "cv_out", "Tuned Voltage Out X"),
        ("Audio Out", ["Feedback Output", "Mix Output"], "audio_out", "Mix Output"),
        ("Audio Out", ["Sine", "Triangle", "Sawtooth"], "audio_out", "Sawtooth"),
        ("Gate Out", ["TRIG OUT", "GATE OUT"], "gate_out", "GATE OUT"),
    ],
)
def test_a_name_settles_which_output_a_cable_leaves(role, outputs, jack_type, expected):
    cable, _ = _output_end(role, outputs, jack_type)
    assert (cable.from_port, cable.port_status) == (expected, "declared")


@pytest.mark.parametrize(
    "role, inputs, jack_type, expected",
    [
        ("Audio In", ["Audio Input Right", "Audio Input Left"], "audio_in", "Audio Input Left"),
        ("FX In", ["IN R", "IN L"], "audio_in", "IN L"),
        ("Audio In", ["IN B", "IN A"], "audio_in", "IN A"),
        ("CV In", ["CV2-IN LOG", "CV1-IN LIN"], "cv_in", "CV1-IN LIN"),
        ("Gate In", ["Hang Input", "Reset"], "gate_in", None),
    ],
)
def test_a_channel_mark_names_the_first_channel(role, inputs, jack_type, expected):
    cable, _ = _input_end(role, inputs, jack_type)
    assert cable.to_port == (expected or role)
    assert cable.port_status == ("declared" if expected else "generic")


def test_a_mixer_fills_its_numbered_channels_in_order():
    source = _module(1, "Source", [("Out", "audio_out")])
    mixer = _module(2, "Mixer", [("Channel 2 Input", "audio_in"), ("Channel 1 Input", "audio_in")])
    patches, _ = resolve_and_validate(
        [_patch((1, "Audio Out", 2, "In 1"), (1, "Audio Out", 2, "In 2"))], {1: source, 2: mixer}
    )
    assert [c.to_port for c in patches[0].connections] == ["Channel 1 Input", "Channel 2 Input"]


def test_a_second_cable_of_a_role_takes_the_next_channel():
    source = _module(1, "Source", [("Out", "cv_out")])
    vca = _module(2, "Quad VCA", [("CV 1", "cv_in"), ("CV 2", "cv_in")])
    patches, _ = resolve_and_validate(
        [_patch((1, "CV Out", 2, "CV In"), (1, "CV Out", 2, "CV In"))], {1: source, 2: vca}
    )
    assert [c.to_port for c in patches[0].connections] == ["CV 1", "CV 2"]


@pytest.mark.parametrize("role, inputs", [("V/Oct", ["CV1", "CV2"]), ("Cutoff CV", ["LEFT CV", "RIGHT CV"])])
def test_a_channel_mark_does_not_name_an_input_with_a_specific_job(role, inputs):
    cable, _ = _input_end(role, inputs)
    assert (cable.to_port, cable.port_status) == (role, "generic")


def test_a_side_jack_of_something_else_leaves_the_main_jack_unsettled():
    cable, _ = _output_end("CV Out", ["Inverted Ramp Output", "Gate Output"])
    assert (cable.from_port, cable.port_status) == ("CV Out", "generic")


@pytest.mark.parametrize("inputs", [["Voices CV Input", "1V/Oct Input", "Detune CV Input"], ["RATE CV", "1V/OCT"]])
def test_a_voltage_is_not_a_channel_number(inputs):
    cable, _ = _input_end("CV In", inputs)
    assert (cable.to_port, cable.port_status) == ("CV In", "generic")


def test_a_keyword_must_start_a_word():
    cable, _ = _input_end("CV In", ["Damp CV", "Time CV"])
    assert (cable.to_port, cable.port_status) == ("CV In", "generic")


def test_a_frequency_band_is_not_a_channel_number():
    cable, _ = _output_end("Audio Out", ["630Hz-1.7kHz filter output", "above 4.4kHz filter output"], "audio_out")
    assert (cable.from_port, cable.port_status) == ("Audio Out", "generic")


def test_the_only_jack_of_its_kind_takes_the_cable():
    cable, _ = _input_end("V/Oct", ["CV Input"])
    assert (cable.to_port, cable.port_status) == ("CV Input", "declared")


def test_a_jack_left_over_after_another_cable_is_not_the_only_jack_of_its_kind():
    source = _module(1, "Source", [("Out", "cv_out")])
    vco = _module(2, "VCO", [("V/Oct", "cv_in"), ("Damp CV", "cv_in")])
    patches, report = resolve_and_validate(
        [_patch((1, "CV Out", 2, "V/Oct"), (1, "CV Out", 2, "FM In"))], {1: source, 2: vco}
    )
    assert [c.to_port for c in patches[0].connections] == ["V/Oct", "FM In"]
    assert "SEVERAL_JACKS_FIT" in [f.code for f in report.findings]


def test_modules_without_jacks_stay_generic_and_unresolved():
    patches, report = resolve_and_validate([_patch((4, "Audio Out", 2, "Audio In"))], MODULES)
    cable = patches[0].connections[0]
    assert (cable.from_port, cable.to_port, cable.port_status) == ("Audio Out", "In", "generic")
    assert [f.code for f in report.findings] == ["PORT_NOT_ON_FILE"]
    assert not report.blocking


def test_a_partial_jack_list_is_unresolved_not_blocked():
    # The VCF declares one audio input; a second audio cable has no jack on file.
    _, report = resolve_and_validate(
        [_patch((1, "Audio Out", 2, "Audio In"), (4, "Audio Out", 2, "Audio In"))], MODULES
    )
    assert "INPUT_ALREADY_USED" in [f.code for f in report.findings]
    assert not report.blocking


def test_contradictions_block():
    _, outside = resolve_and_validate(
        [_patch((1, "Audio Out", 2, "Audio In"))], MODULES, allowed_module_ids={1}
    )
    assert outside.blocking and "MODULE_NOT_IN_INVENTORY" in [f.code for f in outside.findings]
    # A declared output used as a cable's destination.
    _, backwards = resolve_and_validate([_patch((2, "LP Out", 1, "Out"))], MODULES)
    assert backwards.blocking and "PORT_DIRECTION_MISMATCH" in [f.code for f in backwards.findings]


def test_feedback_and_empty_runs_are_only_flagged():
    _, loop = resolve_and_validate([_patch((2, "LP Out", 2, "Cutoff CV"))], MODULES)
    assert [f.code for f in loop.findings] == ["FEEDBACK_LOOP"] and not loop.blocking
    _, empty = resolve_and_validate([], MODULES)
    assert [f.code for f in empty.findings] == ["NO_PATCHES"] and not empty.blocking


def test_drop_feedback_patches_removes_looped_patches_and_reindexes_findings():
    graphs, report = resolve_and_validate(
        [
            _patch((4, "Audio Out", 2, "Audio In")),
            _patch((2, "LP Out", 2, "Cutoff CV")),
            _patch((3, "LFO Out", 4, "Audio In")),
        ],
        MODULES,
    )
    kept, dropped = drop_feedback_patches(graphs, report)
    assert dropped == 1 and kept == [graphs[0], graphs[2]]
    assert "FEEDBACK_LOOP" not in [f.code for f in report.findings]
    assert {f.patch_index for f in report.findings} <= {0, 1}


def test_drop_feedback_patches_is_a_no_op_without_loops():
    graphs, report = resolve_and_validate([_patch((1, "Audio Out", 2, "Audio In"))], MODULES)
    kept, dropped = drop_feedback_patches(graphs, report)
    assert dropped == 0 and kept == graphs


def test_a_loop_through_a_second_module_is_flagged_once():
    _, report = resolve_and_validate([_patch((1, "Out", 2, "In"), (2, "LP Out", 1, "FM"))], MODULES)
    assert [f.code for f in report.findings].count("FEEDBACK_LOOP") == 1 and not report.blocking
