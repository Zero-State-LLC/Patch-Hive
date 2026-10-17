"""
ModularGrid data importer for PatchHive.

ABX-Core v1.3 compliance:
- Full provenance tracking with source attribution
- SEED enforcement: all imported data includes source metadata
- Deterministic: import can be replayed with same results
"""

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from cases.models import Case
from community.models import Comment, User, Vote
from core.database import SessionLocal
from core.provenance import Provenance
from integrations.seed_data import CASES_DATABASE, MANUFACTURERS, MODULES_DATABASE

# Import all models to resolve SQLAlchemy relationships
from modules.models import Module
from patches.models import Patch
from racks.models import Rack, RackModule


def import_modules(db: Session, clear_existing: bool = False) -> Dict[str, Any]:
    """
    Import modules from ModularGrid database into PatchHive.

    Args:
        db: Database session
        clear_existing: If True, clear existing ModularGrid-sourced modules first

    Returns:
        Dict with import statistics and provenance
    """
    # Create provenance record
    prov = Provenance.create(entity_type="module_import", pipeline="data_import")

    # Clear existing if requested
    if clear_existing:
        deleted = db.query(Module).filter(Module.source == "ModularGrid").delete()
        db.commit()
        print(f"Deleted {deleted} existing ModularGrid modules")

    # Check for duplicates
    existing_modules = db.query(Module).all()
    existing_keys = {(m.brand, m.name) for m in existing_modules}

    imported_count = 0
    skipped_count = 0

    for module_data in MODULES_DATABASE:
        key = (module_data["brand"], module_data["name"])

        if key in existing_keys:
            skipped_count += 1
            print(f"Skipping duplicate: {key[0]} {key[1]}")
            continue

        # Add source metadata
        module_data_with_source = {
            **module_data,
            "source": "ModularGrid",
            "source_reference": "integrations/seed_data.py",
        }

        module = Module(**module_data_with_source)
        db.add(module)
        imported_count += 1
        print(f"Imported: {module.brand} {module.name}")

    db.commit()

    # Complete provenance
    prov.mark_completed()
    prov.add_metric("imported_count", imported_count)
    prov.add_metric("skipped_count", skipped_count)
    prov.add_metric("total_processed", imported_count + skipped_count)

    return {
        "status": "success",
        "imported": imported_count,
        "skipped": skipped_count,
        "total": imported_count + skipped_count,
        "provenance": prov.to_dict(),
    }


def import_cases(db: Session, clear_existing: bool = False) -> Dict[str, Any]:
    """
    Import cases from ModularGrid database into PatchHive.

    Args:
        db: Database session
        clear_existing: If True, clear existing ModularGrid-sourced cases first

    Returns:
        Dict with import statistics and provenance
    """
    # Create provenance record
    prov = Provenance.create(entity_type="case_import", pipeline="data_import")

    # Clear existing if requested
    if clear_existing:
        deleted = db.query(Case).filter(Case.source == "ModularGrid").delete()
        db.commit()
        print(f"Deleted {deleted} existing ModularGrid cases")

    # Check for duplicates
    existing_cases = db.query(Case).all()
    existing_keys = {(c.brand, c.name) for c in existing_cases}

    imported_count = 0
    skipped_count = 0

    for case_data in CASES_DATABASE:
        key = (case_data["brand"], case_data["name"])

        if key in existing_keys:
            skipped_count += 1
            print(f"Skipping duplicate case: {key[0]} {key[1]}")
            continue

        # Add source metadata
        case_data_with_source = {
            **case_data,
            "source": "ModularGrid",
            "source_reference": "integrations/seed_data.py",
        }

        case = Case(**case_data_with_source)
        db.add(case)
        imported_count += 1
        print(f"Imported case: {case.brand} {case.name}")

    db.commit()

    # Complete provenance
    prov.mark_completed()
    prov.add_metric("imported_count", imported_count)
    prov.add_metric("skipped_count", skipped_count)
    prov.add_metric("total_processed", imported_count + skipped_count)

    return {
        "status": "success",
        "imported": imported_count,
        "skipped": skipped_count,
        "total": imported_count + skipped_count,
        "provenance": prov.to_dict(),
    }


def import_all(db: Session, clear_existing: bool = False) -> Dict[str, Any]:
    """
    Import all ModularGrid data (modules and cases).

    Args:
        db: Database session
        clear_existing: If True, clear existing ModularGrid data first

    Returns:
        Dict with combined import statistics
    """
    print("\n=== Importing ModularGrid Data ===\n")

    # Create overall provenance
    prov = Provenance.create(entity_type="full_import", pipeline="data_import")

    print("--- Importing Modules ---")
    modules_result = import_modules(db, clear_existing)

    print("\n--- Importing Cases ---")
    cases_result = import_cases(db, clear_existing)

    # Complete provenance
    prov.mark_completed()
    prov.add_metric("modules_imported", modules_result["imported"])
    prov.add_metric("cases_imported", cases_result["imported"])
    prov.add_metric("total_imported", modules_result["imported"] + cases_result["imported"])

    print("\n=== Import Complete ===")
    print(f"Modules: {modules_result['imported']} imported, {modules_result['skipped']} skipped")
    print(f"Cases: {cases_result['imported']} imported, {cases_result['skipped']} skipped")
    print(f"Total: {modules_result['imported'] + cases_result['imported']} items imported\n")

    return {
        "status": "success",
        "modules": modules_result,
        "cases": cases_result,
        "provenance": prov.to_dict(),
    }


def get_manufacturers_list() -> List[str]:
    """Get list of all manufacturers in the database."""
    return MANUFACTURERS


if __name__ == "__main__":
    """Run importer from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Import ModularGrid data into PatchHive")
    parser.add_argument(
        "--clear", action="store_true", help="Clear existing ModularGrid data before importing"
    )
    parser.add_argument("--modules-only", action="store_true", help="Import only modules")
    parser.add_argument("--cases-only", action="store_true", help="Import only cases")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.modules_only:
            result = import_modules(db, args.clear)
        elif args.cases_only:
            result = import_cases(db, args.clear)
        else:
            result = import_all(db, args.clear)

        print(f"\nProvenance ID: {result['provenance']['run_id']}")
    finally:
        db.close()
