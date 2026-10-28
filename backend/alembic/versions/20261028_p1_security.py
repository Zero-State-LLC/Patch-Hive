"""P1 security hardening: sign-in lockout, per-user export idempotency, one referral reward.

Revision ID: 20261028_p1_security
Revises: 20261028_run_validation_report
Create Date: 2026-10-28

- ``users.failed_login_count`` / ``users.locked_until`` for the per-account sign-in lock.
- ``canonical_exports.idempotency_key`` was unique on its own, so one user's key could
  return another user's export. It becomes unique per ``(user_id, idempotency_key)``.
- ``referrals``: a partial unique index allows at most one ``Rewarded`` row per
  referred user, so concurrent first purchases cannot both pay a reward.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261028_p1_security"
down_revision = "20261028_run_validation_report"
branch_labels = None
depends_on = None

EXPORT_UNIQUE = "uq_canonical_exports_user_idempotency"
REWARD_INDEX = "uq_referrals_one_reward"


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _key_only_unique(table: str) -> list[tuple[str, str]]:
    """Unique constraints and indexes on (idempotency_key) alone: (kind, name)."""
    insp = inspect(op.get_bind())
    found = [
        ("constraint", u["name"])
        for u in insp.get_unique_constraints(table)
        if u.get("column_names") == ["idempotency_key"] and u.get("name")
    ]
    # Postgres also reports a unique constraint's backing index; drop it only once.
    constraint_names = {name for _, name in found}
    found += [
        ("index", i["name"])
        for i in insp.get_indexes(table)
        if i.get("unique")
        and i.get("column_names") == ["idempotency_key"]
        and i.get("name")
        and i["name"] not in constraint_names
        and not i.get("duplicates_constraint")
    ]
    return found


def upgrade() -> None:
    users = _columns("users")
    if "failed_login_count" not in users:
        op.add_column(
            "users",
            sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if "locked_until" not in users:
        op.add_column("users", sa.Column("locked_until", sa.DateTime(), nullable=True))

    with op.batch_alter_table("canonical_exports") as batch:
        for kind, name in _key_only_unique("canonical_exports"):
            if kind == "constraint":
                batch.drop_constraint(name, type_="unique")
            else:
                batch.drop_index(name)
        batch.create_unique_constraint(EXPORT_UNIQUE, ["user_id", "idempotency_key"])

    existing = {i["name"] for i in inspect(op.get_bind()).get_indexes("referrals")}
    if REWARD_INDEX not in existing:
        op.create_index(
            REWARD_INDEX,
            "referrals",
            ["referred_user_id"],
            unique=True,
            postgresql_where=sa.text("status = 'Rewarded'"),
            sqlite_where=sa.text("status = 'Rewarded'"),
        )


def downgrade() -> None:
    existing = {i["name"] for i in inspect(op.get_bind()).get_indexes("referrals")}
    if REWARD_INDEX in existing:
        op.drop_index(REWARD_INDEX, table_name="referrals")
    with op.batch_alter_table("canonical_exports") as batch:
        batch.drop_constraint(EXPORT_UNIQUE, type_="unique")
        batch.create_unique_constraint(
            "canonical_exports_idempotency_key_key", ["idempotency_key"]
        )
    users = _columns("users")
    if "locked_until" in users:
        op.drop_column("users", "locked_until")
    if "failed_login_count" in users:
        op.drop_column("users", "failed_login_count")
