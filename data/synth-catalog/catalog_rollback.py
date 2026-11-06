"""Roll back one applied catalog load by its run ID (spec 003 FR-031, decision 40).

A rollback retires the rows that run inserted and restores the fields it changed. It deletes
nothing (D3). A field that changed again since is left alone and reported. Like a load, it is a dry
run until an operator applies it with the plan_hash that dry run printed (FR-020).

A rollback does not touch committed files. A fill-null overlay that is still committed fills a restored
null again on the next load, so revert or replace it first. A retired row stays retired, because
insert-if-absent sees its slug. A provenance batch stays processed, so its fix needs a new batch version.
Case rows have no retired state, so a run's case writes are reported, not undone.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from load_runs import record_run
from population import (
    Op,
    Plan,
    _rigs_holding,
    _stamp,
    apply_plan,
    assert_local_database,
    plan_hash,
    render_plan,
    safe_target,
)

RETIRE = {
    "module_catalog": (
        "UPDATE module_catalog SET tombstoned_at = CURRENT_TIMESTAMP, tombstone_reason = :reason "
        "WHERE id = :row_id AND tombstoned_at IS NULL"
    ),
    "modules": "UPDATE modules SET status = 'tombstoned' WHERE id = :row_id AND status <> 'tombstoned'",
}
# Nothing reads these as live on their own: a power setting belongs to a module, and a maker row
# only lists a name. Neither table has a retired state.
LEFT_IN_PLACE = frozenset({"power_configs", "manufacturers"})


def _column_types(conn: Connection, table: str) -> dict[str, str]:
    rows = conn.execute(
        text("SELECT column_name, udt_name FROM information_schema.columns WHERE table_name = :table"),
        {"table": table},
    ).mappings()
    return {row["column_name"]: row["udt_name"] for row in rows}


def _restore_op(table: str, change: dict[str, Any], kind: str) -> Op:
    """Write the old value back, only while the field still holds what this run wrote."""
    field = change["field"]
    is_json = kind in {"json", "jsonb"}
    stored = f"CAST({field} AS jsonb)" if is_json else field
    cast = "jsonb" if is_json else kind
    dumped = (lambda value: None if value is None else json.dumps(value)) if is_json else (
        lambda value: None if value is None else str(value)
    )
    return Op(
        "rollback_restore",
        f"UPDATE {table} SET {field} = CAST(:old AS {kind}) "
        f"WHERE id = :row_id AND {stored} IS NOT DISTINCT FROM CAST(:new AS {cast})",
        {"row_id": change["row_id"], "old": dumped(change["old_value"]), "new": dumped(change["new_value"])},
    )


def plan_rollback(conn: Connection, run_id: str) -> tuple[Plan, dict[str, Any]]:
    run = conn.execute(
        text("SELECT kind, rolled_back_by, receipt FROM catalog_load_runs WHERE run_id = :run_id"),
        {"run_id": run_id},
    ).mappings().first()
    if run is None:
        raise SystemExit(
            f"refusing to roll back {run_id}: there is no record of it. Loads before migration "
            "20261106_catalog_load_runs recorded no changes, so they can't be rolled back."
        )
    if run["kind"] != "apply":
        raise SystemExit(f"refusing to roll back {run_id}: it is a rollback, not a load")
    if run["rolled_back_by"]:
        raise SystemExit(f"refusing to roll back {run_id}: {run['rolled_back_by']} already did")

    changes = [
        dict(row)
        for row in conn.execute(
            text(
                "SELECT table_name, row_id, row_key, change, field, old_value, new_value "
                "FROM catalog_load_changes WHERE run_id = :run_id ORDER BY id"
            ),
            {"run_id": run_id},
        ).mappings()
    ]
    plan = Plan()
    stats: dict[str, Any] = {"retired": {}, "restored": {}, "left_in_place": {}, "archive_rows_marked": 0}
    reason = f"rollback of catalog load {run_id}"
    retiring: list[tuple[str, str]] = []
    types = {table: _column_types(conn, table) for table in {c["table_name"] for c in changes}}
    for change in changes:
        table = change["table_name"]
        if table == "catalog_value_archive":
            if change["change"] == "insert":
                plan.add_update(
                    "catalog_value_archive_rolled_back",
                    Op(
                        "rollback_mark_archive",
                        "UPDATE catalog_value_archive SET rolled_back_run_id = :run_id "
                        "WHERE id = :row_id AND rolled_back_run_id IS NULL",
                        {"run_id": run_id, "row_id": change["row_id"]},
                    ),
                )
                stats["archive_rows_marked"] += 1
            continue
        if change["change"] == "insert":
            if table in LEFT_IN_PLACE:
                stats["left_in_place"][table] = stats["left_in_place"].get(table, 0) + 1
                continue
            params = {"row_id": change["row_id"]}
            if table == "module_catalog":
                params["reason"] = reason
            elif change["row_key"] and "::" in change["row_key"]:
                brand, name = change["row_key"].split("::", 1)
                retiring.append((brand, name))
            plan.add_update(f"{table}_retired", Op("rollback_retire", RETIRE[table], params))
            stats["retired"][table] = stats["retired"].get(table, 0) + 1
            continue
        current = conn.execute(
            text(f"SELECT {change['field']} FROM {table} WHERE id = :row_id"),
            {"row_id": change["row_id"]},
        ).scalar()
        current = current.isoformat() if hasattr(current, "isoformat") else current
        if current != change["new_value"]:
            plan.conflict(
                table=table, row_key=change["row_key"], field=change["field"], reason="changed_since_run"
            )
            continue
        plan.add_update(f"{table}_restored", _restore_op(table, change, types[table][change["field"]]))
        stats["restored"][table] = stats["restored"].get(table, 0) + 1
    stats["retired_on_racks"] = _rigs_holding(conn, retiring)
    prior = run["receipt"] if isinstance(run["receipt"], dict) else json.loads(run["receipt"])
    stats["cases_not_rolled_back"] = (prior.get("cases") or {}).get("applied")
    return plan, stats


def rollback(
    database_url: str,
    run_id: str,
    *,
    apply: bool = False,
    allow_nonlocal: bool = False,
    receipt_path: Path | None = None,
    sql_path: Path | None = None,
    expected_plan_hash: str | None = None,
    require_plan_hash: bool = False,
) -> dict[str, Any]:
    assert_local_database(database_url, allow_nonlocal)
    this_run = os.environ.get("GITHUB_RUN_ID") or uuid.uuid4().hex
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    if attempt and attempt != "1":
        this_run = f"{this_run}-{attempt}"
    started_at = _stamp()
    engine = create_engine(database_url)
    try:
        with engine.begin() as conn:
            # Planned and applied in one transaction, so what was reviewed is what gets written.
            plan, stats = plan_rollback(conn, run_id)
            sql = render_plan(plan)
            current_hash = plan_hash(plan)
            if apply and require_plan_hash and expected_plan_hash != current_hash:
                raise SystemExit(
                    "refusing to apply: the rollback differs from the reviewed dry run "
                    f"(expected {expected_plan_hash or 'none'}, planned {current_hash})."
                )
            receipt: dict[str, Any] = {
                "mode": "rollback" if apply else "rollback-dry-run",
                "database": safe_target(database_url),
                "run_id": this_run,
                "rollback_of": run_id,
                "started_at": started_at,
                "plan_hash": current_hash,
                "inserts": plan.inserts,
                "updates": plan.updates,
                "conflicts_total": plan.conflicts_total,
                "conflicts": plan.conflicts,
                "destructive_sql": False,
                **stats,
            }
            if apply:
                apply_plan(conn, plan)
                record_run(
                    conn, run_id=this_run, kind="rollback", plan_hash=current_hash, inputs_hash=None,
                    receipt=receipt, rollback_of=run_id,
                )
                marked = conn.execute(
                    text(
                        "UPDATE catalog_load_runs SET rolled_back_by = :by "
                        "WHERE run_id = :run_id AND rolled_back_by IS NULL"
                    ),
                    {"by": this_run, "run_id": run_id},
                )
                if marked.rowcount != 1:
                    raise SystemExit(f"refusing to roll back {run_id}: another rollback got there first")
    except SQLAlchemyError as exc:
        raise SystemExit(f"database operation failed ({exc.__class__.__name__})") from None
    finally:
        engine.dispose()
    receipt["finished_at"] = _stamp()
    if receipt_path:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2, default=str) + "\n", encoding="utf-8")
    if sql_path:
        sql_path.parent.mkdir(parents=True, exist_ok=True)
        sql_path.write_text(sql, encoding="utf-8")
    return receipt
