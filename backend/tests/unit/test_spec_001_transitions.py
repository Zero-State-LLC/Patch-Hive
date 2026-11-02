"""Spec 001 (rig intelligence) T010: the generation run lifecycle as a transitions table.

Source of truth: specs/001-rig-intelligence/spec.md, "## Stateful behavior",
"### Generation run lifecycle". The table below is copied from that spec's
"#### Transitions" and "#### Illegal transitions". The run lifecycle has no
state-machine function: it is enforced inline in ``patches.routes.run_generation``,
so the tests drive that path against the SQLite fixtures and observe the ``runs.status``
that each commit leaves behind.

Not encoded (see the T010 report): the "Module evidence disposition lifecycle" has no
implementation with those states, and the IDLE/RIG_LOADED states and the QUEUED->SUCCEEDED
style illegal pairs have no event handler to reject them.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

import export.patchbook.design.dual_write as dual_write
import patches.routes as routes
import patches.validation as validation
from patches.models import Patch
from patches.schemas import GeneratePatchesRequest
from racks.models import Rack
from runs.models import Run

# Spec "Generation run lifecycle" / Transitions: rows reachable through run_generation.
# (from, event, guard, to). The run row only exists from QUEUED on, so the status
# sequence a run commits is the path QUEUED -> RUNNING -> terminal.
SPEC_TRANSITIONS = [
    ("RIG_LOADED", "generate_requested", "readiness passes", "QUEUED"),
    ("QUEUED", "worker_started", None, "RUNNING"),
    ("RUNNING", "run_succeeded", "patches validated", "SUCCEEDED"),
    ("RUNNING", "validation_failed", "blocking errors", "FAILED"),
    ("RUNNING", "run_failed", None, "FAILED"),
]
# Spec state -> runs.status (QUEUED is "queued" per the state table; FAILED has two
# stored spellings because the code distinguishes validation_failed from failed).
STATUS_OF = {
    "QUEUED": {"queued"},
    "RUNNING": {"running"},
    "SUCCEEDED": {"succeeded"},
    "FAILED": {"failed", "validation_failed"},
}


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
    assert {to for _, _, _, to in SPEC_TRANSITIONS} == set(STATUS_OF)


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
