"""Neutral seed data for the legacy demo importers.

The module and case lists that used to live in ``integrations/modulargrid_data.py``
were curated partly from ModularGrid. They were removed from the repository on
2026-10-17 (Danny approval) and archived privately; old values are kept in the
database table ``catalog_value_archive``. Only manufacturer names remain here.

Do not add ModularGrid-derived specs. New specs come from manufacturer pages
through the catalog overlays (see data/synth-catalog/README.md).
"""

from typing import Any, Dict, List

# Manufacturer names only (no specs).
MANUFACTURERS: List[str] = [
    "Mutable Instruments",
    "Make Noise",
    "Intellijel",
    "Noise Engineering",
    "Qu-Bit Electronix",
    "4ms Company",
    "Doepfer",
    "ALM Busy Circuits",
    "Mannequins",
    "Hexinverter",
    "Befaco",
    "Erica Synths",
    "Tiptop Audio",
    "Malekko Heavy Industry",
    "WMD",
    "Joranalogue",
    "Xaoc Devices",
    "Industrial Music Electronics",
    "Shakmat Modular",
    "Instruo",
    "Verbos Electronics",
    "Synthesis Technology",
    "Frequency Central",
    "Random*Source",
    "Buchla USA",
]

# Intentionally empty: see module docstring.
MODULES_DATABASE: List[Dict[str, Any]] = []
CASES_DATABASE: List[Dict[str, Any]] = []
