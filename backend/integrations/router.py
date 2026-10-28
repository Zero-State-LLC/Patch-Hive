"""
API endpoints for ModularGrid and Synth Catalog Research integration.

ABX-Core v1.3: Full provenance tracking for all import operations.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from admin.dependencies import require_admin_mutate
from admin.utils import log_admin_action
from community.models import User
from core.database import get_db
from integrations.modulargrid_importer import (
    get_manufacturers_list,
    import_all,
    import_cases,
    import_modules,
)
from integrations.synth_catalog_data import seed_stats
from integrations.synth_catalog_importer import (
    enrich_catalog_hp_from_known_specs,
    import_all as import_synth_catalog_all,
    import_catalog as import_synth_catalog_rows,
    import_full_spec_modules as import_synth_full_spec,
    manufacturers_payload as synth_manufacturers_payload,
)

router = APIRouter(prefix="/modulargrid", tags=["modulargrid"])
synth_catalog_router = APIRouter(prefix="/synth-catalog", tags=["synth-catalog"])


def _audit(db: Session, actor: User, action: str, **params: Any) -> None:
    """Imports rewrite shared reference data, so each run is audited."""
    log_admin_action(
        db, actor=actor, action_type=action, target_type="catalog_import", delta_json=params
    )
    db.commit()


@router.post("/import/modules")
def import_modulargrid_modules(
    clear_existing: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
) -> Dict[str, Any]:
    """
    Import modules from ModularGrid database.

    Args:
        clear_existing: If True, clear existing ModularGrid-sourced modules first
        db: Database session

    Returns:
        Import statistics with provenance
    """
    _audit(db, current_user, "modulargrid.import.modules", clear_existing=clear_existing)
    try:
        result = import_modules(db, clear_existing)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/import/cases")
def import_modulargrid_cases(
    clear_existing: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
) -> Dict[str, Any]:
    """
    Import cases from ModularGrid database.

    Args:
        clear_existing: If True, clear existing ModularGrid-sourced cases first
        db: Database session

    Returns:
        Import statistics with provenance
    """
    _audit(db, current_user, "modulargrid.import.cases", clear_existing=clear_existing)
    try:
        result = import_cases(db, clear_existing)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/import/all")
def import_all_modulargrid_data(
    clear_existing: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
) -> Dict[str, Any]:
    """
    Import all ModularGrid data (modules and cases).

    Args:
        clear_existing: If True, clear existing ModularGrid data first
        db: Database session

    Returns:
        Combined import statistics with provenance
    """
    _audit(db, current_user, "modulargrid.import.all", clear_existing=clear_existing)
    try:
        result = import_all(db, clear_existing)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/manufacturers")
def list_manufacturers() -> Dict[str, Any]:
    """
    Get list of all manufacturers in the ModularGrid database.

    Returns:
        List of manufacturer names
    """
    return {
        "manufacturers": get_manufacturers_list(),
        "count": len(get_manufacturers_list()),
    }


@synth_catalog_router.get("/stats")
def synth_catalog_seed_stats() -> Dict[str, Any]:
    """Return sealed seed stats (counts, content hashes, Abraxas PR link)."""
    try:
        return seed_stats()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@synth_catalog_router.get("/manufacturers")
def synth_catalog_manufacturers() -> Dict[str, Any]:
    """Major brands + brand-index sample from Synth Catalog Research."""
    try:
        return synth_manufacturers_payload()
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@synth_catalog_router.post("/import/catalog")
def import_synth_catalog(
    dry_run: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
) -> Dict[str, Any]:
    """Import Phase 2 research rows into lightweight module_catalog."""
    _audit(db, current_user, "synth_catalog.import.catalog", dry_run=dry_run)
    try:
        return import_synth_catalog_rows(db, dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}") from e


@synth_catalog_router.post("/import/modules")
def import_synth_full_modules(
    clear_existing: bool = False,
    dry_run: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
) -> Dict[str, Any]:
    """Import curated full-spec modules (source=SynthCatalogResearch)."""
    _audit(
        db, current_user, "synth_catalog.import.modules", clear_existing=clear_existing, dry_run=dry_run
    )
    try:
        return import_synth_full_spec(db, clear_existing=clear_existing, dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}") from e


@synth_catalog_router.post("/import/all")
def import_synth_all(
    clear_existing: bool = False,
    dry_run: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
) -> Dict[str, Any]:
    """Import catalog + full-spec tiers from sealed research seed."""
    _audit(db, current_user, "synth_catalog.import.all", clear_existing=clear_existing, dry_run=dry_run)
    try:
        return import_synth_catalog_all(
            db, clear_existing_full=clear_existing, dry_run=dry_run
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}") from e


@synth_catalog_router.post("/enrich/hp")
def enrich_synth_catalog_hp(
    dry_run: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_mutate),
) -> Dict[str, Any]:
    """Fill null module_catalog.hp from curated ModularGrid + modules table."""
    _audit(db, current_user, "synth_catalog.enrich.hp", dry_run=dry_run)
    try:
        return enrich_catalog_hp_from_known_specs(db, dry_run=dry_run)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrich failed: {str(e)}") from e
