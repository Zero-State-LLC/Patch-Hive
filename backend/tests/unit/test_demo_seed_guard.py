"""The demo seeder never publishes a known login on a hosted database or in production."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("seed_golden_demo_guard", ROOT / "scripts" / "seed_golden_demo.py")
seed = importlib.util.module_from_spec(spec)
sys.modules["seed_golden_demo_guard"] = seed
spec.loader.exec_module(seed)

HOSTED = "postgresql://u:p@ep-cool-name-123.us-west-2.aws.neon.tech/patchhive"
STRONG = {"PATCHHIVE_DEMO_USER_PASSWORD": "u" * 20, "PATCHHIVE_DEMO_ADMIN_PASSWORD": "a" * 20}


@pytest.mark.parametrize(
    "url",
    ["postgresql://u:p@localhost:5433/db", "postgresql://u:p@127.0.0.1/db", "postgresql://u:p@db/patchhive", "sqlite:///./x.db"],
)
def test_a_local_database_uses_the_fixed_demo_passwords(url: str) -> None:
    assert seed.demo_passwords(url, None, env={}) == (seed.DEMO_USER_PASSWORD, seed.DEMO_ADMIN_PASSWORD)


@pytest.mark.parametrize("environment", ["production", "prod", "Production"])
def test_production_is_never_seeded(environment: str) -> None:
    with pytest.raises(seed.DemoSeedRefused, match="production"):
        seed.demo_passwords("postgresql://u:p@localhost/db", environment, env=STRONG)


@pytest.mark.parametrize("environment", [None, "", "development"])
def test_a_hosted_database_must_be_declared_staging(environment) -> None:
    with pytest.raises(seed.DemoSeedRefused, match="ENVIRONMENT=staging"):
        seed.demo_passwords(HOSTED, environment, env=STRONG)


@pytest.mark.parametrize(
    "env",
    [{}, {"PATCHHIVE_DEMO_USER_PASSWORD": "short", "PATCHHIVE_DEMO_ADMIN_PASSWORD": "a" * 20},
     {"PATCHHIVE_DEMO_USER_PASSWORD": "u" * 20}],
)
def test_hosted_staging_needs_its_own_strong_passwords(env) -> None:
    with pytest.raises(seed.DemoSeedRefused, match="PATCHHIVE_DEMO_"):
        seed.demo_passwords(HOSTED, "staging", env=env)


def test_hosted_staging_uses_the_supplied_passwords() -> None:
    assert seed.demo_passwords(HOSTED, "staging", env=STRONG) == ("u" * 20, "a" * 20)
