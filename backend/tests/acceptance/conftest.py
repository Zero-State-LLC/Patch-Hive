import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from alembic import command
from alembic.config import Config
from cases.models import Case
from community.models import User
from core.security import get_password_hash
from modules.models import Module

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = REPO_ROOT / "fixtures" / "golden_demo_seed.json"


def _external_database_url() -> str | None:
    """Optional: point acceptance at an existing Postgres (e.g. compose staging).

    Set ACCEPTANCE_DATABASE_URL=postgresql://user:pass@host:port/dbname
    When set, Testcontainers is skipped (CI and local still use containers by default).
    """
    url = (os.environ.get("ACCEPTANCE_DATABASE_URL") or os.environ.get("STAGING_DATABASE_URL") or "").strip()
    return url or None


@pytest.fixture(scope="package")
def postgres_container() -> Generator[PostgresContainer | None, None, None]:
    if _external_database_url():
        yield None
        return
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture(scope="package")
def database_url(postgres_container: PostgresContainer | None) -> str:
    external = _external_database_url()
    if external:
        return external
    assert postgres_container is not None
    return postgres_container.get_connection_url()


# Process-wide state the acceptance package changes: these environment variables, and the
# modules it reloads so the app reads them. Reloading swaps new objects (settings, engine,
# app) into those modules while tests collected earlier still hold the old ones, so at
# teardown the original module namespaces are put back rather than reloaded again.
_ACCEPTANCE_ENV = ("DATABASE_URL", "TEST_MODE", "STRIPE_TEST_MODE", "ALLOW_PRODUCTION_PAYMENTS", "EXPORT_DIR")
_REBOUND_MODULES = (
    "core",
    "core.config",
    "core.database",
    "main",
    "export.routes",
    "patches.routes",
    "canon.routes",
)


def _snapshot_modules() -> dict[str, dict[str, object]]:
    return {name: dict(vars(importlib.import_module(name))) for name in _REBOUND_MODULES}


def _restore_modules(snapshot: dict[str, dict[str, object]]) -> None:
    for name, namespace in snapshot.items():
        module_vars = vars(sys.modules[name])
        module_vars.clear()
        module_vars.update(namespace)


def _rebind_settings() -> None:
    import canon.routes
    import core
    import core.config
    import core.database
    import export.routes
    import main
    import patches.routes

    importlib.reload(core.config)
    importlib.reload(core.database)
    # Route modules bind `settings` at import time; re-point them at the reloaded instance.
    core.settings = core.config.settings
    export.routes.settings = core.config.settings
    patches.routes.settings = core.config.settings
    canon.routes.settings = core.config.settings
    importlib.reload(main)


@pytest.fixture(scope="package")
def migrated_db(database_url: str, tmp_path_factory: pytest.TempPathFactory) -> Generator[sessionmaker, None, None]:
    saved_env = {key: os.environ.get(key) for key in _ACCEPTANCE_ENV}
    saved_modules = _snapshot_modules()
    os.environ["DATABASE_URL"] = database_url
    os.environ["TEST_MODE"] = "true"
    os.environ.setdefault("STRIPE_TEST_MODE", "true")
    os.environ.setdefault("ALLOW_PRODUCTION_PAYMENTS", "false")
    # Prefer explicit dir (Windows agents sometimes cannot write %TEMP%/pytest-of-*)
    export_override = (os.environ.get("ACCEPTANCE_EXPORT_DIR") or "").strip()
    if export_override:
        export_path = Path(export_override)
        export_path.mkdir(parents=True, exist_ok=True)
    else:
        try:
            export_path = Path(tmp_path_factory.mktemp("exports"))
        except OSError:
            export_path = REPO_ROOT / "tmp" / "acceptance-exports"
            export_path.mkdir(parents=True, exist_ok=True)
    os.environ["EXPORT_DIR"] = str(export_path)
    _rebind_settings()

    alembic_cfg = Config(str(Path(__file__).resolve().parents[1] / ".." / "alembic.ini"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(database_url)
    try:
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _restore_modules(saved_modules)


@pytest.fixture(autouse=True)
def _clean_db(migrated_db: sessionmaker) -> None:
    engine = migrated_db.kw["bind"]
    with engine.begin() as conn:
        tables = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        ).fetchall()
        for (table,) in tables:
            conn.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))


@pytest.fixture()
def db_session(migrated_db: sessionmaker) -> Generator[Session, None, None]:
    session = migrated_db()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client(migrated_db: sessionmaker) -> TestClient:
    import main

    return TestClient(main.app)


@pytest.fixture()
def create_user(db_session: Session):
    def _create(username: str, password: str, role: str = "User") -> User:
        user = User(
            username=username,
            email=f"{username}@example.com",
            password_hash=get_password_hash(password),
            display_name=username,
            role=role,
            referral_code=f"{username}-ref",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture()
def login(api_client: TestClient):
    def _login(username: str, password: str) -> str:
        resp = api_client.post(
            "/api/community/auth/login",
            json={"username": username, "password": password},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]

    return _login


@pytest.fixture()
def admin_user(create_user) -> User:
    return create_user("admin", "admin-pass", role="Admin")


@pytest.fixture()
def seed_minimal_modules(db_session: Session):
    case = Case(
        id=2001,
        brand="Intellijel",
        name="7U Performance Case",
        total_hp=208,
        rows=2,
        hp_per_row=[104, 104],
        power_12v_ma=3000,
        power_neg12v_ma=1500,
        power_5v_ma=500,
        description="Professional 7U case",
        source="Manual",
        source_reference="Seed data",
    )
    db_session.add(case)

    modules = [
        Module(
            id=1001,
            brand="Mutable Instruments",
            name="Plaits",
            hp=12,
            module_type="VCO",
            power_12v_ma=70,
            power_neg12v_ma=5,
            io_ports=[{"name": "Out", "type": "audio_out"}],
            tags=["digital"],
            description="Macro oscillator",
            source="Manual",
            source_reference="Seed data",
        ),
        Module(
            id=1002,
            brand="Mutable Instruments",
            name="Ripples",
            hp=8,
            module_type="VCF",
            power_12v_ma=50,
            power_neg12v_ma=50,
            io_ports=[{"name": "LP Out", "type": "audio_out"}],
            tags=["analog"],
            description="Filter",
            source="Manual",
            source_reference="Seed data",
        ),
        Module(
            id=1003,
            brand="Intellijel",
            name="Quad VCA",
            hp=12,
            module_type="VCA",
            power_12v_ma=60,
            power_neg12v_ma=60,
            io_ports=[{"name": "Out 1", "type": "audio_out"}],
            tags=["vca"],
            description="VCA",
            source="Manual",
            source_reference="Seed data",
        ),
        Module(
            id=1004,
            brand="Make Noise",
            name="Maths",
            hp=20,
            module_type="ENV",
            power_12v_ma=60,
            power_neg12v_ma=60,
            io_ports=[{"name": "Out 1", "type": "cv_out"}],
            tags=["utility"],
            description="Envelope",
            source="Manual",
            source_reference="Seed data",
        ),
        Module(
            id=1005,
            brand="Mutable Instruments",
            name="Batumi",
            hp=10,
            module_type="LFO",
            power_12v_ma=70,
            power_neg12v_ma=10,
            io_ports=[{"name": "LFO 1 Out", "type": "cv_out"}],
            tags=["lfo"],
            description="LFO",
            source="Manual",
            source_reference="Seed data",
        ),
        Module(
            id=1006,
            brand="Make Noise",
            name="Rene 2",
            hp=34,
            module_type="SEQ",
            power_12v_ma=150,
            power_neg12v_ma=30,
            io_ports=[{"name": "Gate Out", "type": "gate_out"}],
            tags=["sequencer"],
            description="Sequencer",
            source="Manual",
            source_reference="Seed data",
        ),
        Module(
            id=1007,
            brand="Intellijel",
            name="Mixup",
            hp=6,
            module_type="MIX",
            power_12v_ma=40,
            power_neg12v_ma=40,
            io_ports=[{"name": "Mix Out", "type": "audio_out"}],
            tags=["utility"],
            description="Mixer",
            source="Manual",
            source_reference="Seed data",
        ),
        Module(
            id=1008,
            brand="Mutable Instruments",
            name="Clouds",
            hp=18,
            module_type="FX",
            power_12v_ma=100,
            power_neg12v_ma=20,
            io_ports=[{"name": "Out L", "type": "audio_out"}],
            tags=["fx"],
            description="FX",
            source="Manual",
            source_reference="Seed data",
        ),
        Module(
            id=1009,
            brand="Noise Engineering",
            name="Ataraxic Iteritas",
            hp=6,
            module_type="NOISE",
            power_12v_ma=42,
            power_neg12v_ma=22,
            io_ports=[{"name": "Noise Out", "type": "audio_out"}],
            tags=["noise"],
            description="Noise",
            source="Manual",
            source_reference="Seed data",
        ),
    ]
    db_session.add_all(modules)
    db_session.commit()

    return {"case": case, "modules": modules}


@pytest.fixture()
def golden_demo_seed(db_session: Session):
    seed_script = REPO_ROOT / "scripts" / "seed_golden_demo.py"
    spec = importlib.util.spec_from_file_location("seed_golden_demo", seed_script)
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_golden_demo"] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.seed_golden_demo(db_session)
