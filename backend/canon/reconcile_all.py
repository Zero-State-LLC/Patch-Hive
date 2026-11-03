"""Operator entry point for ledger reconciliation across every user (release gate 6).

Usage (from ``backend/``)::

    python -m canon.reconcile_all                       # prints one JSON report
    python -m canon.reconcile_all --json-out out.json   # also writes it to a file

Read-only: on PostgreSQL the transaction is ``READ ONLY`` and is always rolled back.
The report holds counts and mismatches only. A mismatch names the export id and the
anomaly, never a user id, name or email, so the output can go into a public log or
receipt. Exit code 0 means no mismatch, 1 means at least one, 2 means the database
could not be read. See docs/OPERATIONS.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import func, select, text, union
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# Importing the app module registers every model with SQLAlchemy exactly as the API does, so
# foreign keys (canonical ledger -> users, exports) resolve when this runs standalone.
import main as _app_models  # noqa: F401
from canon.exports import reconcile_ledger
from canon.models import CanonicalCreditLedgerEntryRecord, CanonicalExportRecord
from community.models import User

# A report with thousands of mismatches is no more useful than one with the first hundred.
MAX_LISTED_MISMATCHES = 100


def _user_ids(db: Session) -> list[int]:
    """Every user with an account, a ledger entry or an export."""
    query = union(
        select(User.id),
        select(CanonicalCreditLedgerEntryRecord.user_id),
        select(CanonicalExportRecord.user_id),
    )
    return sorted(int(user_id) for user_id in db.scalars(query))


def _count(db: Session, model) -> int:
    return int(db.scalar(select(func.count()).select_from(model)) or 0)


def run(db: Session) -> dict[str, object]:
    """Reconcile every user's ledger in ``db`` and return the report. Writes nothing."""
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(text("SET TRANSACTION READ ONLY"))
    users_checked = 0
    balance_total = export_debits_total = reversals_total = 0
    mismatches: list[dict[str, str]] = []
    for user_id in _user_ids(db):
        report = reconcile_ledger(db, user_id)
        users_checked += 1
        balance_total += report.balance
        export_debits_total += report.export_debits
        reversals_total += report.reversals
        for anomaly in report.anomalies:
            export_id, _sep, detail = anomaly.partition(": ")
            mismatches.append({"export_id": export_id, "anomaly": detail})
    mismatches.sort(key=lambda item: (item["export_id"], item["anomaly"]))
    return {
        "status": "mismatch" if mismatches else "ok",
        "users_checked": users_checked,
        "users_with_ledger_entries": int(
            db.scalar(select(func.count(func.distinct(CanonicalCreditLedgerEntryRecord.user_id))))
            or 0
        ),
        "ledger_entries": _count(db, CanonicalCreditLedgerEntryRecord),
        "exports": _count(db, CanonicalExportRecord),
        "balance_total": balance_total,
        "export_debits_total": export_debits_total,
        "reversals_total": reversals_total,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:MAX_LISTED_MISMATCHES],
        "mismatches_truncated": len(mismatches) > MAX_LISTED_MISMATCHES,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m canon.reconcile_all",
        description="Reconcile the credit ledger for every user. Read-only; exit 1 on any mismatch.",
    )
    parser.add_argument("--json-out", type=Path, help="also write the JSON report to this file")
    args = parser.parse_args(argv)

    from core.database import SessionLocal

    db = SessionLocal()
    try:
        report = run(db)
    except SQLAlchemyError as exc:
        # The driver message can name the host and user; the class name is enough here.
        print(json.dumps({"status": "error", "error": exc.__class__.__name__}, sort_keys=True))
        return 2
    finally:
        db.rollback()
        db.close()
    rendered = json.dumps(report, sort_keys=True)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(rendered)
    return 1 if report["mismatch_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
