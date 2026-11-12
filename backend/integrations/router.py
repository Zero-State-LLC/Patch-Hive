"""
Read-only endpoints for the maker names and the Synth Catalog Research seed.

Nothing here writes a catalog row: data/synth-catalog/population.py is the only writer (spec 003 D5).
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from integrations.seed_data import MANUFACTURERS
from integrations.synth_catalog_data import manufacturers_payload as synth_manufacturers_payload
from integrations.synth_catalog_data import seed_stats

router = APIRouter(prefix="/modulargrid", tags=["modulargrid"])
synth_catalog_router = APIRouter(prefix="/synth-catalog", tags=["synth-catalog"])


@router.get("/manufacturers")
def list_manufacturers() -> Dict[str, Any]:
    """
    Get the list of maker names.

    Returns:
        List of manufacturer names
    """
    return {
        "manufacturers": MANUFACTURERS,
        "count": len(MANUFACTURERS),
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
