"""Spec 009 T021 on Postgres: the Readings migration round-trips empty and refuses to
downgrade while a Reading exists, on the real schema."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from canon.models import ImageAssetRecord, PhotoReadingRecord
from racks.models import Rack

BEFORE = "20261107_rig_case_optional"


def _alembic(database_url: str) -> Config:
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def _tables(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        return {
            row[0]
            for row in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }


def test_the_migration_round_trips_empty_and_refuses_while_a_reading_exists(
    migrated_db: sessionmaker, db_session: Session, database_url: str, create_user
) -> None:
    config = _alembic(database_url)
    engine = migrated_db.kw["bind"]
    # The per-test truncation empties alembic_version too; the schema is at head.
    command.stamp(config, "head")

    command.downgrade(config, BEFORE)
    try:
        assert not {"photo_readings", "photo_sightings"} & _tables(engine)
    finally:
        command.upgrade(config, "head")
    assert {"photo_readings", "photo_sightings"} <= _tables(engine)

    owner = create_user("pg-reading-owner", "pg-pass")
    rack = Rack(user_id=owner.id, case_id=None, name="From a photo", tags=[])
    db_session.add(rack)
    db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add(
        ImageAssetRecord(
            id="img-pg-reading",
            rack_id=rack.id,
            user_id=owner.id,
            content_sha256="b" * 64,
            width=160,
            height=90,
            byte_length=100,
            storage_path="/dev/null",
            retention_expires_at=now + timedelta(days=30),
        )
    )
    db_session.flush()
    db_session.add(
        PhotoReadingRecord(
            id="read-pg",
            rack_id=rack.id,
            image_asset_id="img-pg-reading",
            user_id=owner.id,
            status="failed",
            reason_code="RECORDING_MISSING",
            provider="recorded",
            photo_sha256="a" * 64,
            policy_version="decision-policy-v1",
            first_row=0,
            last_row=0,
        )
    )
    db_session.commit()
    db_session.close()

    with pytest.raises(RuntimeError, match="refusing to downgrade 20261107_photo_readings"):
        command.downgrade(config, BEFORE)

    assert {"photo_readings", "photo_sightings"} <= _tables(engine)
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "20261107_photo_readings"
