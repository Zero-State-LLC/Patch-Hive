"""Spec 004 T053: the purchase refunds migration stays on the single Alembic head."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from canon.models import ProviderPaymentRecord

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND / "alembic" / "versions" / "20261102_purchase_refunds.py"


def _load():
    spec = importlib.util.spec_from_file_location("purchase_refunds", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_the_migration_revises_credit_checkout_on_the_single_head() -> None:
    module = _load()
    assert module.revision == "20261102_purchase_refunds"
    assert module.down_revision == "20261102_credit_checkout"
    # alembic_version.version_num is VARCHAR(32).
    assert len(module.revision) <= 32
    script = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    heads = script.get_heads()
    assert heads == [module.revision]


def test_the_model_and_the_migration_allow_the_same_statuses() -> None:
    module = _load()
    (status,) = [
        constraint
        for constraint in ProviderPaymentRecord.__table__.constraints
        if constraint.name == "ck_provider_payments_status"
    ]
    assert " ".join(str(status.sqltext).split()) == " ".join(module._NEW_STATUSES.split())
