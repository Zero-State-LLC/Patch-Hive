"""What each applied catalog load changed, kept in the database (spec 003 FR-031, decision 40).

The loader's statements are insert-if-absent, fill-null and reviewed corrections, so what one run
really wrote depends on the database it met. Comparing the tracked tables before and after, inside
the apply transaction, records exactly that and works for any statement the plan holds.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Hiding or restoring is possible for these. A case row has no retired state (see catalog_rollback).
TRACKED_TABLES = ("module_catalog", "modules", "power_configs", "manufacturers", "catalog_value_archive")
# Bookkeeping that moves with every write, so a difference here isn't a change to restore.
UNTRACKED_FIELDS = frozenset({"updated_at", "created_at"})
INSERT_BATCH = 1000


def actions_run_id() -> str | None:
    """The ID a load takes from its GitHub Actions run, or None outside Actions.

    Only the db-load entry point asks for it. One CI run sets this variable for every process it
    starts, so a loader that read it unasked would give two applies in that run the same ID.
    """
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return None
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    return f"{run_id}-{attempt}" if attempt and attempt != "1" else run_id


def json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def row_key(table: str, row: dict[str, Any]) -> str | None:
    if table == "module_catalog":
        return row.get("slug")
    if table in {"modules", "power_configs"} and row.get("brand") is not None:
        return f"{row['brand']}::{row['name']}"
    if table == "manufacturers":
        return row.get("slug")
    return row.get("row_key")


def snapshot(conn: Connection) -> dict[str, dict[int, dict[str, Any]]]:
    tables: dict[str, dict[int, dict[str, Any]]] = {}
    for table in TRACKED_TABLES:
        rows = conn.execute(text(f"SELECT * FROM {table}")).mappings()
        tables[table] = {
            int(row["id"]): {key: json_safe(value) for key, value in row.items()} for row in rows
        }
    return tables


def diff(
    before: dict[str, dict[int, dict[str, Any]]], after: dict[str, dict[int, dict[str, Any]]]
) -> list[dict[str, Any]]:
    """One entry per inserted row and per changed field. A load never deletes a row (D3)."""
    changes: list[dict[str, Any]] = []
    for table in TRACKED_TABLES:
        gone = before[table].keys() - after[table].keys()
        if gone:
            raise RuntimeError(f"refusing a load that deleted {len(gone)} rows from {table}")
        for row_id, row in after[table].items():
            prior = before[table].get(row_id)
            if prior is None:
                changes.append(
                    {"table_name": table, "row_id": row_id, "row_key": row_key(table, row),
                     "change": "insert", "field": None, "old_value": None, "new_value": None}
                )
                continue
            for field, value in row.items():
                if field not in UNTRACKED_FIELDS and prior.get(field) != value:
                    changes.append(
                        {"table_name": table, "row_id": row_id, "row_key": row_key(table, row),
                         "change": "update", "field": field,
                         "old_value": prior.get(field), "new_value": value}
                    )
    return changes


def record_run(
    conn: Connection,
    *,
    run_id: str,
    kind: str,
    plan_hash: str,
    inputs_hash: str | None,
    receipt: dict[str, Any],
    changes: list[dict[str, Any]] | None = None,
    rollback_of: str | None = None,
) -> None:
    conn.execute(
        text(
            "INSERT INTO catalog_load_runs (run_id, kind, rollback_of, plan_hash, inputs_hash, receipt) "
            "VALUES (:run_id, :kind, :rollback_of, :plan_hash, :inputs_hash, CAST(:receipt AS JSON))"
        ),
        {"run_id": run_id, "kind": kind, "rollback_of": rollback_of, "plan_hash": plan_hash,
         "inputs_hash": inputs_hash, "receipt": json.dumps(receipt, default=str)},
    )
    rows = changes or []
    for start in range(0, len(rows), INSERT_BATCH):
        conn.execute(
            text(
                "INSERT INTO catalog_load_changes "
                "(run_id, table_name, row_id, row_key, change, field, old_value, new_value) VALUES "
                "(:run_id, :table_name, :row_id, :row_key, :change, :field, "
                "CAST(:old_value AS JSON), CAST(:new_value AS JSON))"
            ),
            [
                {**row, "run_id": run_id, "old_value": json.dumps(row["old_value"]),
                 "new_value": json.dumps(row["new_value"])}
                for row in rows[start : start + INSERT_BATCH]
            ],
        )
