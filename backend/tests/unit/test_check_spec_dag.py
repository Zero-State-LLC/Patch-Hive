"""Tests for the specs/*/tasks.md dependency-graph checker."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "check_spec_dag.py"
SPEC = spec_from_file_location("check_spec_dag", SCRIPT)
assert SPEC and SPEC.loader
module = module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _feature(root: Path, name: str, tasks: str, spec: str = "# spec\n") -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "spec.md").write_text(spec)
    (d / "plan.md").write_text("# plan\n")
    (d / "tasks.md").write_text(tasks)


def _codes(root: Path) -> list[str]:
    _, errors, _ = module.check(root)
    return [e.split(": ", 1)[1].split()[0] for e in errors]


def test_repo_specs_are_a_valid_dag():
    _, errors, warnings = module.check(REPO / "specs")
    assert errors == []
    assert warnings == []


def test_done_task_with_open_dependency_is_an_error(tmp_path):
    _feature(tmp_path, "001-a", "- [ ] T050 Bind\n- [x] T060 Wire\n  - depends_on: [T050]\n")
    assert _codes(tmp_path) == ["DONE-BEFORE-DEP"]


def test_undefined_dependency_and_cycle_are_errors(tmp_path):
    _feature(
        tmp_path,
        "001-a",
        "- [ ] T010 A\n  - depends_on: [T020]\n- [ ] T020 B\n  - depends_on: [T010, T099]\n",
    )
    assert sorted(_codes(tmp_path)) == ["TASK-CYCLE", "UNDEFINED"]


def test_done_parent_with_open_subtask_is_an_error(tmp_path):
    _feature(tmp_path, "001-a", "- [x] T010 Parent\n  - [x] T010a Code\n  - [ ] T010b Operator\n")
    assert _codes(tmp_path) == ["DONE-BEFORE-CHILD"]


def test_cross_spec_dependency_resolves_and_spec_cycle_is_detected(tmp_path):
    _feature(tmp_path, "001-a", "- [x] T010 A\n", spec="**Depends on:** Spec 002\n")
    _feature(tmp_path, "002-b", "## Upstream\n- Depends on Spec 001.\n- [x] T010 B\n  - depends_on: [001:T010]\n")
    assert _codes(tmp_path) == ["SPEC-CYCLE"]


def test_literal_newline_in_task_line_is_an_error(tmp_path):
    _feature(tmp_path, "001-a", "- [x] T010 One.\\n- [x] T011 Two.\n")
    assert _codes(tmp_path) == ["LITERAL-NEWLINE"]
