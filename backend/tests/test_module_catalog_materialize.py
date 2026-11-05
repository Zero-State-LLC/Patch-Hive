"""Module catalog browse filters, stats coverage, and materialize."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from modules.catalog import ModuleCatalog
from modules.catalog_routes import materialize_catalog_entry
from modules.models import Module
from fastapi import HTTPException
import pytest


def _entry(
    db: Session,
    *,
    brand: str,
    name: str,
    hp: int | None,
    category: str = "UTIL",
) -> ModuleCatalog:
    row = ModuleCatalog(
        slug=ModuleCatalog.create_slug(brand, name),
        brand=brand,
        name=name,
        hp=hp,
        category=category,
        is_available="available",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_materialize_requires_hp(db_session: Session):
    row = _entry(db_session, brand="Acid Rain Technology", name="Maestro", hp=None)
    with pytest.raises(HTTPException) as exc:
        materialize_catalog_entry(db_session, row.slug)
    assert exc.value.status_code == 422


def test_materialize_creates_and_is_idempotent(db_session: Session):
    row = _entry(
        db_session, brand="Make Noise", name="DPO", hp=30, category="VCO"
    )
    first = materialize_catalog_entry(db_session, row.slug)
    assert first["status"] == "created"
    assert first["module"]["hp"] == 30
    assert first["module"]["source"] == "ModuleCatalog"

    second = materialize_catalog_entry(db_session, row.slug)
    assert second["status"] == "exists"
    assert second["module_id"] == first["module_id"]

    count = (
        db_session.query(Module)
        .filter(Module.brand == "Make Noise", Module.name == "DPO")
        .count()
    )
    assert count == 1


def test_catalog_stats_hp_coverage(db_session: Session, client=None):
    # Prefer direct ORM stats path used by route
    from modules.catalog_routes import get_catalog_stats

    _entry(db_session, brand="A", name="One", hp=8)
    _entry(db_session, brand="B", name="Two", hp=None)
    stats = get_catalog_stats(db_session)
    assert stats["total_modules"] == 2
    assert stats["hp_stats"]["known"] == 1
    assert stats["hp_stats"]["unknown"] == 1
    assert stats["hp_stats"]["coverage_pct"] == 50.0


def test_materialize_batch_hp_known_only(db_session: Session):
    from modules.catalog_routes import materialize_catalog_batch

    _entry(db_session, brand="BatchCo", name="Alpha", hp=8)
    _entry(db_session, brand="BatchCo", name="Beta", hp=None)
    _entry(db_session, brand="BatchCo", name="Gamma", hp=12)

    first = materialize_catalog_batch(
        db_session, brand="BatchCo", hp_known_only=True, limit=50
    )
    assert first["scanned"] == 2
    assert first["created"] == 2
    assert first["exists"] == 0
    assert first["failed"] == 0

    second = materialize_catalog_batch(
        db_session, brand="BatchCo", hp_known_only=True, limit=50
    )
    assert second["created"] == 0
    assert second["exists"] == 2

    count = (
        db_session.query(Module)
        .filter(Module.brand == "BatchCo")
        .count()
    )
    assert count == 2
    # Null-HP Beta must not materialize
    assert (
        db_session.query(Module)
        .filter(Module.brand == "BatchCo", Module.name == "Beta")
        .count()
        == 0
    )


def test_materialize_batch_keeps_exception_text_out_of_the_result(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    from modules.catalog_routes import materialize_catalog_batch

    detail = "postgresql://ops:hunter2@db.internal/patchhive"
    entry = _entry(db_session, brand="FailCo", name="Alpha", hp=8)

    def fail(*_args, **_kwargs):
        raise RuntimeError(detail)

    monkeypatch.setattr("modules.catalog_routes.materialize_catalog_entry", fail)
    with caplog.at_level(logging.ERROR, logger="modules.catalog_routes"):
        result = materialize_catalog_batch(db_session, brand="FailCo", hp_known_only=True, limit=50)
    assert result["status"] == "partial"
    assert result["failed_samples"] == [{"catalog_slug": entry.slug, "error": "MATERIALIZE_FAILED"}]
    assert detail not in str(result)
    assert detail in caplog.text


def test_catalog_source_persisted_and_filterable(db_session: Session):
    row = ModuleCatalog(
        slug=ModuleCatalog.create_slug("TestCo", "Widget"),
        brand="TestCo",
        name="Widget",
        hp=4,
        category="UTIL",
        is_available="available",
        source="SynthCatalogResearch",
    )
    db_session.add(row)
    db_session.commit()

    assert row.to_dict()["source"] == "SynthCatalogResearch"

    from modules.catalog_routes import browse_module_catalog

    result = browse_module_catalog(
        db=db_session,
        search=None,
        brand=None,
        category=None,
        hp_min=None,
        hp_max=None,
        hp_known=None,
        is_available=None,
        source="SynthCatalogResearch",
        skip=0,
        limit=50,
        sort_by="brand",
        sort_order="asc",
    )
    assert result["total"] >= 1
    assert all(m.get("source") == "SynthCatalogResearch" for m in result["modules"])

    empty = browse_module_catalog(
        db=db_session,
        search=None,
        brand=None,
        category=None,
        hp_min=None,
        hp_max=None,
        hp_known=None,
        is_available=None,
        source="DoesNotExist",
        skip=0,
        limit=50,
        sort_by="brand",
        sort_order="asc",
    )
    assert empty["total"] == 0
