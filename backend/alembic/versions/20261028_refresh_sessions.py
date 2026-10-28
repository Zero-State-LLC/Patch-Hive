"""Refresh-token sessions and a per-user token version.

Revision ID: 20261028_refresh_sessions
Revises: 20261028_p1_security
Create Date: 2026-10-28

Access tokens become short-lived and live in memory in the SPA; sessions are renewed
with rotating refresh tokens kept in an HttpOnly cookie (community/sessions.py).
``users.token_version`` is carried in every access token so that signing out
everywhere, or a role change, revokes outstanding tokens. Additive only.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20261028_refresh_sessions"
down_revision = "20261028_p1_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    insp = inspect(op.get_bind())
    if "token_version" not in {c["name"] for c in insp.get_columns("users")}:
        op.add_column(
            "users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0")
        )
    if "refresh_tokens" not in insp.get_table_names():
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("family_id", sa.String(64), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("replaced_by", sa.String(64), nullable=True),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
        op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    insp = inspect(op.get_bind())
    if "refresh_tokens" in insp.get_table_names():
        op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
        op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
        op.drop_table("refresh_tokens")
    if "token_version" in {c["name"] for c in insp.get_columns("users")}:
        op.drop_column("users", "token_version")
