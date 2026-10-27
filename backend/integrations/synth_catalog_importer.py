"""
Synth Catalog Research importer for PatchHive.

Two-tier admit:
1. module_catalog — lightweight browse rows from Phase 2 research seed
2. modules — full-spec curated entries only (hp required; power null when unknown)

Idempotent by slug (catalog) and (brand, name, source) for full modules.
ABX-Core v1.3 provenance on every run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from cases.models import Case  # noqa: F401 — SQLAlchemy mapper registration
from community.models import Comment, User, Vote  # noqa: F401
from core.database import SessionLocal
from core.provenance import Provenance
from integrations.seed_data import MODULES_DATABASE
from integrations.synth_catalog_data import (
    DEFAULT_SEED_PATH,
    SOURCE_NAME,
    SOURCE_REFERENCE_DEFAULT,
    get_brand_index,
    get_catalog_modules,
    get_full_spec_modules,
    get_major_brands,
    load_seed,
    resolve_seed_path,
    seed_stats,
)
from modules.catalog import ModuleCatalog
from modules.models import Module  # noqa: F401
from patches.models import Patch  # noqa: F401
from racks.models import Rack, RackModule  # noqa: F401


def _seed_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_catalog_rows(path: Path) -> List[Dict[str, Any]]:
    """Load catalog_modules from a seed path (phase2 default or explicit phase3)."""
    if not path.is_file():
        raise FileNotFoundError(f"Seed not found: {path}")
    # Use get_catalog_modules when path is the default seed; else raw JSON.
    try:
        if path.resolve() == resolve_seed_path().resolve():
            return get_catalog_modules(str(path))
    except FileNotFoundError:
        pass
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("catalog_modules") or [])


def import_catalog(
    db: Session,
    seed_path: Optional[Path] = None,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Admit research catalog rows into module_catalog (skip existing slugs)."""
    path = Path(seed_path).expanduser().resolve() if seed_path else resolve_seed_path()
    rows = _load_catalog_rows(path)
    prov = Provenance.create(entity_type="synth_catalog_import", pipeline="import")

    imported = 0
    skipped = 0
    errors: List[str] = []

    for row in rows:
        brand = (row.get("brand") or "").strip()
        name = (row.get("name") or "").strip()
        if not brand or not name:
            errors.append(f"missing brand/name: {row!r}")
            continue
        slug = ModuleCatalog.create_slug(brand, name)
        existing = db.query(ModuleCatalog).filter(ModuleCatalog.slug == slug).first()
        if existing:
            skipped += 1
            continue
        if dry_run:
            imported += 1
            continue
        entry = ModuleCatalog(
            slug=slug,
            brand=brand,
            name=name,
            hp=row.get("hp"),
            category=row.get("category") or "UTIL",
            manufacturer_url=row.get("manufacturer_url"),
            modulargrid_url=row.get("modulargrid_url"),
            image_url=row.get("image_url"),
            is_available=row.get("is_available") or "available",
            source=(row.get("source") or SOURCE_NAME),
            # ModularGrid-derived seed rows carry their lead tags (spec 003 D1).
            access_basis=row.get("access_basis"),
            evidence_status=row.get("evidence_status"),
        )
        db.add(entry)
        imported += 1

    if not dry_run:
        db.commit()

    prov.mark_completed()
    prov.add_metric("imported_count", imported)
    prov.add_metric("skipped_count", skipped)
    prov.add_metric("error_count", len(errors))

    return {
        "status": "success",
        "tier": "module_catalog",
        "dry_run": dry_run,
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:20],
        "input_records": len(rows),
        "seed_path": str(path),
        "seed_sha256": _seed_sha256(path) if path.is_file() else None,
        "provenance": prov.to_dict(),
    }


def import_full_spec_modules(
    db: Session,
    seed_path: Optional[Path] = None,
    *,
    clear_existing: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Admit curated full-spec modules into modules table."""
    path = resolve_seed_path(seed_path)
    modules = get_full_spec_modules(str(path) if path.is_file() else None)
    prov = Provenance.create(entity_type="synth_catalog_module_import", pipeline="import")

    if clear_existing and not dry_run:
        deleted = db.query(Module).filter(Module.source == SOURCE_NAME).delete()
        db.commit()
        print(f"Deleted {deleted} existing {SOURCE_NAME} modules")

    existing = {
        (m.brand, m.name)
        for m in db.query(Module).filter(Module.source == SOURCE_NAME).all()
    }
    # also skip if same brand+name already present from any source (avoid dual identity)
    all_existing = {(m.brand, m.name) for m in db.query(Module).all()}

    imported = 0
    skipped = 0

    for data in modules:
        brand = data["brand"].strip()
        name = data["name"].strip()
        key = (brand, name)
        if key in existing or key in all_existing:
            skipped += 1
            continue
        if data.get("hp") is None:
            skipped += 1
            continue
        if dry_run:
            imported += 1
            continue
        module = Module(
            brand=brand,
            name=name,
            hp=int(data["hp"]),
            module_type=data.get("module_type") or "UTIL",
            power_12v_ma=data.get("power_12v_ma"),
            power_neg12v_ma=data.get("power_neg12v_ma"),
            power_5v_ma=data.get("power_5v_ma"),
            depth_mm=data.get("depth_mm"),
            io_ports=data.get("io_ports") or [],
            tags=data.get("tags") or [],
            description=data.get("description"),
            manufacturer_url=data.get("manufacturer_url"),
            source=data.get("source") or SOURCE_NAME,
            source_reference=data.get("source_reference") or SOURCE_REFERENCE_DEFAULT,
        )
        db.add(module)
        imported += 1
        all_existing.add(key)

    if not dry_run:
        db.commit()

    prov.mark_completed()
    prov.add_metric("imported_count", imported)
    prov.add_metric("skipped_count", skipped)

    return {
        "status": "success",
        "tier": "modules",
        "dry_run": dry_run,
        "imported": imported,
        "skipped": skipped,
        "input_records": len(modules),
        "seed_path": str(path),
        "seed_sha256": _seed_sha256(path) if path.is_file() else None,
        "provenance": prov.to_dict(),
    }


def import_all(
    db: Session,
    seed_path: Optional[Path] = None,
    *,
    clear_existing_full: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Import catalog + full-spec tiers."""
    path = resolve_seed_path(seed_path)
    prov = Provenance.create(entity_type="synth_catalog_full_import", pipeline="import")

    catalog_result = import_catalog(db, path, dry_run=dry_run)
    full_result = import_full_spec_modules(
        db, path, clear_existing=clear_existing_full, dry_run=dry_run
    )

    prov.mark_completed()
    prov.add_metric("catalog_imported", catalog_result["imported"])
    prov.add_metric("full_spec_imported", full_result["imported"])

    return {
        "status": "success",
        "dry_run": dry_run,
        "catalog": catalog_result,
        "full_spec": full_result,
        "stats": seed_stats(str(path) if path.is_file() else None),
        "provenance": prov.to_dict(),
    }


def manufacturers_payload() -> Dict[str, Any]:
    return {
        "source": SOURCE_NAME,
        "major_brands": get_major_brands(),
        "major_count": len(get_major_brands()),
        "brand_index_count": len(get_brand_index()),
        "brands_sample": get_brand_index()[:50],
    }


def _known_hp_index(db: Session) -> Dict[tuple[str, str], Dict[str, Any]]:
    """
    Build (brand_lower, name_lower) → {hp, category, source} from
    manufacturer-curated ModularGrid data + existing modules rows.
    Never invents values.
    """
    known: Dict[tuple[str, str], Dict[str, Any]] = {}

    for row in MODULES_DATABASE:
        brand = (row.get("brand") or "").strip()
        name = (row.get("name") or "").strip()
        hp = row.get("hp")
        if not brand or not name or hp is None:
            continue
        known[(brand.lower(), name.lower())] = {
            "hp": int(hp),
            "category": row.get("module_type"),
            "spec_source": "ModularGridCurated",
        }

    for m in db.query(Module).filter(Module.hp.isnot(None)).all():
        key = (m.brand.lower(), m.name.lower())
        # Prefer curated constant; modules table fills gaps only
        if key in known:
            continue
        known[key] = {
            "hp": int(m.hp),
            "category": m.module_type,
            "spec_source": f"modules:{m.source}",
        }

    return known


def enrich_catalog_hp_from_known_specs(
    db: Session,
    *,
    dry_run: bool = False,
    fill_category: bool = True,
) -> Dict[str, Any]:
    """
    Fill null module_catalog.hp (and empty category) from known manufacturer specs.

    Sources (fail-closed — only explicit values):
    1. integrations.seed_data.MODULES_DATABASE (empty since 2026-10-17)
    2. existing modules table rows with non-null hp

    Never overwrites a non-null catalog.hp.
    """
    prov = Provenance.create(entity_type="synth_catalog_hp_enrich", pipeline="import")
    known = _known_hp_index(db)

    updated_hp = 0
    updated_category = 0
    examined = 0
    samples: List[Dict[str, Any]] = []

    candidates = (
        db.query(ModuleCatalog)
        .filter((ModuleCatalog.hp.is_(None)) | (ModuleCatalog.category.is_(None)))
        .all()
    )

    for entry in candidates:
        examined += 1
        key = (entry.brand.lower(), entry.name.lower())
        spec = known.get(key)
        if not spec:
            continue
        changed = False
        if entry.hp is None and spec.get("hp") is not None:
            if not dry_run:
                entry.hp = spec["hp"]
            updated_hp += 1
            changed = True
        if (
            fill_category
            and (not entry.category or entry.category == "UTIL")
            and spec.get("category")
            and entry.category != spec["category"]
        ):
            # Only replace UTIL/null with a more specific curated type
            if not entry.category or entry.category == "UTIL":
                if not dry_run:
                    entry.category = spec["category"]
                updated_category += 1
                changed = True
        if changed and len(samples) < 20:
            samples.append(
                {
                    "brand": entry.brand,
                    "name": entry.name,
                    "hp": spec.get("hp"),
                    "category": spec.get("category"),
                    "spec_source": spec.get("spec_source"),
                }
            )

    if not dry_run:
        db.commit()

    prov.mark_completed()
    prov.add_metric("updated_hp", updated_hp)
    prov.add_metric("updated_category", updated_category)
    prov.add_metric("examined", examined)
    prov.add_metric("known_specs", len(known))

    return {
        "status": "success",
        "dry_run": dry_run,
        "examined": examined,
        "known_specs": len(known),
        "updated_hp": updated_hp,
        "updated_category": updated_category,
        "samples": samples,
        "provenance": prov.to_dict(),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Import Synth Catalog Research into PatchHive")
    parser.add_argument(
        "--seed",
        type=Path,
        default=DEFAULT_SEED_PATH,
        help="Path to seed-phase2-v1.json",
    )
    parser.add_argument("--catalog-only", action="store_true")
    parser.add_argument("--full-spec-only", action="store_true")
    parser.add_argument(
        "--clear-full",
        action="store_true",
        help="Delete existing SynthCatalogResearch modules before full-spec import",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--enrich-hp",
        action="store_true",
        help="Fill null catalog HP from ModularGrid curated + modules table",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=None,
        help="Write JSON receipt to this path",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        if args.enrich_hp:
            result = enrich_catalog_hp_from_known_specs(db, dry_run=args.dry_run)
        elif args.catalog_only:
            result = import_catalog(db, args.seed, dry_run=args.dry_run)
        elif args.full_spec_only:
            result = import_full_spec_modules(
                db, args.seed, clear_existing=args.clear_full, dry_run=args.dry_run
            )
        else:
            result = import_all(
                db, args.seed, clear_existing_full=args.clear_full, dry_run=args.dry_run
            )
        print(json.dumps(result, indent=2, default=str))
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            args.receipt.write_text(json.dumps(result, indent=2, default=str) + "\n")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
