#!/usr/bin/env python3
"""GitHub Actions catalog load. Never prints the database URL.

Environment:
  DATABASE_URL          connection string (required, not logged)
  PATCHHIVE_DB_ENV      staging or prod, stored in the receipt instead of the URL
  PATCHHIVE_LOAD_MODE   dry-run (default) or apply
  PATCHHIVE_PLAN_HASH   apply only: the plan_hash of the reviewed dry run (required)
  PATCHHIVE_INPUTS_HASH apply only: the inputs_hash of the reviewed dry run (required)
  PATCHHIVE_ROLLBACK_RUN_ID  roll this load back instead of loading (spec 003 FR-031)
  GITHUB_STEP_SUMMARY   optional path for the job summary
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

from catalog_rollback import rollback  # noqa: E402
from load_runs import actions_run_id  # noqa: E402
from population import (  # noqa: E402
    assert_at_head,
    dump_affected_tables,
    populate,
    table_counts,
)

ARTIFACTS = ROOT / "load-artifacts"


def _summary(
    before: dict[str, int],
    after: dict[str, int] | None,
    mode: str,
    env_name: str,
    receipt: dict | None = None,
) -> str:
    lines = [f"## Catalog load ({env_name}, {mode})", ""]
    if receipt and receipt.get("rollback_of"):
        lines = [f"## Catalog rollback of {receipt['rollback_of']} ({env_name}, {mode})", ""]
        lines += [
            f"- plan_hash: `{receipt['plan_hash']}`"
            + (" (apply with this to write exactly this rollback)" if mode == "dry-run" else ""),
            f"- run_id: {receipt['run_id']}",
            f"- rows retired: {receipt['retired']}",
            f"- fields restored: {receipt['restored']}",
            f"- inserted rows left in place: {receipt['left_in_place']}",
            f"- changed since the load, left alone: {receipt['conflicts_total']}",
            f"- retired modules on Rigs: {receipt['retired_on_racks']}",
            f"- case writes not rolled back: {receipt['cases_not_rolled_back']}",
            "- Committed files are unchanged: revert or replace the overlay before the next load.",
            "",
        ]
    elif receipt:
        lines += [
            f"- plan_hash: `{receipt['plan_hash']}`"
            + (" (apply with this to write exactly this plan)" if mode == "dry-run" else ""),
            f"- inputs_hash: `{receipt['inputs_hash']}`"
            + (" (apply with this too: the catalog inputs this plan was built from)" if mode == "dry-run" else ""),
            f"- conflicts: {receipt['conflicts_total']}",
            f"- run_id: {receipt['run_id']}",
        ]
        if sync := receipt.get("module_type_sync"):
            # Decision 51: the exact count, for the owner's go-ahead on a production load.
            lines.append(
                f"- modules.module_type set from the catalog category: {sync['synced']} {sync['by_category']}; "
                f"left alone: {sync['left_alone_other_value']} with another value, "
                f"{sync['left_alone_not_loader_row']} not loader rows"
            )
        if basis := receipt.get("access_basis"):
            # Decisions 52 and 53: the exact counts, for the owner's go-ahead on a production load.
            lines.append(
                f"- access_basis set: {basis['official_publication']} official_publication, "
                f"{basis['leads_tagged_unknown']} unknown; "
                f"{basis['left_out_by_overlay']} maker rows failed the check and stay as they are"
            )
            lines.append(
                f"- ModularGrid URLs cleared: {basis['urls_cleared']}; "
                f"on retired rows, left alone: {basis['left_alone_retired_with_url']}"
            )
        if promoted := receipt.get("lead_promotions"):
            # FR-034: what a production go-ahead would bring back into anonymous reads.
            lines.append(
                f"- leads confirmed by a maker page: {promoted['promoted']}; "
                f"already confirmed: {promoted['already_confirmed']}; not in this database: {promoted['rows_missing']}"
            )
        lines.append("")
    lines += [
        "| table | before | after | delta |",
        "|---|---:|---:|---:|",
    ]
    for table, prior in before.items():
        later = prior if after is None else after.get(table, prior)
        lines.append(f"| {table} | {prior} | {later} | {later - prior} |")
    if after is None:
        lines.append("")
        lines.append("After counts were not recorded because the load stopped early.")
    return "\n".join(lines) + "\n"


def _write_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY", "").strip()
    if not path:
        print(text)
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    env_name = os.environ.get("PATCHHIVE_DB_ENV", "").strip()
    mode = os.environ.get("PATCHHIVE_LOAD_MODE", "dry-run").strip() or "dry-run"
    if env_name not in {"staging", "prod"}:
        raise SystemExit("PATCHHIVE_DB_ENV must be staging or prod")
    if mode not in {"dry-run", "apply"}:
        raise SystemExit("PATCHHIVE_LOAD_MODE must be dry-run or apply")
    allow = "--allow-nonlocal" in sys.argv
    if not allow:
        raise SystemExit("refusing a remote load without --allow-nonlocal")

    head = assert_at_head(database_url)
    before = table_counts(database_url)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "counts-before.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    after: dict[str, int] | None = None
    receipt: dict | None = None
    try:
        if mode == "apply":
            dump_affected_tables(database_url, ARTIFACTS / "pre-apply.dump")
        rollback_of = os.environ.get("PATCHHIVE_ROLLBACK_RUN_ID", "").strip()
        if rollback_of:
            receipt = rollback(
                database_url,
                rollback_of,
                apply=mode == "apply",
                allow_nonlocal=True,
                receipt_path=ARTIFACTS / "receipt.json",
                sql_path=ARTIFACTS / "population-upsert.sql",
                expected_plan_hash=os.environ.get("PATCHHIVE_PLAN_HASH", "").strip() or None,
                require_plan_hash=mode == "apply",
                this_run=actions_run_id(),
            )
        else:
            receipt = populate(
                database_url,
                apply=mode == "apply",
                allow_nonlocal=True,
                receipt_path=ARTIFACTS / "receipt.json",
                sql_path=ARTIFACTS / "population-upsert.sql",
                expected_plan_hash=os.environ.get("PATCHHIVE_PLAN_HASH", "").strip() or None,
                require_plan_hash=mode == "apply",
                expected_inputs_hash=os.environ.get("PATCHHIVE_INPUTS_HASH", "").strip() or None,
                require_inputs_hash=mode == "apply",
                run_id=actions_run_id(),
            )
        receipt["alembic_head"] = head
        (ARTIFACTS / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        after = table_counts(database_url)
        (ARTIFACTS / "counts-after.json").write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"mode": receipt["mode"], "database": receipt["database"], "inserts": receipt["inserts"]}, indent=2))
        return 0
    finally:
        _write_summary(_summary(before, after, mode, env_name, receipt))


if __name__ == "__main__":
    raise SystemExit(main())
