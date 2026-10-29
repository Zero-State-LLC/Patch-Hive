"""Spec 004 T045: stored webhook events get a reason code and no row stays ``received``."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND / "alembic" / "versions" / "20261029_webhook_disposition.py"


def _load():
    spec = importlib.util.spec_from_file_location("webhook_event_disposition", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeOp:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def add_column(self, table: str, column) -> None:
        self.calls.append(("add_column", table, column.name, column.nullable))

    def drop_column(self, table: str, column: str) -> None:
        self.calls.append(("drop_column", table, column))

    def execute(self, sql: str) -> None:
        self.calls.append(("execute", " ".join(str(sql).split())))


def _run(direction: str, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    module = _load()
    fake = _FakeOp()
    monkeypatch.setattr(module, "op", fake)
    getattr(module, direction)()
    return fake.calls


def test_the_migration_extends_the_single_head() -> None:
    module = _load()
    assert module.down_revision == "20261029_ledger_append_only"
    # alembic_version.version_num is VARCHAR(32).
    assert len(module.revision) <= 32
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1
    assert module.revision in {rev.revision for rev in script.iterate_revisions(heads[0], "base")}


def test_upgrade_adds_reason_code_and_resolves_stored_received_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_column, backfill = _run("upgrade", monkeypatch)
    assert add_column == ("add_column", "stripe_event_records", "reason_code", True)
    assert backfill == (
        "execute",
        "UPDATE stripe_event_records SET status = 'unresolved', "
        "reason_code = 'RECEIVED_BEFORE_PROCESSOR', processed_at = CURRENT_TIMESTAMP "
        "WHERE status = 'received'",
    )


def test_downgrade_drops_reason_code(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run("downgrade", monkeypatch) == [
        ("drop_column", "stripe_event_records", "reason_code")
    ]
