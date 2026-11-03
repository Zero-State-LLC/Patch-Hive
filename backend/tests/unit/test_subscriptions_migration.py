"""Spec 004 T049: the subscriptions migration is the single Alembic head and matches
the models. Postgres round trip and the refusing downgrade:
tests/acceptance/test_subscription_postgres.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from canon.models import (
    SUBSCRIPTION_GRANT_SHAPE,
    SUBSCRIPTION_STATUSES,
    ProviderSubscriptionRecord,
    SubscriptionPeriodGrantRecord,
)

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND / "alembic" / "versions" / "20261102_subscriptions.py"


def _load():
    spec = importlib.util.spec_from_file_location("subscriptions_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _check(table: sa.Table, name: str) -> str:
    (constraint,) = [c for c in table.constraints if c.name == name]
    return " ".join(str(constraint.sqltext).split())


def _normal(text: str) -> str:
    return " ".join(text.split())


def test_the_migration_revises_purchase_refunds_and_is_the_single_head() -> None:
    module = _load()
    assert module.revision == "20261102_subscriptions"
    assert module.down_revision == "20261102_purchase_refunds"
    # alembic_version.version_num is VARCHAR(32).
    assert len(module.revision) <= 32
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert script.get_heads() == [module.revision]


def test_the_model_and_the_migration_agree_on_the_constraints() -> None:
    module = _load()
    subscriptions = ProviderSubscriptionRecord.__table__
    grants = SubscriptionPeriodGrantRecord.__table__
    assert _check(subscriptions, "ck_provider_subscriptions_status") == _normal(
        module._STATUS_CHECK
    )
    assert _check(subscriptions, "ck_provider_subscriptions_tier") == module._TIER_CHECK
    assert _check(grants, "ck_subscription_period_grants_shape") == _normal(module._GRANT_SHAPE)
    assert _normal(SUBSCRIPTION_GRANT_SHAPE) == _normal(module._GRANT_SHAPE)
    assert set(SUBSCRIPTION_STATUSES) == {
        "incomplete",
        "incomplete_expired",
        "trialing",
        "active",
        "past_due",
        "canceled",
        "unpaid",
        "paused",
    }


def _run(module, direction: str, engine: sa.Engine) -> None:
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            getattr(module, direction)()


def test_upgrade_and_downgrade_on_an_empty_schema(tmp_path: Path) -> None:
    """Upgrade creates both tables; downgrade drops them when empty and refuses with
    rows (SQLite, the migration alone over minimal parent tables)."""
    module = _load()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        conn.execute(sa.text("CREATE TABLE canonical_credit_ledger (id VARCHAR(64) PRIMARY KEY)"))
        conn.execute(sa.text("INSERT INTO users (id) VALUES (1)"))

    _run(module, "upgrade", engine)
    tables = set(sa.inspect(engine).get_table_names())
    assert {"provider_subscriptions", "subscription_period_grants"} <= tables

    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO provider_subscriptions (id, user_id, provider_subscription_id, "
                "provider_customer_id, price_id, tier, status, current_period_start, "
                "current_period_end, created_at, updated_at) VALUES ('sub-1', 1, 'sub_1', "
                "'cus_1', 'price_1', 'core', 'active', '2026-11-01', '2026-12-01', "
                "'2026-11-01', '2026-11-01')"
            )
        )
    with pytest.raises(RuntimeError, match="refusing to downgrade"):
        _run(module, "downgrade", engine)
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM provider_subscriptions"))

    _run(module, "downgrade", engine)
    tables = set(sa.inspect(engine).get_table_names())
    assert "provider_subscriptions" not in tables
    assert "subscription_period_grants" not in tables
