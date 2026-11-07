"""Unit tests for Synth Catalog Research bridge."""

from __future__ import annotations

from pathlib import Path

from integrations.synth_catalog_data import (
    DEFAULT_SEED_PATH,
    map_availability,
    map_category,
    seed_stats,
)


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


def test_seed_rebuild_script_exists():
    script = Path(__file__).resolve().parents[2] / "scripts" / "build_synth_catalog_seed.py"
    assert script.is_file()
