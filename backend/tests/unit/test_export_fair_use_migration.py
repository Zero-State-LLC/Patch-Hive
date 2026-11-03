"""Spec 004 T050: the export fair-use migration is the single Alembic head, matches the
model, and its downgrade refuses while an export points at a STUDIO grant. Postgres round
trip: tests/acceptance/test_studio_fair_use_postgres.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from canon.models import EXPORT_GRANT_SHAPE, CanonicalExportRecord

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND / "alembic" / "versions" / "20261102_export_fair_use.py"


def _load():
    spec = importlib.util.spec_from_file_location("export_fair_use_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _normal(text: str) -> str:
    return " ".join(text.split())


def test_the_migration_revises_subscriptions_on_the_single_head() -> None:
    module = _load()
    assert module.revision == "20261102_export_fair_use"
    assert module.down_revision == "20261102_subscriptions"
    # alembic_version.version_num is VARCHAR(32).
    assert len(module.revision) <= 32
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1
    assert module.revision in {rev.revision for rev in script.iterate_revisions(heads[0], "base")}


def test_the_model_and_the_migration_agree() -> None:
    module = _load()
    table = CanonicalExportRecord.__table__
    (shape,) = [c for c in table.constraints if c.name == "ck_canonical_exports_grant_shape"]
    assert _normal(str(shape.sqltext)) == _normal(module._GRANT_SHAPE)
    assert _normal(EXPORT_GRANT_SHAPE) == _normal(module._GRANT_SHAPE)
    column = table.c.subscription_grant_id
    assert column.nullable
    (fk,) = column.foreign_keys
    assert fk.target_fullname == "subscription_period_grants.id"
    assert fk.ondelete == "RESTRICT"


def _run(module, direction: str, engine: sa.Engine) -> None:
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            getattr(module, direction)()


def test_upgrade_and_downgrade_on_a_minimal_schema(tmp_path: Path) -> None:
    module = _load()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE subscription_period_grants (id VARCHAR(64) PRIMARY KEY)"))
        conn.execute(
            sa.text(
                "CREATE TABLE canonical_exports (id VARCHAR(64) PRIMARY KEY, "
                "credit_cost INTEGER NOT NULL, ledger_entry_id VARCHAR(64))"
            )
        )
        conn.execute(sa.text("INSERT INTO subscription_period_grants (id) VALUES ('g1')"))
        conn.execute(
            sa.text("INSERT INTO canonical_exports (id, credit_cost) VALUES ('paid', 3)")
        )

    _run(module, "upgrade", engine)
    columns = {c["name"] for c in sa.inspect(engine).get_columns("canonical_exports")}
    assert "subscription_grant_id" in columns

    with engine.begin() as conn:
        with pytest.raises(sa.exc.IntegrityError):
            with conn.begin_nested():
                conn.execute(
                    sa.text(
                        "INSERT INTO canonical_exports (id, credit_cost, subscription_grant_id) "
                        "VALUES ('bad', 3, 'g1')"
                    )
                )
        conn.execute(
            sa.text(
                "INSERT INTO canonical_exports (id, credit_cost, subscription_grant_id) "
                "VALUES ('studio', 0, 'g1')"
            )
        )
    with pytest.raises(RuntimeError, match="refusing to downgrade"):
        _run(module, "downgrade", engine)
    with engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM canonical_exports WHERE id = 'studio'"))

    _run(module, "downgrade", engine)
    columns = {c["name"] for c in sa.inspect(engine).get_columns("canonical_exports")}
    assert "subscription_grant_id" not in columns
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT id FROM canonical_exports")).scalars().all() == [
            "paid"
        ]
