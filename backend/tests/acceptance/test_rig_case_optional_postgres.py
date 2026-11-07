"""Spec 009 T020 on Postgres: a Rig's Case is optional, and the downgrade refuses while any
Rig has none, on the real schema."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from racks.models import Rack

BEFORE = "20261106_commerce_append_only"


def _alembic(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _case_optional(engine: Engine) -> bool:
    with engine.connect() as conn:
        answer = conn.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name = 'racks' AND column_name = 'case_id'"
            )
        ).scalar()
    return answer == "YES"


def test_the_migration_round_trips_empty_and_refuses_while_a_rig_has_no_case(
    migrated_db: sessionmaker, db_session: Session, database_url: str, create_user
) -> None:
    config = _alembic(database_url)
    engine = migrated_db.kw["bind"]
    # The per-test truncation empties alembic_version too; the schema is at head.
    command.stamp(config, "head")
    assert _case_optional(engine)

    command.downgrade(config, BEFORE)
    try:
        assert not _case_optional(engine)
    finally:
        command.upgrade(config, "head")
    assert _case_optional(engine)

    owner = create_user("pg-photo-owner", "pg-pass")
    db_session.add(Rack(user_id=owner.id, case_id=None, name="From a photo", tags=[]))
    db_session.commit()
    db_session.close()

    with pytest.raises(RuntimeError, match="have no Case"):
        command.downgrade(config, BEFORE)

    assert _case_optional(engine)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "20261107_rig_case_optional"
