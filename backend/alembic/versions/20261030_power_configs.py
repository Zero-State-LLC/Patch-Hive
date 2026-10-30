"""Jumper-dependent power as one row per setting (spec 003 D8, T034).

Revision ID: 20261030_power_configs
Revises: 20261030_catalog_hp_source
Create Date: 2026-10-30

``power_configs`` holds one +12 V / -12 V / +5 V set per jumper setting of a module,
each with the maker page that states it and the page's power block verbatim. A rail
the page does not give a number for stays NULL, never 0. Rows hang off ``modules``,
the table rack budgets read. The catalog loader only inserts rows that are missing;
it never updates or deletes one.

``rack_modules.power_config_id`` lets a placement name the setting its module is
jumpered to; the rack budget then uses that setting's draws. NULL means not chosen.
Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261030_power_configs"
down_revision = "20261030_catalog_hp_source"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "power_configs" not in _tables():
        op.create_table(
            "power_configs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("module_id", sa.Integer, sa.ForeignKey("modules.id"), nullable=False),
            sa.Column("brand", sa.String(100), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("setting_key", sa.String(120), nullable=False),
            sa.Column("label", sa.String(300), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("is_recommended", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("power_12v_ma", sa.Integer, nullable=True),
            sa.Column("power_neg12v_ma", sa.Integer, nullable=True),
            sa.Column("power_5v_ma", sa.Integer, nullable=True),
            sa.Column("unit_stated", sa.Boolean, nullable=False),
            sa.Column("rails", sa.JSON, nullable=False),
            sa.Column("source_url", sa.String(500), nullable=False),
            sa.Column("quote", sa.Text, nullable=False),
            sa.Column("source_batch", sa.String(64), nullable=False),
            sa.Column("content_sha256", sa.String(64), nullable=True),
            sa.Column("fetched_at", sa.DateTime, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("module_id", "setting_key", name="uq_power_configs_module_setting"),
            sa.CheckConstraint(
                "(power_12v_ma IS NULL OR power_12v_ma >= 0) AND "
                "(power_neg12v_ma IS NULL OR power_neg12v_ma >= 0) AND "
                "(power_5v_ma IS NULL OR power_5v_ma >= 0)",
                name="ck_power_configs_rails_non_negative",
            ),
        )
        op.create_index("ix_power_configs_module_id", "power_configs", ["module_id"])
    if "power_config_id" not in _columns("rack_modules"):
        op.add_column(
            "rack_modules",
            sa.Column(
                "power_config_id",
                sa.Integer,
                sa.ForeignKey("power_configs.id", name="fk_rack_modules_power_config_id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    if "power_config_id" in _columns("rack_modules"):
        op.drop_constraint("fk_rack_modules_power_config_id", "rack_modules", type_="foreignkey")
        op.drop_column("rack_modules", "power_config_id")
    if "power_configs" in _tables():
        op.drop_index("ix_power_configs_module_id", table_name="power_configs")
        op.drop_table("power_configs")
