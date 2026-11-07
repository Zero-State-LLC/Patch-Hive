"""Make the other credit and referral tables append-only, and referral codes immutable.

Revision ID: 20261106_commerce_append_only
Revises: 20261106_catalog_load_runs
Create Date: 2026-11-06

Spec 004 FR-008, FR-021, FR-029, T001 D5 and D6. ``canonical_credit_ledger`` has had these
triggers since ``20261029_ledger_append_only``; the tables below relied on convention.

A referral code can change only while it's empty, or in the one update that deletes the
account (``account/deletion.py``), because a deleted account's old code must stop resolving
(OQ-12). SQLite test environments keep the convention. No data change.
"""

from __future__ import annotations

from alembic import op

revision = "20261106_commerce_append_only"
down_revision = "20261106_catalog_load_runs"
branch_labels = None
depends_on = None

APPEND_ONLY_TABLES = (
    "credits_ledger",
    "credit_ledger_entries",
    "referrals",
    "subscription_period_grants",
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION patchhive_deny_commerce_row_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    for table in APPEND_ONLY_TABLES:
        for verb in ("UPDATE", "DELETE"):
            op.execute(
                f"""
                CREATE TRIGGER trg_{table}_no_{verb.lower()}
                BEFORE {verb} ON {table}
                FOR EACH ROW EXECUTE FUNCTION patchhive_deny_commerce_row_mutation();
                """
            )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION patchhive_keep_referral_code()
        RETURNS trigger AS $$
        BEGIN
            IF COALESCE(OLD.referral_code, '') <> ''
               AND NEW.referral_code IS DISTINCT FROM OLD.referral_code
               AND NOT (OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL) THEN
                RAISE EXCEPTION 'users.referral_code is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_users_keep_referral_code
        BEFORE UPDATE OF referral_code ON users
        FOR EACH ROW EXECUTE FUNCTION patchhive_keep_referral_code();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS trg_users_keep_referral_code ON users")
    op.execute("DROP FUNCTION IF EXISTS patchhive_keep_referral_code()")
    for table in APPEND_ONLY_TABLES:
        for verb in ("update", "delete"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_no_{verb} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS patchhive_deny_commerce_row_mutation()")
