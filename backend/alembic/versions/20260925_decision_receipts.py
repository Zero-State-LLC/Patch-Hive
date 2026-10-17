"""Add append-only decision intelligence receipts.

Revision ID: 20260925_decision_receipts
Revises: 20260726_module_registry_slugs
"""

from alembic import op
import sqlalchemy as sa

revision = "20260925_decision_receipts"
down_revision = "20260726_module_registry_slugs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_receipts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("provider_version", sa.String(length=100), nullable=False),
        sa.Column("purpose", sa.String(length=100), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.Column("candidate_set_hash", sa.String(length=64), nullable=True),
        sa.Column("rubric_hash", sa.String(length=64), nullable=True),
        sa.Column("answer_type", sa.String(length=32), nullable=False),
        sa.Column("selected_choice", sa.String(length=255), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("probability_yes", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("provider_status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column("disposition", sa.String(length=32), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("packet_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_payload_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("packet_hash", name="uq_decision_receipts_packet_hash"),
    )
    op.create_index("ix_decision_receipts_request_id", "decision_receipts", ["request_id"])
    op.create_index("ix_decision_receipts_purpose", "decision_receipts", ["purpose"])
    op.create_index("ix_decision_receipts_evidence_hash", "decision_receipts", ["evidence_hash"])

    # Database-level append-only enforcement. SQLite test environments rely on ORM guards.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION patchhive_deny_decision_receipt_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'decision_receipts are append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_decision_receipts_no_update
            BEFORE UPDATE ON decision_receipts
            FOR EACH ROW EXECUTE FUNCTION patchhive_deny_decision_receipt_mutation();
            """
        )
        op.execute(
            """
            CREATE TRIGGER trg_decision_receipts_no_delete
            BEFORE DELETE ON decision_receipts
            FOR EACH ROW EXECUTE FUNCTION patchhive_deny_decision_receipt_mutation();
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_decision_receipts_no_delete ON decision_receipts")
        op.execute("DROP TRIGGER IF EXISTS trg_decision_receipts_no_update ON decision_receipts")
        op.execute("DROP FUNCTION IF EXISTS patchhive_deny_decision_receipt_mutation()")
    op.drop_index("ix_decision_receipts_evidence_hash", table_name="decision_receipts")
    op.drop_index("ix_decision_receipts_purpose", table_name="decision_receipts")
    op.drop_index("ix_decision_receipts_request_id", table_name="decision_receipts")
    op.drop_table("decision_receipts")
