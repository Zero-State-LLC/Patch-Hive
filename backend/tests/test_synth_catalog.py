"""Unit tests for Synth Catalog Research bridge."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from integrations.synth_catalog_data import (
    DEFAULT_SEED_PATH,
    map_availability,
    map_category,
    seed_stats,
)
from integrations.synth_catalog_importer import import_all, import_catalog
from modules.catalog import ModuleCatalog  # noqa: F401 — register table
from modules.models import Module


def test_map_category_taxonomy():
    assert map_category("Oscillator / Digital") == "VCO"
    assert map_category("Filter / Analog") == "VCF"
    assert map_category("VCA / Dual") == "VCA"
    assert map_category("Envelope Generator") == "ENV"
    assert map_category("LFO") == "LFO"
    assert map_category("Clock Generator / Sequencer") == "SEQ"
    assert map_category("Distortion / Effect") == "FX"
    assert map_category("Mixer / Utility") == "MIX"
    assert map_category("Sampling / Granular") == "SAMP"
    assert map_category("MIDI") == "MIDI"
    assert map_category("Attenuator / Multiple") == "UTIL"


def test_map_availability():
    assert map_availability("**Discontinued**") == "discontinued"
    assert map_availability("Active") == "available"
    assert map_availability("Upcoming") == "upcoming"


def test_seed_stats_and_counts():
    from integrations.synth_catalog_data import resolve_seed_path

    resolved = resolve_seed_path()
    assert resolved.is_file()
    stats = seed_stats()
    assert stats["fixture_version"] == "1.0"
    assert stats["catalog_module_count"] >= 300
    assert stats["brand_count"] >= 700
    assert stats["full_spec_module_count"] >= 3
    assert stats["content_hashes"]["phase2_major_br_sha256"]
    assert "Abraxas" in (stats.get("abraxas_pr") or "") or "abraxas" in (
        stats.get("abraxas_pr") or ""
    ).lower()
    # Packaged under backend/data for Docker backend-only images
    backend_packaged = (
        Path(__file__).resolve().parents[1] / "data" / "synth-catalog" / "seed-phase2-v1.json"
    )
    assert backend_packaged.is_file()


def test_import_catalog_idempotent(db_session: Session):
    # Ensure catalog model table is present (import triggers mapper)
    first = import_catalog(db_session, dry_run=False)
    assert first["status"] == "success"
    assert first["imported"] >= 300
    assert first["skipped"] == 0

    second = import_catalog(db_session, dry_run=False)
    assert second["imported"] == 0
    assert second["skipped"] == first["imported"]

    count = db_session.query(ModuleCatalog).count()
    assert count == first["imported"]

    # Provenance: research seed admits with SynthCatalogResearch source
    sourced = (
        db_session.query(ModuleCatalog)
        .filter(ModuleCatalog.source == "SynthCatalogResearch")
        .count()
    )
    assert sourced == first["imported"]


def test_import_all_full_spec_and_skip_duplicate_brand_name(db_session: Session):
    # Pre-seed Make Noise Maths from another source — full-spec should skip
    db_session.add(
        Module(
            brand="Make Noise",
            name="Maths",
            hp=20,
            module_type="UTIL",
            power_12v_ma=60,
            power_neg12v_ma=50,
            io_ports=[],
            tags=[],
            source="ModularGrid",
        )
    )
    db_session.commit()

    result = import_all(db_session, dry_run=False)
    assert result["status"] == "success"
    assert result["catalog"]["imported"] >= 300
    # At least Noise Engineering BIA and Instruo arbhar (Maths skipped)
    assert result["full_spec"]["imported"] >= 2
    assert result["full_spec"]["skipped"] >= 1

    synth_modules = (
        db_session.query(Module).filter(Module.source == "SynthCatalogResearch").all()
    )
    names = {(m.brand, m.name) for m in synth_modules}
    assert ("Noise Engineering", "Basimilus Iteritas Alter") in names
    assert ("Instruo", "arbhar") in names
    assert ("Make Noise", "Maths") not in names


def test_dry_run_does_not_write(db_session: Session):
    result = import_all(db_session, dry_run=True)
    assert result["dry_run"] is True
    assert result["catalog"]["imported"] >= 300
    assert db_session.query(ModuleCatalog).count() == 0
    assert (
        db_session.query(Module).filter(Module.source == "SynthCatalogResearch").count()
        == 0
    )


def test_seed_rebuild_script_exists():
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_synth_catalog_seed.py"
    assert script.is_file()


def test_phase3_seed_import(db_session: Session):
    from pathlib import Path
    from integrations.synth_catalog_importer import import_catalog

    seed = Path(__file__).resolve().parents[2] / "data" / "synth-catalog" / "seed-phase3-v1.json"
    if not seed.is_file():
        seed = (
            Path(__file__).resolve().parents[1]
            / "data"
            / "synth-catalog"
            / "seed-phase3-v1.json"
        )
    assert seed.is_file()
    result = import_catalog(db_session, seed, dry_run=False)
    assert result["status"] == "success"
    assert result["imported"] >= 5
    # arbhar may also exist from phase2 full-spec path later; phase3 adds Instruo keys
    instruo = (
        db_session.query(ModuleCatalog)
        .filter(ModuleCatalog.brand == "Instruo")
        .count()
    )
    assert instruo >= 5


def test_enrich_catalog_hp_from_curated(db_session: Session):
    from integrations.synth_catalog_importer import enrich_catalog_hp_from_known_specs

    # The curated ModularGrid list was removed (2026-10-17); known HP now comes
    # from existing modules rows only.
    db_session.add(
        Module(
            brand="Make Noise",
            name="Maths",
            hp=20,
            module_type="ENV",
            io_ports=[],
            tags=[],
            source="Manual",
        )
    )
    # Catalog row with null HP matching the modules row
    db_session.add(
        ModuleCatalog(
            slug="make-noise-maths",
            brand="Make Noise",
            name="Maths",
            hp=None,
            category="UTIL",
            is_available="available",
        )
    )
    # Catalog row with HP already set — must not be overwritten
    db_session.add(
        ModuleCatalog(
            slug="mutable-instruments-plaits",
            brand="Mutable Instruments",
            name="Plaits",
            hp=12,
            category="VCO",
            is_available="available",
        )
    )
    # Unknown module — no curated match
    db_session.add(
        ModuleCatalog(
            slug="unknown-labs-widget",
            brand="Unknown Labs",
            name="Widget",
            hp=None,
            category=None,
            is_available="available",
        )
    )
    db_session.commit()

    dry = enrich_catalog_hp_from_known_specs(db_session, dry_run=True)
    assert dry["updated_hp"] >= 1
    assert db_session.query(ModuleCatalog).filter_by(slug="make-noise-maths").one().hp is None

    live = enrich_catalog_hp_from_known_specs(db_session, dry_run=False)
    assert live["updated_hp"] >= 1
    maths = db_session.query(ModuleCatalog).filter_by(slug="make-noise-maths").one()
    assert maths.hp == 20
    # category may upgrade from UTIL → ENV from curated
    assert maths.category in {"UTIL", "ENV"}
    plaits = db_session.query(ModuleCatalog).filter_by(slug="mutable-instruments-plaits").one()
    assert plaits.hp == 12  # unchanged
    widget = db_session.query(ModuleCatalog).filter_by(slug="unknown-labs-widget").one()
    assert widget.hp is None
