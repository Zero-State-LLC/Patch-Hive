"""Spec 001 (rig intelligence) T010: the generation run lifecycle as a transitions table.

Source of truth: specs/001-rig-intelligence/spec.md, "## Stateful behavior",
"### Generation run lifecycle", read through the mapping in plan.md and the T001 record.
The run lifecycle has no state-machine function: it is enforced inline in
``patches.routes.run_generation``, so the tests drive that path against the SQLite fixtures
and observe the ``runs.status`` that each commit leaves behind.

Some spec rows have no code to test, and the table says why: no request selects a revision
(D1), no worker exists (D4), and a retry is another generate call. The illegal moves hold by
construction, because nothing attempts them, so there is no rejection to assert. The tests pin
that instead: ``run_generation`` is the only writer of a run's status, and it writes only the
moves below. The evidence lifecycle is in ``test_spec_001_evidence_rules.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from canon.models import StageReceiptRecord
import export.patchbook.design.dual_write as dual_write
import patches.routes as routes
import patches.validation as validation
from patches.models import Patch
from patches.schemas import GeneratePatchesRequest
from racks.models import Rack
from runs.models import Run

# Spec "Generation run lifecycle" / Transitions: (from, event, to). The run row only exists from
# QUEUED on, so the status sequence a run commits is the path QUEUED -> RUNNING -> terminal.
SPEC_TRANSITIONS = [
    ("RIG_LOADED", "generate_requested", "QUEUED"),
    ("RIG_LOADED", "generate_requested", "NOT_COMPUTABLE"),
    ("QUEUED", "worker_started", "RUNNING"),
    ("RUNNING", "run_succeeded", "SUCCEEDED"),
    ("RUNNING", "validation_failed", "FAILED"),
    ("RUNNING", "run_failed", "FAILED"),
]
# Spec rows no code handles, with the T001 record's reason. The status moves they lead to are
# still covered: QUEUED -> RUNNING below, and a retry by test_retry_creates_a_new_run_...
DE_SCOPED = {
    ("IDLE", "rig_selected", "RIG_LOADED"): "D1: the request has no revision field",
    ("FAILED", "retry", "QUEUED"): "D1: a retry is another generate call, with no event of its own",
}
# worker_started moves the status, and that's encoded. Its worker and start receipt don't exist (D4).
WITHOUT_ITS_EFFECT = {"worker_started": "D4: the request handler runs generation inline"}
# Spec "Illegal transitions" of the run lifecycle, and what holds each one.
ILLEGAL_HELD_BY = {
    "QUEUED -> SUCCEEDED": "test_a_run_status_has_one_writer_and_only_these_moves",
    "FAILED -> SUCCEEDED": "test_retry_creates_a_new_run_and_leaves_the_failed_run_unchanged",
    "FAILED -> RUNNING": "test_retry_creates_a_new_run_and_leaves_the_failed_run_unchanged",
    "SUCCEEDED -> any state": "test_succeeded_run_is_never_changed_by_regeneration",
    "NOT_COMPUTABLE -> any state": "test_generate_requested_not_ready_is_not_computable_and_creates_no_run",
    "RUNNING -> QUEUED": "test_a_run_status_has_one_writer_and_only_these_moves",
    "edits patches of a finished run": "test_patches_of_a_succeeded_run_are_append_only",
}
# Spec state -> runs.status (QUEUED is "queued" per the state table; FAILED has two
# stored spellings because the code distinguishes validation_failed from failed).
# NOT_COMPUTABLE has no status: it's an answer with no run row.
STATUS_OF = {
    "QUEUED": {"queued"},
    "RUNNING": {"running"},
    "SUCCEEDED": {"succeeded"},
    "FAILED": {"failed", "validation_failed"},
}
SPEC = Path(__file__).resolve().parents[3] / "specs" / "001-rig-intelligence" / "spec.md"
BACKEND = Path(__file__).resolve().parents[2]


def _spec_rows(heading: str) -> list[tuple[str, str, str]]:
    """(from, event, to) for each row of a lifecycle's "#### Transitions" table in the spec."""
    text = SPEC.read_text(encoding="utf-8").split(heading, 1)[1].split("#### Illegal transitions", 1)[0]
    rows = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 5 and cells[0] not in {"from", "---"}:
            rows.append((cells[0], cells[1], cells[3]))
    return rows


class _CommitSpy:
    """Record the status of the newest run after every commit."""

    def __init__(self, db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        self.db = db
        self.seen: list[str] = []
        real_commit = db.commit

        def commit() -> None:
            real_commit()
            run = db.query(Run).order_by(Run.id.desc()).first()
            if run is not None and (not self.seen or self.seen[-1] != run.status):
                self.seen.append(run.status)

        monkeypatch.setattr(db, "commit", commit)


def _generate(db: Session, rack: Rack):
    return routes.run_generation(db, rack, GeneratePatchesRequest())


def _block_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    def blocked(patch_graphs, modules_by_id, allowed_module_ids=None):
        report = validation.ValidationReport()
        report.add(validation.Finding("block", "PORT_DIRECTION_MISMATCH", "test", 0))
        return list(patch_graphs), report

    monkeypatch.setattr(validation, "resolve_and_validate", blocked)


def _fail_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("engine exploded")

    monkeypatch.setattr(routes, "generate_patches_with_ir", boom)


def test_table_covers_every_spec_transition_state() -> None:
    assert {to for _, _, to in SPEC_TRANSITIONS} == set(STATUS_OF) | {"NOT_COMPUTABLE"}


def test_every_spec_row_is_encoded_or_says_why_it_is_not() -> None:
    assert sorted([*SPEC_TRANSITIONS, *DE_SCOPED]) == sorted(_spec_rows("### Generation run lifecycle"))
    assert set(WITHOUT_ITS_EFFECT) <= {event for _, event, _ in SPEC_TRANSITIONS}


def test_every_illegal_move_names_what_holds_it() -> None:
    text = SPEC.read_text(encoding="utf-8").split("### Generation run lifecycle", 1)[1]
    illegal = text.split("#### Illegal transitions", 1)[1].split("```mermaid", 1)[0]
    assert len([line for line in illegal.splitlines() if line.startswith("- ")]) == len(ILLEGAL_HELD_BY)
    for test_name in ILLEGAL_HELD_BY.values():
        assert test_name in globals(), test_name


def test_a_run_status_has_one_writer_and_only_these_moves() -> None:
    """Illegal moves hold by construction: nothing but ``run_generation`` writes a run's status."""
    written = re.compile(r"""^\s*(?:run|failed)\.status\s*=\s*["'](\w+)["']""", re.MULTILINE)
    writers = {}
    for path in BACKEND.rglob("*.py"):
        relative = path.relative_to(BACKEND).as_posix()
        if relative.startswith(("tests/", "alembic/", ".venv/")):
            continue
        found = written.findall(path.read_text(encoding="utf-8"))
        if found:
            writers[relative] = found
    assert writers == {"patches/routes.py": ["running", "validation_failed", "succeeded", "failed"]}
    source = (BACKEND / "patches" / "routes.py").read_text(encoding="utf-8")
    # A failure can only come from a run that hasn't finished.
    assert 'failed.status in {"queued", "running"}' in source
    assert 'Run(rack_id=rack_id, status="queued")' in source


def test_a_succeeded_run_keeps_its_stage_receipts(db_session: Session, sample_rack_basic: Rack) -> None:
    """Three receipts per patch on the success path. A run that seals no patch keeps one outcome
    receipt instead: see ``tests/api/test_spec_001_run_records.py``."""
    result = _generate(db_session, sample_rack_basic)
    assert result.generated_count >= 1
    receipts = db_session.query(StageReceiptRecord).filter(StageReceiptRecord.run_id == result.source_run_id)
    assert receipts.count() == 3 * result.generated_count


def test_generate_requested_ready_goes_queued_running_succeeded(
    db_session: Session, sample_rack_basic: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    spy = _CommitSpy(db_session, monkeypatch)
    result = _generate(db_session, sample_rack_basic)
    assert spy.seen[:2] == ["queued", "running"]
    assert spy.seen[-1] == "succeeded"
    assert spy.seen[-1] in STATUS_OF["SUCCEEDED"]
    run = db_session.get(Run, result.run_id)
    assert run.status == "succeeded"
    assert db_session.query(Patch).filter(Patch.run_id == run.id).count() >= 1


def test_generate_requested_not_ready_is_not_computable_and_creates_no_run(
    db_session: Session, sample_rack_empty: Rack
) -> None:
    before = db_session.query(Run).count()
    result = _generate(db_session, sample_rack_empty)
    assert result.generation_status == "NOT_COMPUTABLE"
    assert result.run_id is None
    assert result.patches == []
    assert db_session.query(Run).count() == before


@pytest.mark.parametrize(
    ("event", "arrange", "final_status"),
    [
        ("validation_failed", _block_validation, "validation_failed"),
        ("run_failed", _fail_engine, "failed"),
    ],
)
def test_running_failure_events_end_failed_and_keep_no_patches(
    event: str,
    arrange,
    final_status: str,
    db_session: Session,
    sample_rack_basic: Rack,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arrange(monkeypatch)
    spy = _CommitSpy(db_session, monkeypatch)
    try:
        _generate(db_session, sample_rack_basic)
    except RuntimeError:
        assert event == "run_failed"
    assert spy.seen == ["queued", "running", final_status]
    assert final_status in STATUS_OF["FAILED"]
    run = db_session.query(Run).order_by(Run.id.desc()).one()
    assert run.status == final_status
    assert db_session.query(Patch).filter(Patch.run_id == run.id).count() == 0
    if event == "validation_failed":
        assert run.validation_report["blocking"] is True


def test_retry_creates_a_new_run_and_leaves_the_failed_run_unchanged(
    db_session: Session, sample_rack_basic: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as m:
        _block_validation(m)
        failed = _generate(db_session, sample_rack_basic)
    failed_run = db_session.get(Run, failed.run_id)
    assert failed_run.status == "validation_failed"
    report_before = failed_run.validation_report

    retry = _generate(db_session, sample_rack_basic)

    assert retry.run_id != failed.run_id
    assert db_session.get(Run, retry.run_id).status == "succeeded"
    db_session.refresh(failed_run)
    assert failed_run.status == "validation_failed"
    assert failed_run.validation_report == report_before
    assert db_session.query(Patch).filter(Patch.run_id == failed.run_id).count() == 0


def test_a_failure_after_generation_never_leaves_the_run_running(
    db_session: Session, sample_rack_basic: Rack, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("dual-write down")

    monkeypatch.setattr(dual_write, "dual_write_generated_patches", boom)
    with pytest.raises(RuntimeError):
        _generate(db_session, sample_rack_basic)
    statuses = [r.status for r in db_session.query(Run).all()]
    assert statuses == ["failed"]


def test_succeeded_run_is_never_changed_by_regeneration(
    db_session: Session, sample_rack_basic: Rack
) -> None:
    """Illegal: SUCCEEDED -> any state. Regeneration creates a new run."""
    first = _generate(db_session, sample_rack_basic)
    patch_ids = sorted(p.id for p in db_session.query(Patch).filter(Patch.run_id == first.run_id))
    second = _generate(db_session, sample_rack_basic)
    assert second.run_id != first.run_id
    assert db_session.get(Run, first.run_id).status == "succeeded"
    assert sorted(p.id for p in db_session.query(Patch).filter(Patch.run_id == first.run_id)) == patch_ids


def test_patches_of_a_succeeded_run_are_append_only(
    db_session: Session, sample_rack_basic: Rack, owner_headers: dict
) -> None:
    """Illegal: any transition that adds, removes, or edits patches of a SUCCEEDED run."""
    from fastapi.testclient import TestClient

    from core import get_db
    from main import app

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app, headers=owner_headers)
        result = _generate(db_session, sample_rack_basic)
        patch = db_session.query(Patch).filter(Patch.run_id == result.run_id).first()
        before = (patch.name, patch.description)

        edited = client.patch(f"/api/patches/{patch.id}", json={"name": "renamed"})
        deleted = client.delete(f"/api/patches/{patch.id}")

        assert edited.status_code == 409
        assert deleted.status_code == 409
        db_session.refresh(patch)
        assert (patch.name, patch.description) == before
    finally:
        app.dependency_overrides.clear()
