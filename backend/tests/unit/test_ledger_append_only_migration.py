"""Spec 004 T042: the canonical credit ledger is append-only on Postgres (FR-008, research R2)."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND / "alembic" / "versions" / "20261029_ledger_append_only.py"


def _load():
    spec = importlib.util.spec_from_file_location("ledger_append_only", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self, dialect: str) -> None:
        self.statements: list[str] = []
        self._bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect))

    def get_bind(self):
        return self._bind

    def execute(self, sql: str) -> None:
        self.statements.append(" ".join(str(sql).split()))


def _run(direction: str, dialect: str, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    module = _load()
    fake = _FakeOp(dialect)
    monkeypatch.setattr(module, "op", fake)
    getattr(module, direction)()
    return fake.statements


def test_the_migration_extends_the_single_head() -> None:
    module = _load()
    assert module.revision == "20261029_ledger_append_only"
    assert module.down_revision == "20261028_catalog_tombstones"
    # alembic_version.version_num is VARCHAR(32).
    assert len(module.revision) <= 32
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1
    # Later migrations may extend the head; this revision must stay on its single line.
    assert module.revision in {rev.revision for rev in script.iterate_revisions(heads[0], "base")}


def test_postgres_upgrade_rejects_update_and_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    statements = _run("upgrade", "postgresql", monkeypatch)
    assert len(statements) == 3
    function, on_update, on_delete = statements
    assert "CREATE OR REPLACE FUNCTION patchhive_deny_canonical_credit_ledger_mutation()" in function
    assert "RAISE EXCEPTION 'canonical_credit_ledger is append-only'" in function
    assert re.search(
        r"CREATE TRIGGER trg_canonical_credit_ledger_no_update BEFORE UPDATE ON "
        r"canonical_credit_ledger FOR EACH ROW EXECUTE FUNCTION "
        r"patchhive_deny_canonical_credit_ledger_mutation\(\)",
        on_update,
    )
    assert re.search(
        r"CREATE TRIGGER trg_canonical_credit_ledger_no_delete BEFORE DELETE ON "
        r"canonical_credit_ledger FOR EACH ROW EXECUTE FUNCTION "
        r"patchhive_deny_canonical_credit_ledger_mutation\(\)",
        on_delete,
    )


def test_postgres_downgrade_drops_the_triggers_and_function(monkeypatch: pytest.MonkeyPatch) -> None:
    statements = _run("downgrade", "postgresql", monkeypatch)
    assert statements == [
        "DROP TRIGGER IF EXISTS trg_canonical_credit_ledger_no_delete ON canonical_credit_ledger",
        "DROP TRIGGER IF EXISTS trg_canonical_credit_ledger_no_update ON canonical_credit_ledger",
        "DROP FUNCTION IF EXISTS patchhive_deny_canonical_credit_ledger_mutation()",
    ]


@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_sqlite_is_a_no_op(direction: str, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run(direction, "sqlite", monkeypatch) == []
