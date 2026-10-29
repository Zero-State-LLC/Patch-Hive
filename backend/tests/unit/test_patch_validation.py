"""Port resolution and validation of generated patches (spec 001 FR-016/017/019, OQ-04)."""

from types import SimpleNamespace

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
