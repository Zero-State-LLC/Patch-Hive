"""Make the canonical credit ledger append-only.

Revision ID: 20261029_ledger_append_only
Revises: 20261028_catalog_tombstones
Create Date: 2026-10-29

Spec 004 FR-008, research R2: ``canonical_credit_ledger`` rows are never updated or
deleted; a correction is a new row (``reversal``). Postgres triggers reject ``UPDATE``
and ``DELETE``, mirroring ``20260925_decision_receipts``. SQLite test environments keep
the convention. No data change.
"""

from __future__ import annotations

from alembic import op

revision = "20261029_ledger_append_only"
down_revision = "20261028_catalog_tombstones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Database-level append-only enforcement. SQLite test environments rely on the convention.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION patchhive_deny_canonical_credit_ledger_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'canonical_credit_ledger is append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_canonical_credit_ledger_no_update
            BEFORE UPDATE ON canonical_credit_ledger
            FOR EACH ROW EXECUTE FUNCTION patchhive_deny_canonical_credit_ledger_mutation();
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_canonical_credit_ledger_no_delete
            BEFORE DELETE ON canonical_credit_ledger
            FOR EACH ROW EXECUTE FUNCTION patchhive_deny_canonical_credit_ledger_mutation();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "DROP TRIGGER IF EXISTS trg_canonical_credit_ledger_no_delete ON canonical_credit_ledger"
        )
        op.execute(
            "DROP TRIGGER IF EXISTS trg_canonical_credit_ledger_no_update ON canonical_credit_ledger"
        )
        op.execute("DROP FUNCTION IF EXISTS patchhive_deny_canonical_credit_ledger_mutation()")
