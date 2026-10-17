"""Idempotent catalog population for an empty or partial database.

Dry-run is the default. Statements insert missing rows and fill null specs.
They do not delete, drop, or overwrite a non-null spec or a settled verification.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
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
    "manufacturers",
    "module_catalog",
    "modules",
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

    def add_insert(self, kind: str, op: Op) -> None:
        self.ops.append(op)
        self.inserts[kind] = self.inserts.get(kind, 0) + 1

    def add_update(self, kind: str, op: Op) -> None:
        self.ops.append(op)
        self.updates[kind] = self.updates.get(kind, 0) + 1

    def conflict(self, **info: Any) -> None:
        if len(self.conflicts) < 50:
            self.conflicts.append(info)


def _bump(counter: dict[str, int], key: str, amount: int = 1) -> None:
    counter[key] = counter.get(key, 0) + amount


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


POWER_OVERLAY_LATEST = 8
ENTRY_VERIFICATION = {"verified", "corrected", "flagged"}


def _entry_verification(entry: dict[str, Any]) -> tuple[str | None, str | None]:
    status = entry.get("verification_status")
    if status not in ENTRY_VERIFICATION:
        return None, None
    return status, entry.get("verification_source_url") or entry.get("source_url")


def build_plan(conn: Connection, *, verification_path: Path | None = None) -> Plan:
    plan = Plan()
    phase2 = _load(CATALOG / "seed-phase2-v1.json")
    phase3 = _load(CATALOG / "seed-phase3-v1.json")
    candidates = _load(CATALOG / "overlays" / "catalog-new-brand-candidates-v1.json")
    verification = _verification_index(verification_path)
    catalog = _catalog_state(conn)
    modules = _module_state(conn)
    manufacturers = _manufacturer_state(conn)

    for brand in phase2.get("brands") or []:
        _schedule_manufacturer(plan, manufacturers, brand)

    for row in list(phase2.get("catalog_modules") or []) + list(phase3.get("catalog_modules") or []):
        _schedule_catalog(plan, catalog, row, modulargrid_url=row.get("modulargrid_url"))

    additions = CATALOG / "overlays" / "catalog-additions-v1.json"
    if additions.is_file():
        for row in _load(additions).get("rows") or []:
            _schedule_catalog(plan, catalog, row, modulargrid_url=None)

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

    hp_overlay = _load(CATALOG / "overlays" / "module-catalog-hp-v1.json")
    for entry in hp_overlay.get("entries") or []:
        _schedule_hp(plan, catalog, entry)

    for row in candidates.get("rows") or []:
        _schedule_candidate(plan, catalog, modules, row, verification)

    overlays = [
        _load(CATALOG / "overlays" / f"module-power-depth-v{version}.json")
        for version in range(1, POWER_OVERLAY_LATEST + 1)
    ]
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

    for row in modules.values():
        if row.get("_planned"):
            _bump(plan.verification, row.get("verification_status") or "unverified")
    return plan


def _verification_index(path: Path | None) -> dict[str, dict[str, Any]]:
    file_path = path or (CATALOG / "hermes-research" / "batch8-brand-verification.json")
    if not file_path.is_file():
        return {}
    payload = _load(file_path)
    rows = payload.get("rows") or payload.get("brand_verification", {}).get("rows") or []
    return {row.get("source_url"): row for row in rows if row.get("source_url")}


def _catalog_state(conn: Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(text("SELECT slug, brand, name, hp, category FROM module_catalog")).mappings()
    return {
        row["slug"]: {
            "brand": row["brand"],
            "name": row["name"],
            "hp": row["hp"],
            "category": row["category"],
            "_planned": False,
        }
        for row in rows
    }


def _module_state(conn: Connection) -> dict[tuple[str, str], dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT brand, name, hp, power_12v_ma, power_neg12v_ma, power_5v_ma, depth_mm, "
            "verification_status, verification_source_url FROM modules"
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
                is_available, source, created_at, updated_at
            )
            SELECT :slug, :brand, :name, :hp, :category, :modulargrid_url, :manufacturer_url,
                   :is_available, :source, :created_at, :updated_at
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
                "is_available": row.get("is_available") or "available",
                "source": row.get("source") or "SynthCatalogResearch",
                "created_at": _stamp(),
                "updated_at": _stamp(),
            },
        ),
    )


def _schedule_hp(plan: Plan, catalog: dict[str, dict[str, Any]], entry: dict[str, Any]) -> None:
    slug = entry.get("slug")
    brand = (entry.get("brand") or "").strip()
    name = (entry.get("name") or "").strip()
    hp = entry.get("hp")
    if hp is None:
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


def _schedule_fill(plan: Plan, existing: dict[str, Any], incoming: dict[str, Any], *, kind: str) -> None:
    fill: dict[str, Any] = {}
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
        incoming_status
        and existing.get("verification_status") not in {None, "unverified", incoming_status}
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


def case_receipt(engine: Engine, *, apply: bool) -> dict[str, Any]:
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
    # Plan with a rolled-back import so the counts reflect real fill-null writes only.
    session = sessionmaker(bind=engine)()
    try:
        planned = import_records(session, valid, dry_run=True)
    finally:
        session.close()
    receipt: dict[str, Any] = {
        "input_records": len(records),
        "inserts": planned.get("inserted", 0),
        "updates": planned.get("updated", 0),
        "unchanged": planned.get("unchanged", 0),
        "rejected": rejected,
        "warnings": warnings[:20],
    }
    if apply:
        session = sessionmaker(bind=engine)()
        try:
            applied = import_records(session, records, dry_run=False)
        finally:
            session.close()
        receipt["applied"] = {
            "inserted": applied.get("inserted"),
            "updated": applied.get("updated"),
            "rejected": applied.get("rejected"),
            "status": applied.get("status"),
        }
    return receipt


def receipt_for(plan: Plan, *, database_url: str, apply: bool, cases: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "apply" if apply else "dry-run",
        "database": safe_target(database_url),
        "inserts": plan.inserts,
        "updates": plan.updates,
        "conflicts": plan.conflicts,
        "unmatched": plan.unmatched,
        "verification_on_planned_modules": plan.verification,
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
) -> dict[str, Any]:
    assert_local_database(database_url, allow_nonlocal)
    engine = create_engine(database_url)
    try:
        try:
            with engine.connect() as conn:
                plan = build_plan(conn, verification_path=verification_path)
        except ProgrammingError:
            raise SystemExit(
                "schema is missing importer columns; run alembic upgrade head (db-migrate.yml) first"
            ) from None
        sql = render_plan(plan)
        cases = case_receipt(engine, apply=apply)
        if apply:
            with engine.begin() as conn:
                apply_plan(conn, plan)
        receipt = receipt_for(plan, database_url=database_url, apply=apply, cases=cases)
    except SQLAlchemyError as exc:
        raise SystemExit(f"database operation failed ({exc.__class__.__name__})") from None
    finally:
        engine.dispose()
    if receipt_path:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if sql_path:
        sql_path.parent.mkdir(parents=True, exist_ok=True)
        sql_path.write_text(sql, encoding="utf-8")
    return receipt
