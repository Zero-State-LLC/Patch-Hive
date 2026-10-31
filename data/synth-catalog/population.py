"""Idempotent catalog population for an empty or partial database.

Dry-run is the default. Statements insert missing rows and fill null specs.
They do not delete, drop, or overwrite a non-null spec or a settled verification.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError

CATALOG = Path(__file__).resolve().parent
ROOT = CATALOG.parents[1]
VERIFICATION_STATUSES = {"verified", "corrected", "flagged", "unverified"}
POWER_FIELDS = ("power_12v_ma", "power_neg12v_ma", "power_5v_ma", "depth_mm")
AFFECTED_TABLES = (
    "catalog_value_archive",
    "manufacturers",
    "module_catalog",
    "modules",
    "power_configs",
    "case_catalog",
    "case_revisions",
    "case_rows",
    "case_power_systems",
    "case_features",
    "case_prices",
    "case_sources",
    "case_source_policy_packets",
)


def create_slug(brand: str, name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", f"{brand}-{name}".lower()).strip("-")


def name_from_title(title: str, brand: str) -> str:
    text_value = re.sub(
        r"\s*[-|–—]\s*Eurorack Module on ModularGrid\s*$",
        "",
        title or "",
        flags=re.I,
    ).strip()
    if brand and text_value.lower().startswith(brand.lower()):
        text_value = text_value[len(brand) :].strip(" -–—")
    return text_value


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return repr(value)
    return "'" + str(value).replace("'", "''") + "'"


def render_sql(statement: str, params: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in params:
            return match.group(0)
        return sql_literal(params[name])

    return re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", replace, statement)


def assert_safe_sql(sql: str) -> None:
    forbidden = ("DELETE", "DROP", "TRUNCATE", "ALTER", "GRANT", "REVOKE")
    for chunk in sql.split(";"):
        lines = [line for line in chunk.splitlines() if not line.strip().startswith("--")]
        body = " ".join(lines).strip()
        if not body:
            continue
        head = body.split(None, 1)[0].upper()
        if head in forbidden:
            raise RuntimeError(f"refusing destructive SQL: {head}")
        if head == "UPDATE" and " WHERE " not in f" {body.upper()} ":
            raise RuntimeError("refusing UPDATE without WHERE")


def assert_local_database(url: str, allow_nonlocal: bool) -> None:
    if not url or not url.strip():
        raise SystemExit("DATABASE_URL is required")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    lowered = url.lower()
    remote_markers = ("staging", "prod", "production", "amazonaws.com", "neon.tech", "supabase.co")
    if any(marker in lowered for marker in remote_markers) and not allow_nonlocal:
        raise SystemExit("refusing a staging or production database URL")
    if host not in {"localhost", "127.0.0.1", "::1"} and not allow_nonlocal:
        raise SystemExit("refusing a non-local DATABASE_URL; pass --allow-nonlocal to override")


def safe_target(url: str) -> str:
    named = os.environ.get("PATCHHIVE_DB_ENV", "").strip()
    if named in {"staging", "prod"}:
        return named
    parsed = urlparse(url)
    port = parsed.port or 5432
    name = (parsed.path or "").lstrip("/").split("?", 1)[0]
    return f"{parsed.hostname}:{port}/{name}"


@dataclass
class Op:
    kind: str
    sql: str
    params: dict[str, Any]

    def rendered(self) -> str:
        return render_sql(self.sql, self.params)


@dataclass
class Plan:
    ops: list[Op] = field(default_factory=list)
    inserts: dict[str, int] = field(default_factory=dict)
    updates: dict[str, int] = field(default_factory=dict)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    unmatched: dict[str, int] = field(default_factory=dict)
    verification: dict[str, int] = field(default_factory=dict)
    provenance: dict[str, dict[str, Any]] = field(default_factory=dict)
    power_configs: dict[str, Any] = field(default_factory=dict)

    def add_insert(self, kind: str, op: Op) -> None:
        self.ops.append(op)
        self.inserts[kind] = self.inserts.get(kind, 0) + 1

    def add_update(self, kind: str, op: Op) -> None:
        self.ops.append(op)
        self.updates[kind] = self.updates.get(kind, 0) + 1

    conflicts_total: int = 0

    def conflict(self, **info: Any) -> None:
        # Every conflict is counted (spec 003 FR-016); the receipt lists the first 50.
        self.conflicts_total += 1
        if len(self.conflicts) < 50:
            self.conflicts.append(info)


def _bump(counter: dict[str, int], key: str, amount: int = 1) -> None:
    counter[key] = counter.get(key, 0) + amount


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


POWER_OVERLAY_LATEST = 14
CATALOG_ADDITIONS_LATEST = 6
ENTRY_VERIFICATION = {"verified", "corrected", "flagged"}


def _entry_verification(entry: dict[str, Any]) -> tuple[str | None, str | None]:
    status = entry.get("verification_status")
    if status not in ENTRY_VERIFICATION:
        return None, None
    return status, entry.get("verification_source_url") or entry.get("source_url")


def _load_optional(path: Path) -> dict[str, Any]:
    return _load(path) if path.is_file() else {}


def build_plan(conn: Connection, *, verification_path: Path | None = None) -> Plan:
    plan = Plan()
    phase2 = _load(CATALOG / "seed-phase2-v1.json")
    phase3 = _load(CATALOG / "seed-phase3-v1.json")
    # Removed 2026-10-17 (ModularGrid-derived); kept optional so old checkouts still load.
    candidates = _load_optional(CATALOG / "overlays" / "catalog-new-brand-candidates-v1.json")
    verification = _verification_index(verification_path)
    catalog = _catalog_state(conn)
    modules = _module_state(conn)
    manufacturers = _manufacturer_state(conn)
    history = _reverify_history(conn)

    # Archive-then-null runs first, so later fills from manufacturer overlays
    # can fill a field this run just cleared.
    for manifest_path in PROVENANCE_MANIFESTS:
        if manifest_path.is_file():
            _schedule_provenance(
                plan, catalog, modules, _load(manifest_path), _archive_state(conn, manifest_path), history
            )

    for brand in phase2.get("brands") or []:
        _schedule_manufacturer(plan, manufacturers, brand)

    for row in list(phase2.get("catalog_modules") or []) + list(phase3.get("catalog_modules") or []):
        _schedule_catalog(plan, catalog, row, modulargrid_url=row.get("modulargrid_url"))

    review = _load_optional(MAKER_REVIEW)
    # Catalog rows checked against maker pages; an HP one of them carries is not legacy.
    maker_rows: list[dict[str, Any]] = []
    for version in range(1, CATALOG_ADDITIONS_LATEST + 1):
        additions = CATALOG / "overlays" / f"catalog-additions-v{version}.json"
        if additions.is_file():
            for row in _load(additions).get("rows") or []:
                if (reviewed := _reviewed(row, review)) is not None:
                    _schedule_catalog(plan, catalog, reviewed, modulargrid_url=None)
                    maker_rows.append(reviewed)
    for row in review.get("catalog_rows") or []:
        _schedule_catalog(plan, catalog, row, modulargrid_url=None)
        maker_rows.append(row)

    for row in phase2.get("full_spec_modules") or []:
        _schedule_module(
            plan,
            modules,
            {
                "brand": row["brand"],
                "name": row["name"],
                "hp": row.get("hp"),
                "module_type": row.get("module_type") or "UNKNOWN",
                "power_12v_ma": row.get("power_12v_ma"),
                "power_neg12v_ma": row.get("power_neg12v_ma"),
                "power_5v_ma": row.get("power_5v_ma"),
                "depth_mm": row.get("depth_mm"),
                "description": row.get("description"),
                "manufacturer_url": row.get("manufacturer_url"),
                "source": row.get("source") or "SynthCatalogResearch",
                "source_reference": row.get("source_reference"),
                "io_ports": row.get("io_ports") or [],
                "tags": row.get("tags") or [],
                "verification_status": "unverified",
                "verification_source_url": None,
            },
            kind="modules_full_spec",
        )

    # v1 maker/retail (unsourced); v2+ maker re-verify (2026-10-17); v3 T039 triage and
    # v4 T039 remainder (2026-10-30)
    hp_overlays = [
        (hp_path.name, _load_optional(hp_path))
        for hp_path in sorted((CATALOG / "overlays").glob("module-catalog-hp-v*.json"))
    ]
    _schedule_hp_overlays(plan, catalog, hp_overlays)
    _schedule_hp_source_markers(
        plan,
        catalog,
        hp_overlays,
        maker_hp_slugs={
            (row.get("slug") or create_slug(row["brand"].strip(), row["name"].strip()))[:200]
            for row in maker_rows
            if row.get("hp") is not None and row.get("brand") and row.get("name")
        },
    )

    for category_path in sorted((CATALOG / "overlays").glob("module-catalog-category-v*.json")):
        for entry in _load_optional(category_path).get("entries") or []:
            _schedule_category(plan, catalog, entry)

    for row in candidates.get("rows") or []:
        _schedule_candidate(plan, catalog, modules, row, verification)

    overlays = [
        _load(CATALOG / "overlays" / f"module-power-depth-v{version}.json")
        for version in range(1, POWER_OVERLAY_LATEST + 1)
        if (CATALOG / "overlays" / f"module-power-depth-v{version}.json").is_file()
    ]
    for overlay in overlays:
        reviewed = (_reviewed(entry, review) for entry in overlay.get("entries") or [])
        overlay["entries"] = [entry for entry in reviewed if entry is not None]
    # A manufacturer-verified entry is authoritative for its module: older
    # unverified entries for the same module are skipped so their values can
    # never fill a field the verified source left empty.
    verified_keys = {
        ((entry.get("brand") or "").strip(), (entry.get("name") or "").strip())
        for overlay in overlays
        for entry in overlay.get("entries") or []
        if entry.get("verification_status") == "verified"
    }
    for overlay in overlays:
        for entry in overlay.get("entries") or []:
            key = ((entry.get("brand") or "").strip(), (entry.get("name") or "").strip())
            if key in verified_keys and entry.get("verification_status") != "verified":
                continue
            _schedule_power(plan, catalog, modules, entry)

    # Retirements run last, so a row this plan inserts (a fresh database) is
    # tombstoned in the same transaction.
    for retirement_path in sorted((CATALOG / "overlays").glob("catalog-retirements-v*.json")):
        for entry in _load_optional(retirement_path).get("rows") or []:
            _schedule_retirement(plan, catalog, modules, entry)

    # Jumper settings attach to module rows, so they run after every module insert and
    # retirement above (spec 003 D8, T034).
    if POWER_CONFIG_RECEIPT.is_file():
        _schedule_power_configs(
            plan, modules, _load(POWER_CONFIG_RECEIPT), _power_config_state(conn), _load(POWER_CONFIG_LABELS)
        )

    for row in modules.values():
        if row.get("_planned"):
            _bump(plan.verification, row.get("verification_status") or "unverified")
    return plan


# Owner-review decisions: renames that re-key misnamed crawl entries, and catalog rows for
# the products those pages actually describe (spec 003 conflict review, 2026-10-27).
MAKER_REVIEW = CATALOG / "overlays" / "maker-review-v1.json"


def _reviewed(entry: dict[str, Any], review: dict[str, Any]) -> dict[str, Any] | None:
    """The overlay entry or catalog row under the product name its maker page describes.

    None when the review found the page is not a Eurorack module.
    """
    url = entry.get("source_url") or entry.get("manufacturer_url") or ""
    for rename in review.get("renames") or []:
        if (
            entry.get("brand") == rename["brand"]
            and entry.get("name") == rename["name"]
            and url.startswith(rename["url_prefix"])
        ):
            return None if rename.get("not_module") else {**entry, "name": rename["to"]}
    return entry


PROVENANCE_MANIFESTS = (
    CATALOG / "provenance" / "modulargrid-reverify-v1.json",
    CATALOG / "provenance" / "maker-crawl-v2-rail-fix-v1.json",
    CATALOG / "provenance" / "maker-review-v1.json",
    CATALOG / "provenance" / "maker-crawl-v2-jumper-fix-v1.json",
    CATALOG / "provenance" / "maker-corrections-v1.json",
    CATALOG / "provenance" / "maker-corrections-v2.json",
    CATALOG / "provenance" / "maker-corrections-v3.json",
    CATALOG / "provenance" / "maker-corrections-v4.json",
)
ARCHIVE_FIELDS = {
    "modules": {
        "hp",
        "power_12v_ma",
        "power_neg12v_ma",
        "power_5v_ma",
        "depth_mm",
        "verification_status",
        "verification_source_url",
    },
    "module_catalog": {"hp"},
}
NULLABLE = {"modules": set(POWER_FIELDS) | {"verification_source_url"}, "module_catalog": {"hp"}}
ARCHIVE_ACTIONS = {"null", "keep", "flag", "relabel", "correct"}
HP_BAND = (1, 42)  # FR-007


def _correction_problem(table: str, item: dict[str, Any]) -> str | None:
    """Why a ``correct`` entry is unusable, or None (spec 003 FR-038)."""
    if item.get("only_if_value") is None or item.get("value") is None:
        return "correction_needs_old_and_new_value"
    if not str(item.get("evidence_url") or "").startswith("https://"):
        return "correction_needs_maker_page"
    if item["field"] == "hp":
        value = item["value"]
        if not isinstance(value, int) or not HP_BAND[0] <= value <= HP_BAND[1]:
            return "correction_hp_outside_band"
    if item["field"] == "verification_source_url" and not str(item["value"]).startswith("https://"):
        return "correction_bad_url"
    return None
ROW_MARKER = "*"


def module_row_key(brand: str, name: str) -> str:
    return f"{brand}::{name}"


def _archive_state(conn: Connection, manifest_path: Path) -> set[tuple[str, str, str]]:
    batch = _load(manifest_path).get("batch")
    if conn is None:
        return set()
    rows = conn.execute(
        text("SELECT table_name, row_key, field FROM catalog_value_archive WHERE batch = :batch"),
        {"batch": batch},
    ).mappings()
    return {(row["table_name"], row["row_key"], row["field"]) for row in rows}


def _reverify_history(conn: Connection) -> dict[tuple[str, str], list[tuple[str, str, Any]]]:
    """Every archived flag, relabel, null and correct, by row: what the reverify clear reads."""
    if conn is None:
        return {}
    rows = conn.execute(
        text(
            "SELECT table_name, row_key, field, action, archived_at FROM catalog_value_archive "
            "WHERE action IN ('flag', 'relabel', 'null', 'correct')"
        )
    ).mappings()
    history: dict[tuple[str, str], list[tuple[str, str, Any]]] = {}
    for row in rows:
        history.setdefault((row["table_name"], row["row_key"]), []).append(
            (row["field"], row["action"], row["archived_at"])
        )
    return history


def _reverify_open(
    table: str,
    state: dict[str, Any],
    entries: list[tuple[str, str, Any]],
    corrected_now: set[str],
) -> bool:
    """True while the clear in ``_clear_reverify_if_resolved`` would leave the row flagged.

    Mirrors its SQL: a correction must exist, every flagged or relabelled field needs a later
    correction of that field, and every nulled field must hold a value again. A field this run
    corrects counts as fixed, since its archive row is written before the clear runs.
    """
    if not corrected_now and not any(action == "correct" for _, action, _ in entries):
        return True
    for field_name, action, archived_at in entries:
        if action not in {"flag", "relabel"} or field_name == "*" or field_name in corrected_now:
            continue
        if not any(
            other == field_name and kind == "correct" and when >= archived_at for other, kind, when in entries
        ):
            return True
    return any(
        action == "null" and field_name in NULLABLE[table] and state.get(field_name) is None
        for field_name, action, _ in entries
    )


def _schedule_provenance(
    plan: Plan,
    catalog: dict[str, dict[str, Any]],
    modules: dict[tuple[str, str], dict[str, Any]],
    manifest: dict[str, Any],
    archived: set[tuple[str, str, str]],
    history: dict[tuple[str, str], list[tuple[str, str, Any]]] | None = None,
) -> None:
    """Archive listed values with their source tag, then null, flag, relabel or correct.

    Only a ``correct`` entry carries a value: the new one, with the wrong value it
    replaces and the maker page that states it (FR-038). Every other action carries none. Each statement copies the current DB value
    into catalog_value_archive first; the follow-up UPDATE only clears a field
    whose archived copy matches the current value, so nothing is lost and a
    re-run is a no-op. Never deletes.
    """
    batch = manifest.get("batch") or ""
    stats = plan.provenance.setdefault(
        batch,
        {
            "archived_values": 0,
            "already_archived": 0,
            "rows_missing": 0,
            "null_in_db": 0,
            "by_action": {},
            "nulled_values": 0,
            "relabeled_rows": 0,
            "flagged_rows": 0,
        },
    )
    stats.setdefault("rows_already_processed", 0)
    stats.setdefault("value_not_matched", 0)
    stats.setdefault("corrected_values", 0)
    stats.setdefault("refused_row_tombstoned", 0)
    stats.setdefault("reverify_clear_scheduled", 0)
    markers: list[tuple[str, str, str, str]] = []
    resolved: list[tuple[str, str, str, str, dict[str, Any]]] = []
    corrected_now: dict[tuple[str, str], set[str]] = {}
    for row in manifest.get("rows") or []:
        table = row.get("table")
        if table not in ARCHIVE_FIELDS:
            plan.conflict(table="catalog_value_archive", reason="bad_manifest_table")
            continue
        brand = (row.get("brand") or "").strip()
        name = (row.get("name") or "").strip()
        if table == "modules":
            state = modules.get((brand, name))
            row_key = module_row_key(brand, name)
            if state and state.get("_duplicate"):
                plan.conflict(table="modules", brand=brand, name=name, reason="duplicate_brand_name")
                continue
        else:
            row_key = row.get("slug") or create_slug(brand, name)
            state = catalog.get(row_key)
            if state and (state["brand"] != brand or state["name"] != name):
                plan.conflict(table="module_catalog", slug=row_key, reason="provenance_identity_mismatch")
                continue
        if state is not None and (state.get("tombstoned") or state.get("status") == "tombstoned"):
            stats["refused_row_tombstoned"] += 1
            continue
        # A corrected row leaves FLAGGED once every flagged field is fixed (research R8).
        # Checked on every run, so a correction applied before this rule existed counts too.
        if state is not None and state.get("needs_reverify") and any(
            item.get("action") == "correct" for item in row.get("fields") or []
        ):
            resolved.append((table, row_key, brand, name, state))
        # A row is processed once per batch. Rows inserted later (or fields filled
        # later from manufacturer overlays) are never touched by this batch.
        if (table, row_key, ROW_MARKER) in archived:
            stats["rows_already_processed"] += 1
            continue
        markers.append((table, row_key, brand, name))
        if state is None:
            stats["rows_missing"] += 1
            continue
        todo: list[dict[str, Any]] = []
        for item in row.get("fields") or []:
            field_name = item.get("field")
            action = item.get("action")
            if field_name not in ARCHIVE_FIELDS[table] or action not in ARCHIVE_ACTIONS:
                plan.conflict(table=table, field=field_name, reason="bad_manifest_field")
                continue
            if action == "null" and field_name not in NULLABLE[table]:
                plan.conflict(table=table, field=field_name, reason="not_nullable")
                continue
            if action == "correct" and (problem := _correction_problem(table, item)):
                plan.conflict(table=table, field=field_name, reason=problem)
                continue
            if (table, row_key, field_name) in archived:
                stats["already_archived"] += 1
                continue
            if state.get(field_name) is None:
                stats["null_in_db"] += 1
                continue
            # A correction names the wrong value it clears; any other value is left alone.
            expected = item.get("only_if_value")
            if expected is not None and str(state.get(field_name)) != str(expected) and not (
                field_name in POWER_FIELDS and float(state[field_name]) == float(expected)
            ):
                stats["value_not_matched"] += 1
                continue
            todo.append(item)
        if not todo:
            continue
        _archive_row(plan, batch, table, row_key, brand, name, todo)
        stats["archived_values"] += len(todo)
        for item in todo:
            _bump(stats["by_action"], item["action"])
        corrections = [item for item in todo if item["action"] == "correct"]
        if corrections:
            _correct_row(plan, batch, table, row_key, brand, name, corrections)
            for item in corrections:
                state[item["field"]] = item["value"]
            corrected_now.setdefault((table, row_key), set()).update(item["field"] for item in corrections)
            stats["corrected_values"] += len(corrections)
        todo = [item for item in todo if item["action"] != "correct"]
        if not todo:
            continue
        nulls = [item["field"] for item in todo if item["action"] == "null"]
        relabel = any(item["action"] == "relabel" for item in todo)
        if not nulls and not relabel and all(item["action"] == "keep" for item in todo):
            continue
        flag = row.get("flag_reverify", manifest.get("flag_reverify", True))
        _reverify_row(plan, batch, table, row_key, brand, name, nulls, relabel, flag)
        for field_name in nulls:
            state[field_name] = None
        stats["nulled_values"] += len(nulls)
        if relabel and state.get("verification_status") in {"verified", "corrected"}:
            state["verification_status"] = "unverified"
            state["verification_source_url"] = None
            stats["relabeled_rows"] += 1
        if flag:
            stats["flagged_rows"] += 1
    if markers:
        _archive_markers(plan, batch, markers)
    for table, row_key, brand, name, state in resolved:
        # Without the archive history (a test calling this directly) the database decides alone.
        if history is not None and _reverify_open(
            table, state, history.get((table, row_key), []), corrected_now.get((table, row_key), set())
        ):
            continue
        _clear_reverify_if_resolved(plan, table, row_key, brand, name)
        stats["reverify_clear_scheduled"] += 1


def _clear_reverify_if_resolved(plan: Plan, table: str, row_key: str, brand: str, name: str) -> None:
    """Clear ``needs_reverify`` once every field the row was flagged for is fixed (FLAGGED -> LIVE).

    A ``flag`` or ``relabel`` is fixed by a later ``correct`` of the same field; a ``null`` is
    fixed once the field holds a value again. The database decides, so the statement is safe
    to re-run and does nothing while any flagged field is still open.
    """
    nulled_and_empty = [
        f"({column} IS NULL AND EXISTS (SELECT 1 FROM catalog_value_archive n "
        f"WHERE n.table_name = '{table}' AND n.row_key = :row_key AND n.field = '{column}' "
        "AND n.action = 'null'))"
        for column in sorted(NULLABLE[table])
    ]
    plan.add_update(
        f"{table}_reverify_cleared",
        Op(
            "clear_reverify",
            f"""
            UPDATE {table}
            SET needs_reverify = FALSE,
                {"updated_at = :updated_at" if table == "module_catalog" else "updated_at = CURRENT_TIMESTAMP"}
            WHERE {_row_where(table)}
              AND needs_reverify
              AND EXISTS (
                SELECT 1 FROM catalog_value_archive c
                WHERE c.table_name = '{table}' AND c.row_key = :row_key AND c.action = 'correct'
              )
              AND NOT EXISTS (
                SELECT 1 FROM catalog_value_archive a
                WHERE a.table_name = '{table}' AND a.row_key = :row_key
                  AND a.action IN ('flag', 'relabel') AND a.field <> '*'
                  AND NOT EXISTS (
                    SELECT 1 FROM catalog_value_archive c
                    WHERE c.table_name = a.table_name AND c.row_key = a.row_key
                      AND c.field = a.field AND c.action = 'correct' AND c.archived_at >= a.archived_at
                  )
              )
              AND NOT ({" OR ".join(nulled_and_empty)})
            """,
            {"row_key": row_key, "brand": brand, "name": name, "updated_at": _stamp()},
        ),
    )


def _archive_markers(plan: Plan, batch: str, markers: list[tuple[str, str, str, str]]) -> None:
    params: dict[str, Any] = {"batch": batch, "marker": ROW_MARKER}
    values = []
    for index, (table, row_key, brand, name) in enumerate(markers):
        params[f"mt{index}"] = table
        params[f"mk{index}"] = row_key
        params[f"mb{index}"] = brand
        params[f"mn{index}"] = name
        values.append(f"(:mt{index}, :mk{index}, :mb{index}, :mn{index})")
    plan.add_insert(
        "catalog_value_archive_markers",
        Op(
            "archive_markers",
            """
            INSERT INTO catalog_value_archive (
                batch, table_name, row_key, brand, name, field,
                old_value, source_tag, maker_check, action, archived_at
            )
            SELECT :batch, v.table_name, v.row_key, v.brand, v.name, :marker,
                   NULL, 'row_processed', NULL, 'processed', CURRENT_TIMESTAMP
            FROM (VALUES
                """
            + ",\n                ".join(values)
            + """
            ) AS v(table_name, row_key, brand, name)
            WHERE NOT EXISTS (
                SELECT 1 FROM catalog_value_archive a
                WHERE a.batch = :batch AND a.table_name = v.table_name
                  AND a.row_key = v.row_key AND a.field = :marker
            )
            """,
            params,
        ),
    )


def _row_where(table: str) -> str:
    # A retired row is final (row lifecycle): no manifest archives, corrects or flags it.
    if table == "modules":
        return "brand = :brand AND name = :name AND status <> 'tombstoned'"
    return "slug = :row_key AND brand = :brand AND name = :name AND tombstoned_at IS NULL"


def _archive_row(
    plan: Plan,
    batch: str,
    table: str,
    row_key: str,
    brand: str,
    name: str,
    items: list[dict[str, Any]],
) -> None:
    params: dict[str, Any] = {"batch": batch, "table_name": table, "row_key": row_key, "brand": brand, "name": name}
    selects = []
    for index, item in enumerate(items):
        column = item["field"]
        if column not in ARCHIVE_FIELDS[table]:
            raise RuntimeError("refusing unknown archive field")
        params[f"f{index}"] = column
        params[f"t{index}"] = str(item.get("source_tag") or "unknown")[:200]
        params[f"m{index}"] = (item.get("maker_check") or None) and str(item["maker_check"])[:40]
        params[f"a{index}"] = item["action"]
        expected = ""
        if item.get("only_if_value") is not None:
            params[f"e{index}"] = str(item["only_if_value"])
            numeric = column in POWER_FIELDS or column == "hp"
            current = f"CAST(t.{column} AS NUMERIC)" if numeric else f"CAST(t.{column} AS TEXT)"
            wanted = f"CAST(:e{index} AS NUMERIC)" if numeric else f":e{index}"
            expected = f"\n              AND {current} = {wanted}"
        selects.append(
            f"""
            SELECT :batch, :table_name, :row_key, :brand, :name, :f{index},
                   CAST(t.{column} AS TEXT), :t{index}, :m{index}, :a{index}, CURRENT_TIMESTAMP
            FROM {table} t
            WHERE {_row_where(table).replace("brand =", "t.brand =").replace("name =", "t.name =").replace("slug =", "t.slug =").replace("status <>", "t.status <>").replace("tombstoned_at IS", "t.tombstoned_at IS")}
              AND t.{column} IS NOT NULL{expected}
              AND NOT EXISTS (
                SELECT 1 FROM catalog_value_archive a
                WHERE a.batch = :batch AND a.table_name = :table_name
                  AND a.row_key = :row_key AND a.field = :f{index}
              )"""
        )
    plan.add_insert(
        "catalog_value_archive",
        Op(
            "archive_values",
            """
            INSERT INTO catalog_value_archive (
                batch, table_name, row_key, brand, name, field,
                old_value, source_tag, maker_check, action, archived_at
            )"""
            + "\n            UNION ALL".join(selects),
            params,
        ),
    )


def _correct_row(
    plan: Plan,
    batch: str,
    table: str,
    row_key: str,
    brand: str,
    name: str,
    items: list[dict[str, Any]],
) -> None:
    """Write corrected values, only where this batch archived the value now stored.

    The archive insert above copies a value only while it equals ``only_if_value``, so a
    value changed since review is neither archived nor overwritten (FR-038).
    """
    params: dict[str, Any] = {"batch": batch, "row_key": row_key, "brand": brand, "name": name}
    sets = []
    for index, item in enumerate(items):
        column = item["field"]
        if column not in ARCHIVE_FIELDS[table]:
            raise RuntimeError("refusing unknown correction field")
        params[f"c{index}"] = item["value"]
        sets.append(
            f"{column} = CASE WHEN EXISTS (SELECT 1 FROM catalog_value_archive a WHERE a.batch = :batch "
            f"AND a.table_name = '{table}' AND a.row_key = :row_key AND a.field = '{column}' "
            f"AND a.action = 'correct' AND a.old_value = CAST({table}.{column} AS TEXT)) "
            f"THEN :c{index} ELSE {column} END"
        )
    sets.append("updated_at = :updated_at" if table == "module_catalog" else "updated_at = CURRENT_TIMESTAMP")
    params["updated_at"] = _stamp()
    assignments = ",\n                ".join(sets)
    plan.add_update(
        f"{table}_correct",
        Op(
            "correct_values",
            f"""
            UPDATE {table}
            SET {assignments}
            WHERE {_row_where(table)}
            """,
            params,
        ),
    )


def _reverify_row(
    plan: Plan,
    batch: str,
    table: str,
    row_key: str,
    brand: str,
    name: str,
    nulls: list[str],
    relabel: bool,
    flag_reverify: bool = True,
) -> None:
    def archived(field_name: str, action: str, column: str | None = None) -> str:
        match = f" AND a.old_value = CAST({table}.{column} AS TEXT)" if column else ""
        return (
            "EXISTS (SELECT 1 FROM catalog_value_archive a WHERE a.batch = :batch "
            f"AND a.table_name = '{table}' AND a.row_key = :row_key AND a.field = '{field_name}' "
            f"AND a.action = '{action}'{match})"
        )

    sets = []
    for column in nulls:
        if column not in NULLABLE[table]:
            raise RuntimeError("refusing to null a NOT NULL column")
        sets.append(f"{column} = CASE WHEN {archived(column, 'null', column)} THEN NULL ELSE {column} END")
    if relabel and table == "modules":
        sets.append(
            "verification_status = CASE WHEN verification_status IN ('verified', 'corrected') AND "
            f"{archived('verification_status', 'relabel', 'verification_status')} THEN 'unverified' "
            "ELSE verification_status END"
        )
        sets.append(
            "verification_source_url = CASE WHEN "
            f"{archived('verification_source_url', 'relabel', 'verification_source_url')} THEN NULL "
            "ELSE verification_source_url END"
        )
    if flag_reverify:
        sets.append("needs_reverify = TRUE")
    sets.append("updated_at = :updated_at" if table == "module_catalog" else "updated_at = CURRENT_TIMESTAMP")
    assignments = ",\n                ".join(sets)
    plan.add_update(
        f"{table}_reverify",
        Op(
            "reverify_row",
            f"""
            UPDATE {table} SET
                {assignments}
            WHERE {_row_where(table)}
              AND EXISTS (
                SELECT 1 FROM catalog_value_archive a
                WHERE a.batch = :batch AND a.table_name = '{table}' AND a.row_key = :row_key
                  AND a.field <> '*'
              )
            """,
            {"batch": batch, "row_key": row_key, "brand": brand, "name": name, "updated_at": _stamp()},
        ),
    )


def _verification_index(path: Path | None) -> dict[str, dict[str, Any]]:
    file_path = path or (CATALOG / "hermes-research" / "batch8-brand-verification.json")
    if not file_path.is_file():
        return {}
    payload = _load(file_path)
    rows = payload.get("rows") or payload.get("brand_verification", {}).get("rows") or []
    return {row.get("source_url"): row for row in rows if row.get("source_url")}


def _catalog_state(conn: Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        text("SELECT slug, brand, name, hp, hp_source, category, tombstoned_at, needs_reverify FROM module_catalog")
    ).mappings()
    return {
        row["slug"]: {
            "brand": row["brand"],
            "name": row["name"],
            "hp": row["hp"],
            "hp_source": row["hp_source"],
            "category": row["category"],
            "tombstoned": row["tombstoned_at"] is not None,
            "needs_reverify": bool(row["needs_reverify"]),
            "_planned": False,
        }
        for row in rows
    }


def _module_state(conn: Connection) -> dict[tuple[str, str], dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT brand, name, hp, power_12v_ma, power_neg12v_ma, power_5v_ma, depth_mm, "
            "verification_status, verification_source_url, status, needs_reverify, source_reference "
            "FROM modules"
        )
    ).mappings()
    state: dict[tuple[str, str], dict[str, Any]] = {}
    duplicates: set[tuple[str, str]] = set()
    for row in rows:
        key = (row["brand"], row["name"])
        if key in state:
            duplicates.add(key)
        state[key] = {**dict(row), "_planned": False, "_duplicate": False}
    for key in duplicates:
        state[key]["_duplicate"] = True
    return state


def _manufacturer_state(conn: Connection) -> set[str]:
    rows = conn.execute(text("SELECT slug FROM manufacturers")).mappings()
    return {row["slug"] for row in rows}


def _schedule_manufacturer(plan: Plan, seen: set[str], brand: str) -> None:
    slug = create_slug(brand, "")[:100]
    if slug in seen:
        return
    if len(brand) > 100:
        plan.conflict(table="manufacturers", brand=brand, reason="name_too_long")
        return
    seen.add(slug)
    provenance = json.dumps(
        {
            "source": "data/synth-catalog/seed-phase2-v1.json",
            "provenance": "OBSERVED",
            "note": "brand index entry; activity not verified",
        }
    )
    plan.add_insert(
        "manufacturers",
        Op(
            "insert_manufacturer",
            """
            INSERT INTO manufacturers
                (canonical_name, slug, aliases, website, status, provenance, created_at, updated_at)
            SELECT :canonical_name, :slug, CAST(:aliases AS json), NULL, 'unknown',
                   CAST(:provenance AS json), NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM manufacturers WHERE slug = :slug OR canonical_name = :canonical_name
            )
            """,
            {
                "canonical_name": brand,
                "slug": slug,
                "aliases": "[]",
                "provenance": provenance,
            },
        ),
    )


def _schedule_catalog(plan: Plan, catalog: dict[str, dict[str, Any]], row: dict[str, Any], modulargrid_url: str | None) -> None:
    brand = (row.get("brand") or "").strip()
    name = (row.get("name") or "").strip()
    if not brand or not name:
        plan.conflict(table="module_catalog", reason="missing_identity")
        return
    slug = (row.get("slug") or create_slug(brand, name))[:200]
    existing = catalog.get(slug)
    if existing and (existing["brand"] != brand or existing["name"] != name):
        plan.conflict(table="module_catalog", slug=slug, reason="identity_mismatch")
        return
    if existing:
        if existing["hp"] is None and row.get("hp") is not None:
            existing["hp"] = row["hp"]
            plan.add_update("module_catalog_hp", _hp_update(slug, brand, name, int(row["hp"])))
        if existing.get("category") is None and row.get("category"):
            existing["category"] = row["category"]
            plan.add_update("module_catalog_category", _category_update(slug, brand, name, str(row["category"])))
        return
    catalog[slug] = {
        "brand": brand,
        "name": name,
        "hp": row.get("hp"),
        "category": row.get("category"),
        "_planned": True,
    }
    plan.add_insert(
        "module_catalog",
        Op(
            "insert_catalog",
            """
            INSERT INTO module_catalog (
                slug, brand, name, hp, category, modulargrid_url, manufacturer_url,
                image_url, is_available, source, access_basis, evidence_status,
                created_at, updated_at
            )
            SELECT :slug, :brand, :name, :hp, :category, :modulargrid_url, :manufacturer_url,
                   :image_url, :is_available, :source, :access_basis, :evidence_status,
                   :created_at, :updated_at
            WHERE NOT EXISTS (SELECT 1 FROM module_catalog WHERE slug = :slug)
            """,
            {
                "slug": slug,
                "brand": brand,
                "name": name,
                "hp": row.get("hp"),
                "category": row.get("category"),
                "modulargrid_url": modulargrid_url,
                "manufacturer_url": row.get("manufacturer_url"),
                "image_url": (row.get("image_url") or None) and str(row.get("image_url"))[:500],
                "is_available": row.get("is_available") or "available",
                "source": row.get("source") or "SynthCatalogResearch",
                # Spec 003 D1: ModularGrid-derived seed rows arrive tagged as leads.
                "access_basis": row.get("access_basis"),
                "evidence_status": row.get("evidence_status"),
                "created_at": _stamp(),
                "updated_at": _stamp(),
            },
        ),
    )


# HP overlays written before entries carried their maker page. Kept as loaded
# (spec 003 FR-024 review pending); every later HP overlay must cite a maker page.
UNSOURCED_HP_OVERLAYS = frozenset({"module-catalog-hp-v1.json"})


def _hp_entry_sourced(entry: dict[str, Any]) -> bool:
    """HP decides placement, so only a maker page may supply it (FR-024, FR-027)."""
    return entry.get("source_class") == "maker" and str(entry.get("source_url") or "").startswith("https://")


def _hp_entry_keys(entry: dict[str, Any]) -> set[str]:
    """Every catalog slug ``_schedule_hp`` could resolve this entry to."""
    keys = {entry["slug"]} if entry.get("slug") else set()
    brand = (entry.get("brand") or "").strip()
    name = (entry.get("name") or "").strip()
    if brand and name:
        keys.add(create_slug(brand, name))
    return keys


def _schedule_hp_overlays(
    plan: Plan,
    catalog: dict[str, dict[str, Any]],
    overlays: list[tuple[str, dict[str, Any]]],
) -> None:
    """Fill empty HP from every HP overlay, in the given (sorted) order.

    A maker-cited entry takes precedence over an unsourced legacy entry for the
    same module: a legacy entry is skipped wherever any sourced overlay carries an
    HP for that slug, so the maker value lands on an empty row whichever file
    sorts first. Fill-null is unchanged: a stored HP is never overwritten (a
    stored wrong value is fixed only by a reviewed ``correct`` entry, D4).
    """
    sourced_slugs: set[str] = set()
    for overlay_name, overlay in overlays:
        if overlay_name in UNSOURCED_HP_OVERLAYS:
            continue
        for entry in overlay.get("entries") or []:
            if entry.get("hp") is not None and _hp_entry_sourced(entry):
                sourced_slugs |= _hp_entry_keys(entry)
    for overlay_name, overlay in overlays:
        legacy = overlay_name in UNSOURCED_HP_OVERLAYS
        for entry in overlay.get("entries") or []:
            if legacy and not _hp_entry_sourced(entry) and _hp_entry_keys(entry) & sourced_slugs:
                continue
            _schedule_hp(plan, catalog, entry, legacy_unsourced=legacy)


HP_SOURCE_LEGACY = "legacy_unsourced"


def _schedule_hp_source_markers(
    plan: Plan,
    catalog: dict[str, dict[str, Any]],
    overlays: list[tuple[str, dict[str, Any]]],
    *,
    maker_hp_slugs: set[str] | frozenset[str] = frozenset(),
) -> None:
    """Keep ``module_catalog.hp_source = 'legacy_unsourced'`` on exactly the rows whose
    stored HP is an unsourced legacy overlay value (spec 003 T039).

    A row is marked when an entry of an ``UNSOURCED_HP_OVERLAYS`` file names it, the
    stored HP equals that entry's HP, and no maker source carries an HP for the slug
    (a maker-cited HP overlay entry, or a maker-checked catalog row in
    ``maker_hp_slugs``). A marked row that no longer qualifies (re-sourced, or its HP
    corrected) is cleared. Runs after the HP fills, so it sees this plan's values.
    Only the marker changes; HP is never written here.
    """
    sourced = set(maker_hp_slugs)
    for overlay_name, overlay in overlays:
        if overlay_name in UNSOURCED_HP_OVERLAYS:
            continue
        for entry in overlay.get("entries") or []:
            if entry.get("hp") is not None and _hp_entry_sourced(entry):
                sourced |= _hp_entry_keys(entry)
    legacy: set[str] = set()
    for overlay_name, overlay in overlays:
        if overlay_name not in UNSOURCED_HP_OVERLAYS:
            continue
        for entry in overlay.get("entries") or []:
            hp = entry.get("hp")
            if hp is None or _hp_entry_sourced(entry) or _hp_entry_keys(entry) & sourced:
                continue
            brand = (entry.get("brand") or "").strip()
            name = (entry.get("name") or "").strip()
            slug = entry.get("slug")
            row = catalog.get(slug) if slug else None
            if row is None and brand and name:
                slug = create_slug(brand, name)
                row = catalog.get(slug)
            if row is None or row["brand"] != brand or row["name"] != name:
                continue
            if row.get("hp") is not None and int(row["hp"]) == int(hp):
                legacy.add(slug)
    for slug in sorted(catalog):
        row = catalog[slug]
        current = row.get("hp_source")
        if slug in legacy and current is None:
            row["hp_source"] = HP_SOURCE_LEGACY
            plan.add_update(
                "hp_source_legacy_marked",
                Op(
                    "mark_hp_source",
                    """
                    UPDATE module_catalog
                    SET hp_source = :hp_source, updated_at = :updated_at
                    WHERE slug = :slug AND brand = :brand AND name = :name AND hp = :hp AND hp_source IS NULL
                    """,
                    {"slug": slug, "brand": row["brand"], "name": row["name"], "hp": int(row["hp"]),
                     "hp_source": HP_SOURCE_LEGACY, "updated_at": _stamp()},
                ),
            )
        elif slug not in legacy and current == HP_SOURCE_LEGACY:
            row["hp_source"] = None
            plan.add_update(
                "hp_source_legacy_cleared",
                Op(
                    "clear_hp_source",
                    """
                    UPDATE module_catalog
                    SET hp_source = NULL, updated_at = :updated_at
                    WHERE slug = :slug AND brand = :brand AND name = :name AND hp_source = :hp_source
                    """,
                    {"slug": slug, "brand": row["brand"], "name": row["name"],
                     "hp_source": HP_SOURCE_LEGACY, "updated_at": _stamp()},
                ),
            )


def _schedule_hp(
    plan: Plan,
    catalog: dict[str, dict[str, Any]],
    entry: dict[str, Any],
    *,
    legacy_unsourced: bool = False,
) -> None:
    slug = entry.get("slug")
    brand = (entry.get("brand") or "").strip()
    name = (entry.get("name") or "").strip()
    hp = entry.get("hp")
    if hp is None:
        return
    sourced = _hp_entry_sourced(entry)
    if not sourced and not legacy_unsourced:
        plan.conflict(table="module_catalog", slug=slug, reason="hp_overlay_unsourced")
        return
    row = catalog.get(slug) if slug else None
    if row is None and brand and name:
        slug = create_slug(brand, name)
        row = catalog.get(slug)
    if row is None:
        _bump(plan.unmatched, "hp")
        return
    if row["brand"] != brand or row["name"] != name:
        plan.conflict(table="module_catalog", slug=slug, reason="hp_overlay_identity_mismatch")
        return
    if row["hp"] is not None:
        return
    row["hp"] = hp
    plan.add_update("hp_overlay", _hp_update(slug, brand, name, int(hp)))


def _schedule_category(plan: Plan, catalog: dict[str, dict[str, Any]], entry: dict[str, Any]) -> None:
    """Fill a catalog row's missing category from a category overlay (never overwrite)."""
    slug = entry.get("slug")
    brand = (entry.get("brand") or "").strip()
    name = (entry.get("name") or "").strip()
    category = entry.get("category")
    if not category:
        return
    row = catalog.get(slug) if slug else None
    if row is None:
        _bump(plan.unmatched, "category")
        return
    if row["brand"] != brand or row["name"] != name:
        plan.conflict(table="module_catalog", slug=slug, reason="category_overlay_identity_mismatch")
        return
    if row.get("category"):
        return
    row["category"] = category
    plan.add_update("category_overlay", _category_update(slug, brand, name, str(category)))


def _schedule_retirement(
    plan: Plan,
    catalog: dict[str, dict[str, Any]],
    modules: dict[tuple[str, str], dict[str, Any]],
    entry: dict[str, Any],
) -> None:
    """Tombstone a catalog row and its module row named by a retirement manifest.

    Never deletes: module_catalog gets tombstoned_at and a reason, modules gets
    status 'tombstoned' (the admin convention). Rows already tombstoned are left alone.
    """
    brand = (entry.get("brand") or "").strip()
    name = (entry.get("name") or "").strip()
    reason = (entry.get("reason") or "").strip()
    if not (brand and name and reason):
        plan.conflict(table="module_catalog", reason="retirement_missing_identity_or_reason")
        return
    slug = (entry.get("slug") or create_slug(brand, name))[:200]
    row = catalog.get(slug)
    if row is None:
        _bump(plan.unmatched, "retire_catalog")
    elif row["brand"] != brand or row["name"] != name:
        plan.conflict(table="module_catalog", slug=slug, reason="retirement_identity_mismatch")
        return
    elif not row.get("tombstoned"):
        row["tombstoned"] = True
        plan.add_update(
            "catalog_retire",
            Op(
                "retire_catalog",
                """
                UPDATE module_catalog
                SET tombstoned_at = CAST(:tombstoned_at AS TIMESTAMP), tombstone_reason = :reason,
                    updated_at = :updated_at
                WHERE slug = :slug AND brand = :brand AND name = :name AND tombstoned_at IS NULL
                """,
                {"slug": slug, "brand": brand, "name": name, "reason": reason[:200],
                 "tombstoned_at": _stamp(), "updated_at": _stamp()},
            ),
        )
    module = modules.get((brand, name))
    if module is None:
        _bump(plan.unmatched, "retire_module")
    elif module.get("status") != "tombstoned":
        module["status"] = "tombstoned"
        plan.add_update(
            "module_retire",
            Op(
                "retire_module",
                """
                UPDATE modules
                SET status = 'tombstoned', tombstoned_at = CAST(:tombstoned_at AS TIMESTAMP)
                WHERE brand = :brand AND name = :name AND status IS DISTINCT FROM 'tombstoned'
                """,
                {"brand": brand, "name": name, "tombstoned_at": _stamp()},
            ),
        )


def _category_update(slug: str, brand: str, name: str, category: str) -> Op:
    return Op(
        "update_category",
        """
        UPDATE module_catalog
        SET category = :category, updated_at = :updated_at
        WHERE slug = :slug AND brand = :brand AND name = :name AND category IS NULL
        """,
        {"slug": slug, "brand": brand, "name": name, "category": category[:50], "updated_at": _stamp()},
    )


def _hp_update(slug: str, brand: str, name: str, hp: int) -> Op:
    return Op(
        "update_hp",
        """
        UPDATE module_catalog
        SET hp = :hp, updated_at = :updated_at
        WHERE slug = :slug AND brand = :brand AND name = :name AND hp IS NULL
        """,
        {"slug": slug, "brand": brand, "name": name, "hp": hp, "updated_at": _stamp()},
    )


def _schedule_candidate(
    plan: Plan,
    catalog: dict[str, dict[str, Any]],
    modules: dict[tuple[str, str], dict[str, Any]],
    row: dict[str, Any],
    verification: dict[str, dict[str, Any]],
) -> None:
    source_url = row.get("source_url")
    checked = verification.get(source_url) or {}
    brand = (checked.get("effective_brand") or row.get("brand") or "").strip()
    name = (checked.get("module_name") or name_from_title(row.get("page_title") or "", brand)).strip()
    status = checked.get("verification_status") or "unverified"
    if status not in VERIFICATION_STATUSES:
        plan.conflict(table="modules", source_url=source_url, reason="bad_verification_status")
        status = "unverified"
    if not brand or not name or row.get("hp") is None:
        plan.conflict(table="modules", source_url=source_url, reason="candidate_missing_hp_or_name")
        return
    _schedule_catalog(
        plan,
        catalog,
        {
            "brand": brand,
            "name": name,
            "hp": row.get("hp"),
            "category": None,
            "is_available": "available",
            "source": "CatalogCandidate",
            "manufacturer_url": None,
            "slug": create_slug(brand, name),
        },
        modulargrid_url=source_url,
    )
    _schedule_module(
        plan,
        modules,
        {
            "brand": brand,
            "name": name,
            "hp": int(row["hp"]),
            "module_type": "UNKNOWN",
            "power_12v_ma": row.get("power_12v_ma"),
            "power_neg12v_ma": row.get("power_neg12v_ma"),
            "power_5v_ma": row.get("power_5v_ma"),
            "depth_mm": row.get("depth_mm"),
            "description": None,
            "manufacturer_url": None,
            "source": "CatalogCandidate",
            "source_reference": source_url,
            "io_ports": [],
            "tags": [],
            "verification_status": status,
            "verification_source_url": checked.get("source_url") or source_url,
        },
        kind="modules_candidates",
    )


def _schedule_module(plan: Plan, modules: dict[tuple[str, str], dict[str, Any]], row: dict[str, Any], *, kind: str) -> None:
    brand = row["brand"].strip()
    name = row["name"].strip()
    if row.get("hp") is None:
        plan.conflict(table="modules", brand=brand, name=name, reason="hp_required")
        return
    key = (brand, name)
    existing = modules.get(key)
    if existing and existing.get("_duplicate"):
        plan.conflict(table="modules", brand=brand, name=name, reason="duplicate_brand_name")
        return
    if existing:
        _schedule_fill(plan, existing, row, kind="modules_fill")
        return
    status = row.get("verification_status") or "unverified"
    modules[key] = {
        "brand": brand,
        "name": name,
        "hp": int(row["hp"]),
        "power_12v_ma": row.get("power_12v_ma"),
        "power_neg12v_ma": row.get("power_neg12v_ma"),
        "power_5v_ma": row.get("power_5v_ma"),
        "depth_mm": row.get("depth_mm"),
        "verification_status": status,
        "verification_source_url": row.get("verification_source_url"),
        "source_reference": (row.get("source_reference") or "")[:500] or None,
        "_planned": True,
        "_duplicate": False,
    }
    plan.add_insert(
        kind,
        Op(
            "insert_module",
            """
            INSERT INTO modules (
                brand, name, hp, module_type,
                power_12v_ma, power_neg12v_ma, power_5v_ma, depth_mm,
                io_ports, tags, description, manufacturer_url,
                source, source_reference, status,
                verification_status, verification_source_url,
                imported_at, created_at, updated_at
            )
            SELECT :brand, :name, :hp, :module_type,
                   :power_12v_ma, :power_neg12v_ma, :power_5v_ma, :depth_mm,
                   CAST(:io_ports AS json), CAST(:tags AS json), :description, :manufacturer_url,
                   :source, :source_reference, 'active',
                   :verification_status, :verification_source_url,
                   NOW(), NOW(), NOW()
            WHERE NOT EXISTS (SELECT 1 FROM modules WHERE brand = :brand AND name = :name)
            """,
            {
                "brand": brand,
                "name": name,
                "hp": int(row["hp"]),
                "module_type": row.get("module_type") or "UNKNOWN",
                "power_12v_ma": row.get("power_12v_ma"),
                "power_neg12v_ma": row.get("power_neg12v_ma"),
                "power_5v_ma": row.get("power_5v_ma"),
                "depth_mm": row.get("depth_mm"),
                "io_ports": json.dumps(row.get("io_ports") or []),
                "tags": json.dumps(row.get("tags") or []),
                "description": row.get("description"),
                "manufacturer_url": row.get("manufacturer_url"),
                "source": row.get("source") or "SynthCatalogResearch",
                "source_reference": (row.get("source_reference") or "")[:500] or None,
                "verification_status": status,
                "verification_source_url": row.get("verification_source_url"),
            },
        ),
    )


# modules.power_* are INTEGER columns: a published 3.5 mA is stored as 4.
INTEGER_POWER_FIELDS = ("power_12v_ma", "power_neg12v_ma", "power_5v_ma")


def _as_stored(field_name: str, value: Any) -> float:
    """The value as the column keeps it (numeric to integer rounds half away from zero)."""
    number = float(value)
    if field_name in INTEGER_POWER_FIELDS:
        return float(math.copysign(math.floor(abs(number) + 0.5), number))
    return number


def _schedule_fill(plan: Plan, existing: dict[str, Any], incoming: dict[str, Any], *, kind: str) -> None:
    fill: dict[str, Any] = {}
    if incoming.get("verification_status") == "verified" and any(
        existing.get(name) is not None
        and incoming.get(name) is not None
        and _as_stored(name, existing[name]) != _as_stored(name, incoming[name])
        for name in POWER_FIELDS
    ):
        # Stored values disagree with the verified source. Never overwrite them;
        # mark the row for review instead of calling it verified.
        incoming = {**incoming, "verification_status": "flagged"}
    for field_name in POWER_FIELDS:
        if existing.get(field_name) is None and incoming.get(field_name) is not None:
            fill[field_name] = incoming[field_name]
            existing[field_name] = incoming[field_name]
    incoming_status = incoming.get("verification_status")
    if (
        existing.get("verification_status") == "unverified"
        and incoming_status in {"verified", "corrected", "flagged"}
    ):
        fill["verification_status"] = incoming_status
        existing["verification_status"] = incoming_status
    elif (
        # Only a source that claims verification can disagree with one; an
        # unverified seed row never conflicts with a verified module.
        incoming_status in ENTRY_VERIFICATION
        and existing.get("verification_status") not in {None, "unverified", "flagged", incoming_status}
    ):
        plan.conflict(
            table="modules",
            brand=existing["brand"],
            name=existing["name"],
            reason="verification_conflict",
        )
    if existing.get("verification_source_url") is None and incoming.get("verification_source_url"):
        fill["verification_source_url"] = incoming["verification_source_url"]
        existing["verification_source_url"] = incoming["verification_source_url"]
    if not fill:
        return
    params = {
        "brand": existing["brand"],
        "name": existing["name"],
        "power_12v_ma": fill.get("power_12v_ma"),
        "power_neg12v_ma": fill.get("power_neg12v_ma"),
        "power_5v_ma": fill.get("power_5v_ma"),
        "depth_mm": fill.get("depth_mm"),
        "verification_status": fill.get("verification_status") or existing.get("verification_status") or "unverified",
        "verification_source_url": fill.get("verification_source_url"),
    }
    plan.add_update(
        kind,
        Op(
            "fill_module",
            """
            UPDATE modules SET
                power_12v_ma = COALESCE(power_12v_ma, :power_12v_ma),
                power_neg12v_ma = COALESCE(power_neg12v_ma, :power_neg12v_ma),
                power_5v_ma = COALESCE(power_5v_ma, :power_5v_ma),
                depth_mm = COALESCE(depth_mm, :depth_mm),
                verification_status = CASE
                    WHEN verification_status = 'unverified'
                         AND :verification_status IN ('verified', 'corrected', 'flagged')
                    THEN :verification_status
                    ELSE verification_status
                END,
                verification_source_url = COALESCE(verification_source_url, :verification_source_url),
                updated_at = NOW()
            WHERE brand = :brand AND name = :name
              AND (
                (power_12v_ma IS NULL AND :power_12v_ma IS NOT NULL)
                OR (power_neg12v_ma IS NULL AND :power_neg12v_ma IS NOT NULL)
                OR (power_5v_ma IS NULL AND :power_5v_ma IS NOT NULL)
                OR (depth_mm IS NULL AND :depth_mm IS NOT NULL)
                OR (verification_status = 'unverified'
                    AND :verification_status IN ('verified', 'corrected', 'flagged'))
                OR (verification_source_url IS NULL AND :verification_source_url IS NOT NULL)
              )
            """,
            params,
        ),
    )


def _schedule_power(
    plan: Plan,
    catalog: dict[str, dict[str, Any]],
    modules: dict[tuple[str, str], dict[str, Any]],
    entry: dict[str, Any],
) -> None:
    brand = (entry.get("brand") or "").strip()
    name = (entry.get("name") or "").strip()
    if not brand or not name:
        _bump(plan.unmatched, "power_depth")
        return
    key = (brand, name)
    if key not in modules:
        catalog_row = None
        slug = entry.get("catalog_slug")
        if slug and slug in catalog and catalog[slug]["brand"] == brand and catalog[slug]["name"] == name:
            catalog_row = catalog[slug]
        else:
            slug = create_slug(brand, name)
            if slug in catalog and catalog[slug]["brand"] == brand and catalog[slug]["name"] == name:
                catalog_row = catalog[slug]
        if catalog_row is None or catalog_row.get("hp") is None:
            _bump(plan.unmatched, "power_depth")
            return
        _schedule_module(
            plan,
            modules,
            {
                "brand": brand,
                "name": name,
                "hp": int(catalog_row["hp"]),
                "module_type": catalog_row.get("category") or "UNKNOWN",
                "power_12v_ma": entry.get("power_12v_ma"),
                "power_neg12v_ma": entry.get("power_neg12v_ma"),
                "power_5v_ma": entry.get("power_5v_ma"),
                "depth_mm": entry.get("depth_mm"),
                "description": None,
                "manufacturer_url": None,
                "source": "SynthCatalogResearch",
                "source_reference": entry.get("source_url"),
                "io_ports": [],
                "tags": [],
                "verification_status": _entry_verification(entry)[0] or "unverified",
                "verification_source_url": _entry_verification(entry)[1],
            },
            kind="modules_power_targets",
        )
        return
    _schedule_fill(
        plan,
        modules[key],
        {
            "power_12v_ma": entry.get("power_12v_ma"),
            "power_neg12v_ma": entry.get("power_neg12v_ma"),
            "power_5v_ma": entry.get("power_5v_ma"),
            "depth_mm": entry.get("depth_mm"),
            "verification_status": _entry_verification(entry)[0],
            "verification_source_url": _entry_verification(entry)[1],
        },
        kind="power_depth_overlay",
    )


# Jumper-dependent power (spec 003 D8, research R5, task T034): one row per setting,
# read from the T035 receipt, which recorded each maker page's draws verbatim.
POWER_CONFIG_RECEIPT = CATALOG / "receipts" / "t035-jumper-power.json"
# Labels for settings the product page leaves unnamed, quoted from the maker's own manual.
POWER_CONFIG_LABELS = CATALOG / "receipts" / "t034-manual-labels.json"
POWER_CONFIG_RAILS = (("+12V", "power_12v_ma"), ("-12V", "power_neg12v_ma"), ("+5V", "power_5v_ma"))
RAIL_STATUSES = {"stated", "not_used", "not_stated"}


def power_setting_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:120]


def power_setting_problem(setting: dict[str, Any]) -> str | None:
    """Why a receipt setting cannot be loaded as it stands, or None.

    These are the T035 receipt's open questions for T034; the owner has not answered
    them, so nothing is guessed: an unlabelled setting (no neutral label is invented),
    a number the page gives without a unit, and a draw the page gives without a rail.
    """
    if not setting.get("label_on_page") or not (setting.get("label") or "").strip():
        return "label_not_on_page"
    if setting.get("unattributed_draw"):
        return "draw_without_rail"
    rails = setting.get("rails") or {}
    for rail, _ in POWER_CONFIG_RAILS:
        value = rails.get(rail) or {}
        status = value.get("status")
        if status not in RAIL_STATUSES:
            return "rail_status_unknown"
        if value.get("unit_stated") is False:
            return "unit_not_stated"
        ma = value.get("ma")
        if status == "stated" and (not isinstance(ma, int) or ma < 0 or not value.get("quote")):
            return "stated_rail_without_value"
        if status == "not_used" and ma not in (None, 0):
            return "not_used_rail_with_value"
        if status == "not_stated" and ma is not None:
            return "not_stated_rail_with_value"
    return None


def _power_config_state(conn: Connection | None) -> set[tuple[str, str, str]]:
    """(brand, name, setting_key) of every stored setting, read through its module row."""
    if conn is None:
        return set()
    rows = conn.execute(
        text(
            "SELECT m.brand, m.name, p.setting_key FROM power_configs p "
            "JOIN modules m ON m.id = p.module_id"
        )
    ).all()
    return {(row[0], row[1], row[2]) for row in rows}


def _schedule_power_configs(
    plan: Plan,
    modules: dict[tuple[str, str], dict[str, Any]],
    receipt: dict[str, Any],
    stored: set[tuple[str, str, str]],
    manual_labels: dict[str, Any] | None = None,
) -> None:
    """Insert each clean jumper setting from the T035 receipt as a ``power_configs`` row.

    Fill-only and idempotent: a setting already stored is counted, never rewritten, and
    nothing is deleted. Only pages the receipt marks jumper-dependent load; a page is
    matched to its module by brand and source URL. A setting the page leaves unlabelled
    takes a label only from ``manual_labels``, quoted from the maker's manual. The single draw columns are left as
    they are (D8: they stay unknown); a single value that differs from a stated setting
    value is reported as a conflict for review, not changed.
    """
    batch = str(receipt.get("receipt") or "t035-jumper-power")[:64]
    stats = plan.power_configs.setdefault(
        batch,
        {
            "jumper_pages": 0,
            "settings_seen": 0,
            "settings_loadable": 0,
            "already_stored": 0,
            "planned_inserts": 0,
            "pages_unmatched": 0,
            "pages_tombstoned": 0,
            "pages_ambiguous": 0,
            "pages_without_clean_setting": 0,
            "single_column_conflicts": 0,
            "skipped_by_reason": {},
            "skipped": [],
        },
    )
    for page in receipt.get("pages") or []:
        if not page.get("jumper_dependent"):
            continue
        stats["jumper_pages"] += 1
        brand = (page.get("brand") or "").strip()
        url = (page.get("url") or "").strip()
        page_name = (page.get("name") or "").strip()
        settings = _with_manual_labels(page, manual_labels)
        stats["settings_seen"] += len(settings)
        clean: list[dict[str, Any]] = []
        for index, setting in enumerate(settings):
            problem = power_setting_problem(setting)
            if problem:
                _bump(stats["skipped_by_reason"], problem)
                stats["skipped"].append(
                    {"brand": brand, "name": page_name, "setting": index, "label": setting.get("label"), "reason": problem}
                )
            else:
                clean.append(setting)
        if not clean:
            stats["pages_without_clean_setting"] += 1
            continue
        keys = [power_setting_key(setting["label"]) for setting in clean]
        if len(set(keys)) != len(keys):
            plan.conflict(table="power_configs", brand=brand, name=page_name, reason="duplicate_setting_label")
            continue
        matches = [
            state
            for (row_brand, _), state in modules.items()
            if row_brand == brand and url and (state.get("source_reference") or "") == url
        ]
        if not matches:
            stats["pages_unmatched"] += 1
            _bump(plan.unmatched, "power_configs")
            continue
        if len(matches) > 1 or matches[0].get("_duplicate"):
            stats["pages_ambiguous"] += 1
            plan.conflict(table="power_configs", brand=brand, url=url, reason="source_url_matches_several_modules")
            continue
        module = matches[0]
        if module.get("status") == "tombstoned":
            stats["pages_tombstoned"] += 1
            continue
        name = module["name"]
        stats["settings_loadable"] += len(clean)
        for setting, key in zip(clean, keys):
            rails = setting["rails"]
            values = {
                column: (rails[rail].get("ma") if rails[rail]["status"] != "not_stated" else None)
                for rail, column in POWER_CONFIG_RAILS
            }
            for rail, column in POWER_CONFIG_RAILS:
                single = module.get(column)
                if single is not None and rails[rail]["status"] == "stated" and int(single) != values[column]:
                    stats["single_column_conflicts"] += 1
                    plan.conflict(
                        table="modules", brand=brand, name=name, field=column,
                        setting=setting["label"], reason="single_draw_differs_from_setting",
                    )
            if (brand, name, key) in stored:
                stats["already_stored"] += 1
                continue
            stored.add((brand, name, key))
            stats["planned_inserts"] += 1
            plan.add_insert(
                "power_configs",
                Op(
                    "insert_power_config",
                    """
                    INSERT INTO power_configs (
                        module_id, brand, name, setting_key, label, kind, is_recommended,
                        power_12v_ma, power_neg12v_ma, power_5v_ma, unit_stated, rails,
                        source_url, quote, source_batch, content_sha256, fetched_at,
                        created_at, updated_at
                    )
                    SELECT m.id, m.brand, m.name, :setting_key, :label, :kind, :is_recommended,
                           :power_12v_ma, :power_neg12v_ma, :power_5v_ma, TRUE, CAST(:rails AS json),
                           :source_url, :quote, :source_batch, :content_sha256,
                           CAST(:fetched_at AS TIMESTAMP), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    FROM modules m
                    WHERE m.brand = :brand AND m.name = :name AND m.source_reference = :source_url
                      AND m.status <> 'tombstoned'
                      AND NOT EXISTS (
                        SELECT 1 FROM power_configs p
                        WHERE p.module_id = m.id AND p.setting_key = :setting_key
                      )
                    """,
                    {
                        "brand": brand,
                        "name": name,
                        "setting_key": key,
                        "label": setting["label"].strip()[:300],
                        "kind": (setting.get("kind") or "jumper")[:40],
                        # Only a page that marks a setting recommended sets this; none is inferred.
                        "is_recommended": "(recommended)" in setting["label"].lower(),
                        **values,
                        "rails": json.dumps(
                            {
                                rail: {
                                    "status": rails[rail]["status"],
                                    "ma": rails[rail].get("ma"),
                                    "qualifier": rails[rail].get("qualifier"),
                                    "quote": rails[rail].get("quote"),
                                }
                                for rail, _ in POWER_CONFIG_RAILS
                            },
                            sort_keys=True,
                        ),
                        "source_url": url,
                        "quote": _setting_quote(page, setting),
                        "source_batch": batch,
                        "content_sha256": page.get("content_sha256"),
                        "fetched_at": (page.get("fetched_at") or "").rstrip("Z") or None,
                    },
                ),
            )


def _with_manual_labels(page: dict[str, Any], manual_labels: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The page's settings, each unlabelled one named from a matching manual-label entry."""
    settings = list(page.get("settings") or [])
    for entry in (manual_labels or {}).get("labels") or []:
        index = entry.get("setting")
        if (
            entry.get("brand") != page.get("brand")
            or entry.get("page_url") != page.get("url")
            or not isinstance(index, int)
            or not 0 <= index < len(settings)
            or settings[index].get("label_on_page")
            or not str(entry.get("source_url") or "").startswith("https://")
            or not (entry.get("label") or "").strip()
            or not entry.get("quote")
        ):
            continue
        settings[index] = {**settings[index], "label": entry["label"], "label_on_page": True, "label_source": entry}
    return settings


def _setting_quote(page: dict[str, Any], setting: dict[str, Any]) -> str:
    source = setting.get("label_source")
    if not source:
        return page.get("quote") or ""
    return f"{page.get('quote') or ''}\n\nLabel from {source['source_url']}: {source['quote']}"


def render_plan(plan: Plan) -> str:
    lines = [
        "-- Idempotent catalog population.",
        "-- Re-running inserts missing rows and fills null specs only.",
        "-- Cases are applied by integrations.case_catalog_populator (no DELETE).",
        "",
    ]
    for op in plan.ops:
        lines.append(op.rendered().strip() + ";")
        lines.append("")
    sql = "\n".join(lines)
    assert_safe_sql(sql)
    return sql


def apply_plan(conn: Connection, plan: Plan) -> None:
    for op in plan.ops:
        conn.execute(text(op.sql), op.params)


def plan_cases(engine: Engine) -> dict[str, Any]:
    """Plan the case import with a rolled-back run: the valid records and, for each,
    whether it would insert, fill nulls or leave the row alone."""
    import sys

    backend = ROOT / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from integrations.case_catalog_populator import import_records, validate_record

    payload = _load(ROOT / "data" / "cases" / "seed-v1.json")
    records = payload["cases"]
    from sqlalchemy.orm import sessionmaker

    valid = []
    rejected = 0
    warnings: list[str] = []
    for index, record in enumerate(records):
        errors = validate_record(record, index)
        if errors:
            rejected += 1
            warnings.extend(errors[:2])
            continue
        valid.append(record)
    session = sessionmaker(bind=engine)()
    try:
        planned = import_records(session, valid, dry_run=True)
    finally:
        session.close()
    return {
        "input_records": len(records),
        "valid": valid,
        "actions": planned.get("actions", []),
        "inserts": planned.get("inserted", 0),
        "updates": planned.get("updated", 0),
        "unchanged": planned.get("unchanged", 0),
        "rejected": rejected,
        "warnings": warnings[:20],
    }


def case_receipt(engine: Engine, case_plan: dict[str, Any], *, apply: bool) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        key: case_plan[key]
        for key in ("input_records", "inserts", "updates", "unchanged", "rejected", "warnings")
    }
    if apply:
        from integrations.case_catalog_populator import import_records
        from sqlalchemy.orm import sessionmaker

        session = sessionmaker(bind=engine)()
        try:
            applied = import_records(session, case_plan["valid"], dry_run=False)
        finally:
            session.close()
        receipt["applied"] = {
            "inserted": applied.get("inserted"),
            "updated": applied.get("updated"),
            "rejected": applied.get("rejected"),
            "status": applied.get("status"),
        }
    return receipt


def provenance_counts(conn: Connection) -> dict[str, int]:
    """Read-only counts for the receipt (no values)."""
    queries = {
        "archive_rows": "SELECT COUNT(*) FROM catalog_value_archive",
        "modules_needs_reverify": "SELECT COUNT(*) FROM modules WHERE needs_reverify",
        "module_catalog_needs_reverify": "SELECT COUNT(*) FROM module_catalog WHERE needs_reverify",
        "modules_verified": "SELECT COUNT(*) FROM modules WHERE verification_status = 'verified'",
        "modules_legacy_source_modulargrid": "SELECT COUNT(*) FROM modules WHERE source = 'ModularGrid'",
        "module_catalog_with_modulargrid_url": "SELECT COUNT(*) FROM module_catalog WHERE modulargrid_url IS NOT NULL",
    }
    return {key: int(conn.execute(text(sql)).scalar_one()) for key, sql in queries.items()}


# Parameters that hold the time of planning, not what is written.
_CLOCK_PARAMS = frozenset({"created_at", "updated_at", "tombstoned_at"})


def plan_hash(plan: Plan, case_plan: dict[str, Any] | None = None) -> str:
    """The identity of a plan: SHA-256 over every statement and its parameters, with
    the planning clock left out, and over the case records and what each would write.
    An apply that names this hash applies exactly the writes the operator reviewed
    (spec 003 FR-020)."""
    digest = hashlib.sha256()
    for op in plan.ops:
        params = {k: ("<clock>" if k in _CLOCK_PARAMS else v) for k, v in op.params.items()}
        digest.update(op.sql.encode("utf-8"))
        digest.update(json.dumps(params, sort_keys=True, default=str).encode("utf-8"))
    if case_plan is not None:
        digest.update(b"cases")
        digest.update(json.dumps(case_plan["valid"], sort_keys=True, default=str).encode("utf-8"))
        digest.update(json.dumps(case_plan["actions"], sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def inputs_hash() -> str:
    """SHA-256 over every catalog input the plan reads: seeds, overlays, provenance."""
    digest = hashlib.sha256()
    files = sorted(
        [*CATALOG.glob("seed-*.json"), *(CATALOG / "overlays").glob("*.json"),
         *(CATALOG / "provenance").glob("*.json"), POWER_CONFIG_RECEIPT,
         ROOT / "data" / "cases" / "seed-v1.json"]
    )
    for path in files:
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def receipt_for(plan: Plan, *, database_url: str, apply: bool, cases: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "apply" if apply else "dry-run",
        "database": safe_target(database_url),
        "inserts": plan.inserts,
        "updates": plan.updates,
        "conflicts_total": plan.conflicts_total,
        "conflicts": plan.conflicts,
        "unmatched": plan.unmatched,
        "verification_on_planned_modules": plan.verification,
        "provenance": plan.provenance,
        "power_configs": plan.power_configs,
        "cases": cases,
        "destructive_sql": False,
    }


def table_counts(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url)
    counts: dict[str, int] = {}
    try:
        with engine.connect() as conn:
            for table in AFFECTED_TABLES:
                if not re.fullmatch(r"[a-z_]+", table):
                    raise SystemExit("refusing table name")
                counts[table] = int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())
    except SQLAlchemyError as exc:
        raise SystemExit(f"count query failed ({exc.__class__.__name__})") from None
    finally:
        engine.dispose()
    return counts


def assert_at_head(database_url: str) -> str:
    """Exit if the database revision is not this checkout's alembic head."""
    import sys

    backend = ROOT / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    head = ScriptDirectory.from_config(cfg).get_current_head()
    engine = create_engine(database_url)
    try:
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
    except SQLAlchemyError as exc:
        raise SystemExit(f"revision check failed ({exc.__class__.__name__})") from None
    finally:
        engine.dispose()
    if current != head:
        raise SystemExit(
            f"database revision {current or 'none'} is not alembic head {head}; "
            "run .github/workflows/db-migrate.yml on this ref first"
        )
    return head or ""


def dump_affected_tables(database_url: str, output: Path) -> None:
    parsed = urlparse(database_url)
    if not parsed.hostname or not parsed.path:
        raise SystemExit("database URL is missing a host or database name")
    password = parsed.password or ""
    env = os.environ.copy()
    env.pop("DATABASE_URL", None)
    env["PGHOST"] = parsed.hostname
    env["PGPORT"] = str(parsed.port or 5432)
    env["PGUSER"] = parsed.username or ""
    env["PGPASSWORD"] = password
    env["PGDATABASE"] = parsed.path.lstrip("/").split("?", 1)[0]
    query = parse_qs(parsed.query)
    if "sslmode" in query:
        env["PGSSLMODE"] = query["sslmode"][0]
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ["pg_dump", "--no-owner", "--no-privileges", "-Fc", "-f", str(output)]
    for table in AFFECTED_TABLES:
        command.extend(["-t", table])
    try:
        completed = subprocess.run(command, env=env, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        raise SystemExit("pg_dump is not installed") from None
    if completed.returncode != 0:
        detail = (completed.stderr or "").replace(password, "[redacted]") if password else completed.stderr
        detail = re.sub(r"://[^@\s]+@", "://[redacted]@", detail or "")
        raise SystemExit(f"pg_dump failed ({completed.returncode}): {detail[:500]}")
    if not output.is_file() or output.stat().st_size == 0:
        raise SystemExit("pg_dump wrote an empty file")


def populate(
    database_url: str,
    *,
    apply: bool = False,
    allow_nonlocal: bool = False,
    receipt_path: Path | None = None,
    sql_path: Path | None = None,
    verification_path: Path | None = None,
    expected_plan_hash: str | None = None,
    require_plan_hash: bool = False,
) -> dict[str, Any]:
    """Plan, and with ``apply`` write, the catalog load.

    With ``require_plan_hash`` (the Actions load), an apply must name the
    ``plan_hash`` of a dry run the operator reviewed; if the plan has changed since,
    nothing is written (spec 003 FR-020).
    """
    assert_local_database(database_url, allow_nonlocal)
    run_id = os.environ.get("GITHUB_RUN_ID") or uuid.uuid4().hex
    started_at = _stamp()
    engine = create_engine(database_url)
    try:
        try:
            with engine.connect() as conn:
                plan = build_plan(conn, verification_path=verification_path)
                counts_before = provenance_counts(conn)
        except ProgrammingError:
            raise SystemExit(
                "schema is missing importer columns; run alembic upgrade head (db-migrate.yml) first"
            ) from None
        sql = render_plan(plan)
        case_plan = plan_cases(engine)
        current_hash = plan_hash(plan, case_plan)
        if apply and require_plan_hash and expected_plan_hash != current_hash:
            raise SystemExit(
                "refusing to apply: the plan differs from the reviewed dry run "
                f"(expected {expected_plan_hash or 'none'}, planned {current_hash}). "
                "Run a dry run, review it, and apply with its plan_hash."
            )
        cases = case_receipt(engine, case_plan, apply=apply)
        if apply:
            with engine.begin() as conn:
                apply_plan(conn, plan)
        receipt = receipt_for(plan, database_url=database_url, apply=apply, cases=cases)
        receipt["run_id"] = run_id
        receipt["started_at"] = started_at
        receipt["plan_hash"] = current_hash
        receipt["inputs_hash"] = inputs_hash()
        receipt["provenance_counts_before"] = counts_before
        if apply:
            with engine.connect() as conn:
                receipt["provenance_counts_after"] = provenance_counts(conn)
    except SQLAlchemyError as exc:
        raise SystemExit(f"database operation failed ({exc.__class__.__name__})") from None
    finally:
        engine.dispose()
    receipt["finished_at"] = _stamp()
    if receipt_path:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if sql_path:
        sql_path.parent.mkdir(parents=True, exist_ok=True)
        sql_path.write_text(sql, encoding="utf-8")
    return receipt
