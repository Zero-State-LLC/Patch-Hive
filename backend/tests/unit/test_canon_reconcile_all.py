"""Operator CLI for ledger reconciliation across every user (release gate 6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import canon.reconcile_all as reconcile_cli
import core.database
from canon.contracts import ExportRequest
from canon.exports import compensate_failed_export, request_export
from canon.models import CanonicalCreditLedgerEntryRecord, CanonicalExportRecord
from tests.unit.test_canon_contracts import _persist_hierarchy

NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)


def _grant(db: Session, user_id: int, delta: int = 10) -> None:
    db.add(
        CanonicalCreditLedgerEntryRecord(
            id=f"grant-{user_id}",
            user_id=user_id,
            delta=delta,
            entry_type="grant",
            idempotency_key=f"grant-{user_id}",
            created_at=NOW,
        )
    )
    db.commit()


def _export(db: Session, user_id: int) -> CanonicalExportRecord:
    return request_export(
        db,
        ExportRequest(
            request_id="request-1",
            user_id=user_id,
            source_run_id="run-1",
            source_rig_revision_id="rig-rev-1",
            formats=("pdf", "json"),
            license="personal",
            credit_cost=3,
            idempotency_key="idem-1",
            requested_at=NOW,
        ),
        artifact_manifest_hash="a" * 64,
        export_version="1.0.0",
    )


def _unbacked_export(db: Session, user_id: int, export_id: str, status: str) -> None:
    """An export that costs credits but has no ledger rows: the shape reconcile flags."""
    db.add(
        CanonicalExportRecord(
            id=export_id,
            user_id=user_id,
            source_run_id="run-1",
            source_rig_revision_id="rig-rev-1",
            artifact_manifest_hash="a" * 64,
            export_version="1.0.0",
            license="personal",
            credit_cost=3,
            idempotency_key=f"idem-{export_id}",
            status=status,
            created_at=NOW,
        )
    )
    db.commit()


def _sessions(monkeypatch, db: Session) -> None:
    monkeypatch.setattr(core.database, "SessionLocal", lambda: db)


def test_a_balanced_ledger_reports_ok(db_session: Session) -> None:
    user, _patch = _persist_hierarchy(db_session)
    _grant(db_session, user.id)
    export = _export(db_session, user.id)
    compensate_failed_export(db_session, export, occurred_at=NOW)
    db_session.commit()

    report = reconcile_cli.run(db_session)

    assert report["status"] == "ok"
    assert report["mismatch_count"] == 0 and report["mismatches"] == []
    assert report["users_checked"] == 1
    assert report["users_with_ledger_entries"] == 1
    assert report["ledger_entries"] == 3  # grant, debit, reversal
    assert report["exports"] == 1
    assert report["balance_total"] == 10
    assert report["export_debits_total"] == report["reversals_total"] == 3


def test_every_user_is_checked_including_ones_without_ledger_rows(db_session: Session) -> None:
    user, _patch = _persist_hierarchy(db_session)
    _grant(db_session, user.id)
    from community.models import User

    db_session.add(User(username="quiet", email="quiet@example.com", password_hash="x"))
    db_session.commit()

    report = reconcile_cli.run(db_session)

    assert report["users_checked"] == 2
    assert report["users_with_ledger_entries"] == 1


def test_mismatches_name_the_export_and_never_the_user(db_session: Session) -> None:
    user, _patch = _persist_hierarchy(db_session)
    _unbacked_export(db_session, user.id, "export-missing-debit", "queued")
    _unbacked_export(db_session, user.id, "export-missing-reversal", "refunded")

    report = reconcile_cli.run(db_session)

    assert report["status"] == "mismatch"
    assert report["mismatch_count"] == 3
    assert report["mismatches"] == [
        {"export_id": "export-missing-debit", "anomaly": "expected one debit, found 0"},
        {"export_id": "export-missing-reversal", "anomaly": "expected one debit, found 0"},
        {"export_id": "export-missing-reversal", "anomaly": "expected one reversal, found 0"},
    ]
    rendered = json.dumps(report)
    assert user.username not in rendered and user.email not in rendered
    assert "user_id" not in rendered


def test_long_mismatch_lists_are_capped(db_session: Session, monkeypatch) -> None:
    user, _patch = _persist_hierarchy(db_session)
    for index in range(3):
        _unbacked_export(db_session, user.id, f"export-{index}", "queued")
    monkeypatch.setattr(reconcile_cli, "MAX_LISTED_MISMATCHES", 2)

    report = reconcile_cli.run(db_session)

    assert report["mismatch_count"] == 3
    assert len(report["mismatches"]) == 2
    assert report["mismatches_truncated"] is True


def test_run_writes_nothing(db_session: Session) -> None:
    user, _patch = _persist_hierarchy(db_session)
    _grant(db_session, user.id)
    reconcile_cli.run(db_session)
    assert not db_session.new and not db_session.dirty and not db_session.deleted


def test_main_exits_0_when_clean_and_writes_the_report(db_session: Session, monkeypatch, tmp_path, capsys) -> None:
    user, _patch = _persist_hierarchy(db_session)
    _grant(db_session, user.id)
    _sessions(monkeypatch, db_session)
    out = tmp_path / "receipt" / "reconcile.json"

    assert reconcile_cli.main(["--json-out", str(out)]) == 0

    printed = json.loads(capsys.readouterr().out.strip())
    assert printed["status"] == "ok"
    assert json.loads(out.read_text(encoding="utf-8")) == printed


def test_main_exits_1_on_any_mismatch(db_session: Session, monkeypatch, capsys) -> None:
    user, _patch = _persist_hierarchy(db_session)
    _unbacked_export(db_session, user.id, "export-missing-debit", "queued")
    _sessions(monkeypatch, db_session)

    assert reconcile_cli.main([]) == 1
    assert json.loads(capsys.readouterr().out.strip())["mismatch_count"] == 1


def test_main_exits_2_without_leaking_connection_details(db_session: Session, monkeypatch, capsys) -> None:
    def unreachable(*_args, **_kwargs):
        raise OperationalError(
            "SELECT 1", {}, Exception('connection to "ep-secret-host.neon.tech" failed for user "owner"')
        )

    monkeypatch.setattr(reconcile_cli, "run", unreachable)
    _sessions(monkeypatch, db_session)

    assert reconcile_cli.main([]) == 2
    output = capsys.readouterr().out
    assert json.loads(output) == {"error": "OperationalError", "status": "error"}
    assert "ep-secret-host" not in output and "owner" not in output


def test_cli_in_fresh_process(tmp_path) -> None:
    """Run the documented command in a clean interpreter (no conftest model imports)."""
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[2]
    env = {
        "PATH": "/usr/bin:/bin",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'cli.db'}",
        "EXPORT_DIR": str(tmp_path / "exports"),
        "PYTHONPATH": str(backend),
    }
    seed = subprocess.run(
        [sys.executable, "-c", "import main\nfrom core.database import Base, engine\nBase.metadata.create_all(bind=engine)\n"],
        env=env,
        cwd=backend,
        capture_output=True,
        text=True,
    )
    assert seed.returncode == 0, seed.stderr[-2000:]

    cli = subprocess.run(
        [sys.executable, "-m", "canon.reconcile_all"], env=env, cwd=backend, capture_output=True, text=True
    )
    assert cli.returncode == 0, cli.stderr[-2000:]
    report = json.loads(cli.stdout.strip().splitlines()[-1])
    assert report["status"] == "ok" and report["users_checked"] == 0


def test_help_names_the_command(capsys) -> None:
    with pytest.raises(SystemExit) as exit_info:
        reconcile_cli.main(["--help"])
    assert exit_info.value.code == 0
    assert "python -m canon.reconcile_all" in capsys.readouterr().out
