"""Operator entry point for evidence-image retention expiry.

Usage (from ``backend/``)::

    python -m evidence.expire            # dry run: report what would expire, change nothing
    python -m evidence.expire --apply    # soft-delete expired assets and purge their bytes

Nothing schedules this. It runs only when an operator invokes it. See docs/OPERATIONS.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.orm import Session

# Importing the app module registers every model with SQLAlchemy exactly as the API does, so
# foreign keys (image_assets -> racks, users) resolve when this runs standalone.
import main  # noqa: F401
from evidence.retention import expire_image_assets


def run(db: Session, *, apply: bool, now: datetime | None = None) -> dict[str, object]:
    """Run expiry against ``db``; commit only when ``apply`` is true."""
    instant = now or datetime.now(timezone.utc)
    counts = expire_image_assets(db, now=instant, dry_run=not apply)
    if apply:
        db.commit()
    else:
        db.rollback()
    return {"mode": "apply" if apply else "dry-run", "as_of": instant.isoformat(), **counts}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m evidence.expire",
        description="Expire evidence images past retention. Dry run unless --apply is given.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually soft-delete expired image assets and purge their stored bytes",
    )
    args = parser.parse_args(argv)

    from core.database import SessionLocal

    db = SessionLocal()
    try:
        report = run(db, apply=args.apply)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(json.dumps(report, sort_keys=True))
    return 1 if report["purge_deferred"] else 0


if __name__ == "__main__":
    sys.exit(main())
