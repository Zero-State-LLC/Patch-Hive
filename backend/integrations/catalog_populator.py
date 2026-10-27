"""
Module Catalog Populator

Populates the lightweight module catalog from various sources.

Strategy:
1. Start with our curated 32 modules
2. Expand with ModularGrid CSV exports (user-provided)
3. Eventually: ModularGrid API integration (if available)

The catalog is lightweight - just enough info to browse/search.
Full specs fetched on-demand when user adds module to rack.
"""

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from cases.models import Case  # noqa: F401
from community.models import Comment, User, Vote  # noqa: F401
from core.database import SessionLocal
from integrations.seed_data import MODULES_DATABASE
from modules.catalog import ModuleCatalog

# Import all models to register them with SQLAlchemy before querying
from modules.models import Module  # noqa: F401
from patches.models import Patch  # noqa: F401
from racks.models import Rack, RackModule  # noqa: F401


def populate_catalog_from_curated_modules(db: Session) -> Dict[str, Any]:
    """
    Convert our 32 curated modules into catalog entries.

    This creates the initial catalog foundation.
    """
    imported = 0
    skipped = 0

    for module_data in MODULES_DATABASE:
        slug = ModuleCatalog.create_slug(module_data["brand"], module_data["name"])

        # Check if already exists
        existing = db.query(ModuleCatalog).filter(ModuleCatalog.slug == slug).first()
        if existing:
            skipped += 1
            continue

        # Create catalog entry
        source = module_data.get("source") or "ModularGrid"
        lead = source in ("ModularGrid", "ModularGridCSV")
        catalog_entry = ModuleCatalog(
            slug=slug,
            brand=module_data["brand"],
            name=module_data["name"],
            hp=module_data["hp"],
            category=module_data["module_type"],
            manufacturer_url=module_data.get("manufacturer_url"),
            is_available="available",  # Assume available unless specified
            source=source,
            # ModularGrid-derived rows are discovery leads only (spec 003 D1).
            access_basis="unknown" if lead else None,
            evidence_status="CATALOG_OBSERVED" if lead else None,
        )

        db.add(catalog_entry)
        imported += 1
        print(f"Added: {catalog_entry.brand} - {catalog_entry.name}")

    db.commit()

    return {
        "status": "success",
        "imported": imported,
        "skipped": skipped,
        "total": imported + skipped,
    }


def import_from_modulargrid_csv(db: Session, csv_path: str) -> Dict[str, Any]:
    """
    Import catalog from ModularGrid CSV export.

    Expected format (ModularGrid export):
    Brand,Module,HP,Category,Image URL,ModularGrid URL

    This allows users to export from ModularGrid and populate catalog.
    """
    import csv

    imported = 0
    skipped = 0
    errors = []

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    brand = row.get("Brand", "").strip()
                    name = row.get("Module", "").strip()

                    if not brand or not name:
                        continue

                    slug = ModuleCatalog.create_slug(brand, name)

                    # Check existing
                    existing = db.query(ModuleCatalog).filter(ModuleCatalog.slug == slug).first()
                    if existing:
                        skipped += 1
                        continue

                    # Parse HP
                    hp_str = row.get("HP", "").strip()
                    try:
                        hp = int(hp_str) if hp_str else None
                    except ValueError:
                        hp = None

                    # Create entry
                    catalog_entry = ModuleCatalog(
                        slug=slug,
                        brand=brand,
                        name=name,
                        hp=hp,
                        category=row.get("Category", "").strip() or None,
                        image_url=row.get("Image URL", "").strip() or None,
                        modulargrid_url=row.get("ModularGrid URL", "").strip() or None,
                        is_available="available",
                        source="ModularGridCSV",
                        access_basis="unknown",
                        evidence_status="CATALOG_OBSERVED",
                    )

                    db.add(catalog_entry)
                    imported += 1

                    if imported % 100 == 0:
                        print(f"Imported {imported} modules...")

                except Exception as e:
                    errors.append(f"Error processing row: {str(e)}")

        db.commit()

        return {
            "status": "success",
            "imported": imported,
            "skipped": skipped,
            "errors": errors[:10],  # First 10 errors
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


def populate_catalog_from_synth_research(db: Session) -> Dict[str, Any]:
    """
    Admit Phase 2 Synth Catalog Research rows into module_catalog.

    Skips slugs that already exist (idempotent with curated ModularGrid seed).
    """
    from integrations.synth_catalog_importer import import_catalog

    return import_catalog(db, dry_run=False)


def populate_catalog_auto(db: Session) -> Dict[str, Any]:
    """
    Auto-populate catalog intelligently.

    1. Check if catalog is empty
    2. If empty, populate from curated modules then synth research seed
    3. Return stats
    """
    current_count = db.query(ModuleCatalog).count()

    if current_count > 0:
        return {
            "status": "already_populated",
            "count": current_count,
            "message": f"Catalog already has {current_count} modules",
        }

    # Populate from curated modules
    print("Populating catalog from curated modules...")
    curated = populate_catalog_from_curated_modules(db)
    print("Expanding catalog from Synth Catalog Research seed...")
    research = populate_catalog_from_synth_research(db)

    return {
        "status": "success",
        "curated": curated,
        "synth_research": research,
        "total": db.query(ModuleCatalog).count(),
    }


def main():
    """
    CLI entry point.

    Usage:
        python -m integrations.catalog_populator                # Auto-populate
        python -m integrations.catalog_populator --csv file.csv  # Import from CSV
    """
    import argparse

    parser = argparse.ArgumentParser(description="Populate module catalog")
    parser.add_argument("--csv", help="Path to ModularGrid CSV export")
    parser.add_argument(
        "--synth-research",
        action="store_true",
        help="Import data/synth-catalog seed into module_catalog (idempotent)",
    )
    parser.add_argument("--force", action="store_true", help="Force re-populate")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.csv:
            print(f"Importing from CSV: {args.csv}")
            result = import_from_modulargrid_csv(db, args.csv)
        elif args.synth_research:
            print("Importing Synth Catalog Research into module_catalog...")
            result = populate_catalog_from_synth_research(db)
        else:
            print("Auto-populating catalog...")
            result = populate_catalog_auto(db)

        print(f"\nResult: {result}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
