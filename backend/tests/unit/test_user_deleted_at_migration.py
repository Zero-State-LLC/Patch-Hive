"""Spec 004 OQ-12: the ``users.deleted_at`` migration stays on the single Alembic head."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND / "alembic" / "versions" / "20261101_user_deleted_at.py"


def test_the_migration_extends_the_single_head() -> None:
    spec = importlib.util.spec_from_file_location("user_deleted_at", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.revision == "20261101_user_deleted_at"
    assert module.down_revision == "20261030_power_configs"
    # alembic_version.version_num is VARCHAR(32).
    assert len(module.revision) <= 32
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert len(heads) == 1
    assert module.revision in {rev.revision for rev in script.iterate_revisions(heads[0], "base")}
