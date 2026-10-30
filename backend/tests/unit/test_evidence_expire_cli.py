"""Operator CLI for evidence-image expiry: dry run by default, --apply to act."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

import evidence.expire as expire_cli
from canon.models import ClassificationEvidenceRecord, ImageAssetRecord
from evidence import retention
from evidence.retention import expire_image_assets
from racks.models import Rack

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


class FakeStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete(self, path) -> bool:
        self.deleted.append(str(path))
        return True


@pytest.fixture
def store(monkeypatch) -> FakeStore:
    fake = FakeStore()
    monkeypatch.setattr(retention, "get_file_store", lambda: fake)
    return fake


def _asset(rack: Rack, asset_id: str, sha: str, *, expires: datetime) -> ImageAssetRecord:
    return ImageAssetRecord(
        id=asset_id,
        rack_id=rack.id,
        user_id=rack.user_id,
        content_sha256=sha,
        width=10,
        height=10,
        byte_length=5,
        storage_path=f"/tmp/{asset_id}.jpg",
        retention_days=30,
        retention_expires_at=expires,
        created_at=NOW - timedelta(days=40),
    )


@pytest.fixture
def seeded(db_session: Session, sample_rack_basic: Rack):
    db_session.add_all(
        [
            _asset(sample_rack_basic, "expired-a", "a" * 64, expires=NOW - timedelta(days=1)),
            _asset(sample_rack_basic, "live-b", "b" * 64, expires=NOW + timedelta(days=5)),
            # Two expired rows sharing bytes with a live row: bytes must be kept.
            _asset(sample_rack_basic, "expired-c", "c" * 64, expires=NOW - timedelta(days=1)),
            _asset(sample_rack_basic, "live-c", "c" * 64, expires=NOW + timedelta(days=5)),
        ]
    )
    db_session.commit()


def _state(db: Session) -> dict[str, bool]:
    db.expire_all()
    return {r.id: r.deleted_at is not None for r in db.query(ImageAssetRecord).all()}


def test_dry_run_reports_and_changes_nothing(db_session: Session, seeded, store: FakeStore) -> None:
    report = expire_cli.run(db_session, apply=False, now=NOW)
    assert report["mode"] == "dry-run"
    assert (report["soft_deleted"], report["purged_files"], report["purge_deferred"]) == (2, 1, 0)
    assert store.deleted == []
    assert not any(_state(db_session).values())


def test_apply_matches_dry_run_and_only_touches_expired(
    db_session: Session, seeded, store: FakeStore
) -> None:
    dry = expire_cli.run(db_session, apply=False, now=NOW)
    applied = expire_cli.run(db_session, apply=True, now=NOW)
    assert applied["mode"] == "apply"
    for key in ("soft_deleted", "purged_files", "purge_deferred"):
        assert applied[key] == dry[key]
    assert _state(db_session) == {
        "expired-a": True,
        "live-b": False,
        "expired-c": True,
        "live-c": False,
    }
    assert store.deleted == ["/tmp/expired-a.jpg"]  # shared bytes with live-c are kept


def test_dry_run_shared_expired_rows_purge_bytes_once(
    db_session: Session, sample_rack_basic: Rack, store: FakeStore
) -> None:
    db_session.add_all(
        [
            _asset(sample_rack_basic, "x1", "d" * 64, expires=NOW - timedelta(days=1)),
            _asset(sample_rack_basic, "x2", "d" * 64, expires=NOW - timedelta(days=2)),
        ]
    )
    db_session.commit()
    dry = expire_image_assets(db_session, now=NOW, dry_run=True)
    db_session.rollback()
    real = expire_image_assets(db_session, now=NOW)
    assert dry == real == {"soft_deleted": 2, "purged_files": 1, "purge_deferred": 0}


def test_does_not_write_append_only_evidence(db_session: Session, seeded, store: FakeStore) -> None:
    before = db_session.query(ClassificationEvidenceRecord).count()
    expire_cli.run(db_session, apply=True, now=NOW)
    assert db_session.query(ClassificationEvidenceRecord).count() == before


def test_main_defaults_to_dry_run(db_session, seeded, store, monkeypatch, capsys) -> None:
    import core.database as database

    monkeypatch.setattr(database, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)
    assert expire_cli.main([]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["mode"] == "dry-run"
    assert store.deleted == []


def test_flush_failure_never_deletes_bytes(
    db_session: Session, seeded, store: FakeStore, monkeypatch
) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("flush failed")

    monkeypatch.setattr(db_session, "flush", boom)
    with pytest.raises(RuntimeError):
        expire_image_assets(db_session, now=NOW)
    assert store.deleted == []


def test_cli_apply_in_fresh_process(tmp_path) -> None:
    """Run the documented command in a clean interpreter (no conftest model imports)."""
    import subprocess
    import sys
    from pathlib import Path

    from sqlalchemy import create_engine, text

    backend = Path(__file__).resolve().parents[2]
    db_file = tmp_path / "cli.db"
    url = f"sqlite:///{db_file}"
    env = {
        "PATH": "/usr/bin:/bin",
        "DATABASE_URL": url,
        "STORAGE_BACKEND": "local",
        "EXPORT_DIR": str(tmp_path / "exports"),
        "PYTHONPATH": str(backend),
    }
    run_py = (
        "import main\n"
        "from core.database import Base, engine, SessionLocal\n"
        "from canon.models import ImageAssetRecord\n"
        "from community.models import User\n"
        "from racks.models import Rack\n"
        "from datetime import datetime, timedelta, timezone\n"
        "Base.metadata.create_all(bind=engine)\n"
        "db = SessionLocal()\n"
        "u = User(username='u', email='u@example.com', password_hash='x')\n"
        "db.add(u); db.flush()\n"
        "from cases.models import Case\n"
        "c = Case(brand='B', name='C', total_hp=84, rows=1, hp_per_row=[84], power_12v_ma=1,\n"
        "  power_neg12v_ma=1, power_5v_ma=1, description='d', source='test')\n"
        "db.add(c); db.flush()\n"
        "r = Rack(user_id=u.id, case_id=c.id, name='r')\n"
        "db.add(r); db.flush()\n"
        "db.add(ImageAssetRecord(id='a1', rack_id=r.id, user_id=u.id, content_sha256='a'*64,\n"
        "  width=1, height=1, byte_length=1, storage_path='nonexistent/a1.jpg', retention_days=1,\n"
        "  retention_expires_at=datetime.now(timezone.utc)-timedelta(days=1)))\n"
        "db.commit()\n"
    )
    seed = subprocess.run(
        [sys.executable, "-c", run_py], env=env, cwd=backend, capture_output=True, text=True
    )
    assert seed.returncode == 0, seed.stderr[-2000:]

    # Fresh interpreter that has imported nothing but the CLI module.
    cli = subprocess.run(
        [sys.executable, "-m", "evidence.expire", "--apply"],
        env=env,
        cwd=backend,
        capture_output=True,
        text=True,
    )
    assert cli.returncode == 0, cli.stderr[-2000:]
    report = json.loads(cli.stdout.strip().splitlines()[-1])
    assert report["mode"] == "apply" and report["soft_deleted"] == 1

    with create_engine(url).connect() as conn:
        deleted = conn.execute(text("select deleted_at from image_assets where id='a1'")).scalar()
    assert deleted is not None
