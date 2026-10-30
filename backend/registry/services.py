"""Registry query services for the Product Database explorer.

HTTP callers provide a database session. Direct callers without a session use the
versioned registry snapshot, which keeps scripts and tests deterministic and avoids
opening an implicit production connection.

With a session, a manufacturer's models are its registry device models plus its rows
in the module catalog, matched by brand name or alias (or an explicit
``registry_manufacturer_slug``). The catalog is where the loaded modules live; the
snapshot file is not shipped in the API image.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from modules.catalog import ModuleCatalog
from registry.models import DeviceModel, Manufacturer

SNAPSHOT_LATEST = (
    Path(__file__).parent.parent.parent
    / "data"
    / "registry_snapshots"
    / "registry_latest.json"
)


def load_latest_snapshot() -> dict:
    if SNAPSHOT_LATEST.exists():
        return json.loads(SNAPSHOT_LATEST.read_text())
    return {"manufacturers": []}


def _snapshot_manufacturers() -> list[dict]:
    return load_latest_snapshot().get("manufacturers", [])


def _manufacturer_summary(manufacturer: dict) -> dict:
    return {
        "slug": manufacturer.get("slug"),
        "name": manufacturer.get("canonical_name"),
        "model_count": len(manufacturer.get("models", [])),
        "status": manufacturer.get("status"),
    }


def _manufacturer_names(manufacturer: Manufacturer) -> set[str]:
    names = {manufacturer.canonical_name.lower()}
    names.update(alias.lower() for alias in (manufacturer.aliases or []) if isinstance(alias, str))
    return names


_LIVE = ModuleCatalog.tombstoned_at.is_(None)


def _catalog_rows_for(manufacturer: Manufacturer):
    return and_(
        _LIVE,
        or_(
            func.lower(ModuleCatalog.brand).in_(_manufacturer_names(manufacturer)),
            ModuleCatalog.registry_manufacturer_slug == manufacturer.slug,
        ),
    )


def _catalog_model(row: ModuleCatalog) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "name": row.name,
        "brand": row.brand,
        "hp": row.hp,
        "device_type": row.category,
        "format": "eurorack",
        "source": "module_catalog",
    }


def _catalog_counts(db: Session) -> list[tuple[str, str | None, int]]:
    """(lower brand, registry slug, rows) for the whole catalog, in one query."""
    return [
        (brand, slug, int(count))
        for brand, slug, count in db.query(
            func.lower(ModuleCatalog.brand),
            ModuleCatalog.registry_manufacturer_slug,
            func.count(ModuleCatalog.id),
        )
        .filter(_LIVE)
        .group_by(func.lower(ModuleCatalog.brand), ModuleCatalog.registry_manufacturer_slug)
        .all()
    ]


def _model_count(
    manufacturer: Manufacturer,
    device_counts: dict[int, int],
    catalog_counts: list[tuple[str, str | None, int]],
) -> int:
    names = _manufacturer_names(manufacturer)
    catalog = sum(
        count for brand, slug, count in catalog_counts if brand in names or slug == manufacturer.slug
    )
    return device_counts.get(manufacturer.id, 0) + catalog


def count_manufacturers(db: Session | None = None) -> int:
    if db is None:
        return len(_snapshot_manufacturers())
    return db.query(Manufacturer).count()


def list_manufacturers(
    limit: int = 100,
    offset: int = 0,
    db: Session | None = None,
) -> list[dict]:
    if db is None:
        return [
            _manufacturer_summary(manufacturer)
            for manufacturer in _snapshot_manufacturers()[offset : offset + limit]
        ]

    rows = (
        db.query(Manufacturer)
        .order_by(Manufacturer.canonical_name)
        .offset(offset)
        .limit(limit)
        .all()
    )
    device_counts = dict(
        db.query(DeviceModel.manufacturer_id, func.count(DeviceModel.id))
        .group_by(DeviceModel.manufacturer_id)
        .all()
    )
    catalog_counts = _catalog_counts(db)
    return [
        {
            "id": row.id,
            "slug": row.slug,
            "name": row.canonical_name,
            "model_count": _model_count(row, device_counts, catalog_counts),
            "status": row.status or "active",
        }
        for row in rows
    ]


def get_manufacturer(slug: str) -> Optional[dict]:
    for manufacturer in _snapshot_manufacturers():
        if manufacturer.get("slug") == slug:
            return manufacturer
    return None


def search_models(
    q: str = "",
    brand: Optional[str] = None,
    limit: int = 50,
    db: Session | None = None,
) -> list[dict]:
    if db is not None:
        return _search_models_db(db, q=q, brand=brand, limit=limit)
    query = q.lower()
    results = []
    for manufacturer in _snapshot_manufacturers():
        if (
            brand
            and manufacturer.get("slug") != brand
            and manufacturer.get("canonical_name", "").lower() != brand.lower()
        ):
            continue
        for model in manufacturer.get("models", []):
            name = model.get("canonical_name", "")
            if not query or query in name.lower() or query in manufacturer.get(
                "canonical_name", ""
            ).lower():
                results.append(
                    {
                        "brand": manufacturer.get("canonical_name"),
                        "name": name,
                        "slug": model.get("slug"),
                        "hp": model.get("hp"),
                        "device_type": model.get("device_type"),
                    }
                )
                if len(results) >= limit:
                    return results
    return results


def _search_models_db(db: Session, *, q: str, brand: Optional[str], limit: int) -> list[dict]:
    term = q.strip()
    manufacturer = None
    if brand:
        manufacturer = (
            db.query(Manufacturer)
            .filter(
                or_(
                    Manufacturer.slug == brand,
                    func.lower(Manufacturer.canonical_name) == brand.lower(),
                )
            )
            .first()
        )

    devices = db.query(DeviceModel, Manufacturer).join(
        Manufacturer, DeviceModel.manufacturer_id == Manufacturer.id
    )
    if brand:
        devices = devices.filter(Manufacturer.id == (manufacturer.id if manufacturer else -1))
    if term:
        devices = devices.filter(
            or_(
                DeviceModel.canonical_name.icontains(term, autoescape=True),
                Manufacturer.canonical_name.icontains(term, autoescape=True),
            )
        )
    results = [
        {
            "id": model.id,
            "brand": maker.canonical_name,
            "name": model.canonical_name,
            "slug": model.slug,
            "hp": model.hp,
            "device_type": model.device_type,
        }
        for model, maker in devices.order_by(Manufacturer.canonical_name, DeviceModel.canonical_name)
        .limit(limit)
        .all()
    ]

    remaining = limit - len(results)
    if remaining <= 0:
        return results
    catalog = db.query(ModuleCatalog).filter(_LIVE)
    if brand:
        catalog = catalog.filter(
            _catalog_rows_for(manufacturer)
            if manufacturer
            else func.lower(ModuleCatalog.brand) == brand.lower()
        )
    if term:
        catalog = catalog.filter(
            or_(
                ModuleCatalog.name.icontains(term, autoescape=True),
                ModuleCatalog.brand.icontains(term, autoescape=True),
            )
        )
    rows = catalog.order_by(ModuleCatalog.brand, ModuleCatalog.name).limit(remaining).all()
    return results + [_catalog_model(row) for row in rows]


def get_coverage_report(db: Session | None = None) -> dict:
    if db is not None:
        total_manufacturers = db.query(Manufacturer).count()
        total_models = db.query(DeviceModel).count() + db.query(ModuleCatalog).filter(_LIVE).count()
        models_with_hp = (
            db.query(DeviceModel).filter(DeviceModel.hp.is_not(None)).count()
            + db.query(ModuleCatalog).filter(_LIVE, ModuleCatalog.hp.is_not(None)).count()
        )
    else:
        manufacturers = _snapshot_manufacturers()
        models = [model for manufacturer in manufacturers for model in manufacturer.get("models", [])]
        total_manufacturers = len(manufacturers)
        total_models = len(models)
        models_with_hp = sum(model.get("hp") is not None for model in models)

    hp_coverage_pct = round((models_with_hp / total_models) * 100, 2) if total_models else 0
    return {
        "total_manufacturers": total_manufacturers,
        "total_models": total_models,
        "hp_coverage_pct": hp_coverage_pct,
    }


def list_models_for_manufacturer(
    manufacturer_slug: str,
    limit: int = 50,
    db: Session | None = None,
) -> list[dict]:
    if db is None:
        manufacturer = get_manufacturer(manufacturer_slug)
        if not manufacturer:
            return []
        return [
            {
                "slug": model.get("slug"),
                "name": model.get("canonical_name"),
                "hp": model.get("hp"),
                "device_type": model.get("device_type"),
                "format": model.get("format"),
            }
            for model in manufacturer.get("models", [])[:limit]
        ]

    manufacturer = db.query(Manufacturer).filter_by(slug=manufacturer_slug).first()
    if not manufacturer:
        return []
    models = (
        db.query(DeviceModel)
        .filter_by(manufacturer_id=manufacturer.id)
        .limit(limit)
        .all()
    )
    results = [
        {
            "id": model.id,
            "slug": model.slug,
            "name": model.canonical_name,
            "hp": model.hp,
            "device_type": model.device_type,
            "format": model.format,
        }
        for model in models
    ]
    remaining = limit - len(results)
    if remaining > 0:
        rows = (
            db.query(ModuleCatalog)
            .filter(_catalog_rows_for(manufacturer))
            .order_by(ModuleCatalog.name)
            .limit(remaining)
            .all()
        )
        results.extend(_catalog_model(row) for row in rows)
    return results


def get_manufacturer_detail(slug: str, db: Session | None = None) -> Optional[dict]:
    if db is None:
        manufacturer = get_manufacturer(slug)
        if not manufacturer:
            return None
        models = list_models_for_manufacturer(slug, limit=100)
        return {
            "slug": manufacturer.get("slug"),
            "name": manufacturer.get("canonical_name"),
            "website": manufacturer.get("website"),
            "status": manufacturer.get("status"),
            "model_count": len(models),
            "models": models,
        }

    manufacturer = db.query(Manufacturer).filter_by(slug=slug).first()
    if not manufacturer:
        return None
    models = list_models_for_manufacturer(slug, limit=100, db=db)
    model_count = (
        db.query(DeviceModel).filter_by(manufacturer_id=manufacturer.id).count()
        + db.query(ModuleCatalog).filter(_catalog_rows_for(manufacturer)).count()
    )
    return {
        "id": manufacturer.id,
        "slug": manufacturer.slug,
        "name": manufacturer.canonical_name,
        "website": manufacturer.website,
        "status": manufacturer.status,
        "model_count": model_count,
        "models": models,
    }
