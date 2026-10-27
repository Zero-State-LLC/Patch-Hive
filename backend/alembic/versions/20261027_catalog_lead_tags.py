"""Tag ModularGrid-derived catalog rows as discovery leads.

Revision ID: 20261027_catalog_lead_tags
Revises: 20261017_catalog_value_archive
Create Date: 2026-10-27

Spec 003 D1 / FR-033. Adds ``access_basis`` and ``evidence_status`` to
``module_catalog`` and marks the ModularGrid-derived rows (the Phase 2 seed slugs and
rows admitted with source ModularGrid / ModularGridCSV) as
``access_basis = unknown`` / ``evidence_status = CATALOG_OBSERVED``. Additive only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261027_catalog_lead_tags"
down_revision = "20261017_catalog_value_archive"
branch_labels = None
depends_on = None

SEED = Path(__file__).resolve().parents[2] / "data" / "synth-catalog" / "seed-phase2-v1.json"
LEAD_SOURCES = ("ModularGrid", "ModularGridCSV")


def _columns(table: str) -> set[str]:
    if table not in set(inspect(op.get_bind()).get_table_names()):
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _slug(brand: str, name: str) -> str:
    # Same rule as ModuleCatalog.create_slug.
    return re.sub(r"[^a-z0-9]+", "-", f"{brand}-{name}".lower()).strip("-")


def _seed_slugs() -> list[str]:
    if not SEED.exists():
        raise RuntimeError(f"Phase 2 seed not found at {SEED}; cannot tag ModularGrid leads")
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    return sorted(
        {
            _slug(str(row["brand"]).strip(), str(row["name"]).strip())
            for row in seed.get("catalog_modules") or []
            if row.get("brand") and row.get("name")
        }
    )


def upgrade() -> None:
    columns = _columns("module_catalog")
    if not columns:
        return
    if "access_basis" not in columns:
        op.add_column("module_catalog", sa.Column("access_basis", sa.String(40), nullable=True))
        op.create_index("ix_module_catalog_access_basis", "module_catalog", ["access_basis"])
    if "evidence_status" not in columns:
        op.add_column("module_catalog", sa.Column("evidence_status", sa.String(40), nullable=True))

    tag = sa.text(
        "UPDATE module_catalog SET access_basis = 'unknown', evidence_status = 'CATALOG_OBSERVED' "
        "WHERE access_basis IS NULL AND (source IN :sources OR slug IN :slugs)"
    ).bindparams(sa.bindparam("sources", expanding=True), sa.bindparam("slugs", expanding=True))
    slugs = _seed_slugs()
    bind = op.get_bind()
    for start in range(0, len(slugs), 200):
        bind.execute(tag, {"sources": list(LEAD_SOURCES), "slugs": slugs[start : start + 200]})


def downgrade() -> None:
    columns = _columns("module_catalog")
    if "evidence_status" in columns:
        op.drop_column("module_catalog", "evidence_status")
    if "access_basis" in columns:
        op.drop_index("ix_module_catalog_access_basis", table_name="module_catalog")
        op.drop_column("module_catalog", "access_basis")
