# PatchHive ModularGrid Integration

Eurorack module database import and management system with full ABX-Core v1.3 provenance tracking.

## Quick Start

### First-Time Setup (Interactive)

```bash
# Run the bootstrap wizard
python -m integrations.bootstrap

# Or automatic mode
python -m integrations.bootstrap --auto
```

### Import Data

```bash
# Import all data (modules + cases)
python -m integrations.modulargrid_importer

# Import modules only
python -m integrations.modulargrid_importer --modules-only

# Import cases only
python -m integrations.modulargrid_importer --cases-only

# Clear existing and re-import
python -m integrations.modulargrid_importer --clear
```

### Via API

```bash
# Import all data
curl -X POST http://localhost:8000/api/modulargrid/import/all

# Import modules only
curl -X POST http://localhost:8000/api/modulargrid/import/modules

# Import cases only
curl -X POST http://localhost:8000/api/modulargrid/import/cases

# Get manufacturer list
curl http://localhost:8000/api/modulargrid/manufacturers

# Synth Catalog Research (two-tier)
curl http://localhost:8000/api/synth-catalog/stats
curl -X POST 'http://localhost:8000/api/synth-catalog/import/all?dry_run=true'
curl -X POST http://localhost:8000/api/synth-catalog/import/catalog
```

### CLI — Synth Catalog Research

```bash
# Stats + dry-run receipt
python -m integrations.synth_catalog_importer --dry-run \
  --receipt ../data/synth-catalog/receipts/seed-phase2-v1.dry-run.json

# Admit catalog + full-spec
python -m integrations.synth_catalog_importer

# Catalog only (module_catalog)
python -m integrations.catalog_populator --synth-research

# Fill null HP from curated ModularGrid + modules table
python -m integrations.synth_catalog_importer --enrich-hp

# Rebuild seed from Abraxas skill references (optional)
python3 scripts/build_synth_catalog_seed.py
```

## File Structure

```
integrations/
├── __init__.py                # Package initialization
├── README.md                  # This file
├── bootstrap.py               # First-run wizard (interactive)
├── modulargrid_data.py        # Curated module/case data (~900 lines)
├── modulargrid_importer.py    # Import logic with provenance
├── synth_catalog_data.py      # Synth Catalog Research seed loader
├── synth_catalog_importer.py  # Two-tier catalog + full-spec importer
├── catalog_populator.py       # Lightweight module_catalog populate
└── router.py                  # FastAPI endpoints (ModularGrid + synth-catalog)
```

## Data Sources

See `DATA_SOURCES.md` for complete provenance documentation.

**Current Data**:
- 32 real Eurorack modules (ModularGrid curated full specs)
- 7 professional cases
- 25 manufacturer brands (curated list)
- Synth Catalog Research seed: ~700 brands + ~300+ Phase 2 catalog rows + 3 full-spec modules

**Sources**:
- Official manufacturer specifications
- ModularGrid community data (as reference)
- Hand-curated for accuracy
- Abraxas `modular-synth-catalog-research` skill packet (PR #984) → `data/synth-catalog/`

## Features

### ✅ ABX-Core v1.3 Compliant

- **Full Provenance**: Every import tracked with run_id, timestamps, metrics
- **SEED Enforcement**: No mock data, all sources documented
- **Deterministic**: Same input → same output
- **Idempotent**: Re-running safe (duplicate detection)

### 🔧 Import Features

- **Deduplication**: Composite key `(brand, name)` prevents duplicates
- **Progress Reporting**: Real-time console output
- **Error Handling**: Graceful failures with detailed logs
- **Batch Operations**: Import modules and cases together or separately
- **Dry Run**: Check what would be imported without committing

### 📊 Data Quality

- **Power Specs**: Verified against manufacturer datasheets
- **HP Widths**: Accurate from official specs
- **I/O Ports**: Simplified but representative
- **Categorization**: Consistent module_type taxonomy

## API Endpoints

### Import Operations

**POST** `/api/modulargrid/import/modules`
- Import modules from curated database
- Query params: `clear_existing` (bool)
- Returns: Import statistics + provenance

**POST** `/api/modulargrid/import/cases`
- Import cases from curated database
- Query params: `clear_existing` (bool)
- Returns: Import statistics + provenance

**POST** `/api/modulargrid/import/all`
- Import both modules and cases
- Query params: `clear_existing` (bool)
- Returns: Combined statistics + provenance

### Information

**GET** `/api/modulargrid/manufacturers`
- List all tracked manufacturers
- Returns: Array of brand names + count

## Module Data Format

Each module includes:

```python
{
    "brand": "Mutable Instruments",
    "name": "Plaits",
    "hp": 12,
    "module_type": "VCO",
    "power_12v_ma": 70,
    "power_neg12v_ma": 5,
    "power_5v_ma": None,
    "io_ports": [
        {"name": "V/Oct", "type": "cv_in"},
        {"name": "FM", "type": "cv_in"},
        {"name": "Out", "type": "audio_out"}
    ],
    "tags": ["digital", "oscillator", "macro-oscillator"],
    "description": "Macro oscillator with 16 synthesis models...",
    "manufacturer_url": "https://mutable-instruments.net/modules/plaits/",
    "source": "ModularGrid",
    "source_reference": "https://www.modulargrid.net/",
    "imported_at": "2025-12-05T22:33:53.832128"
}
```

## Module Categories

Supported `module_type` values:

- `VCO` - Voltage Controlled Oscillator
- `VCF` - Voltage Controlled Filter
- `VCA` - Voltage Controlled Amplifier
- `ENV` - Envelope Generator
- `LFO` - Low Frequency Oscillator
- `SEQ` - Sequencer
- `FX` - Effects
- `MIX` - Mixer
- `CLK` - Clock Generator
- `RAND` - Random/Noise Source
- `SAMP` - Sampler
- `UTIL` - Utility
- `QUAD` - Quad module (multiple identical units)
- `VIDEO` - Video synthesis (joins no patch)
- `SYSTEM` - Rack infrastructure such as power and fans (joins no patch)

## Adding New Modules

### 1. Add to Data File

Edit `modulargrid_data.py`:

```python
MODULES_DATABASE.append({
    "brand": "Your Manufacturer",
    "name": "Module Name",
    "hp": 12,
    "module_type": "VCO",
    "power_12v_ma": 100,
    "power_neg12v_ma": 50,
    "io_ports": [...],
    "tags": ["analog", "oscillator"],
    "description": "Your description",
    "manufacturer_url": "https://..."
})
```

### 2. Run Importer

```bash
python -m integrations.modulargrid_importer
```

### 3. Verify

```bash
curl http://localhost:8000/api/modules/ | jq '.total'
```

## Manufacturers Included

Current curated list (25 brands):

1. Mutable Instruments
2. Make Noise
3. Intellijel
4. Noise Engineering
5. Qu-Bit Electronix
6. 4ms Company
7. Doepfer
8. ALM Busy Circuits
9. Mannequins
10. Hexinverter
11. Befaco
12. Erica Synths
13. Tiptop Audio
14. Malekko Heavy Industry
15. WMD
16. Joranalogue
17. Xaoc Devices
18. Industrial Music Electronics
19. Shakmat Modular
20. Instruo
21. Verbos Electronics
22. Synthesis Technology
23. Frequency Central
24. Random*Source
25. Buchla USA

## Provenance Tracking

Every import operation creates a `Provenance` record:

```python
{
    "run_id": "4c8f067f-8e32-49e4-bfc9-05882001b43f",
    "entity_type": "full_import",
    "pipeline": "data_import",
    "started_at": "2025-12-05T22:33:53.832128",
    "completed_at": "2025-12-05T22:33:56.234567",
    "metrics": {
        "modules_imported": 32,
        "cases_imported": 7,
        "total_imported": 39
    }
}
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Test import specifically
python -m pytest tests/unit/test_models.py -v

# Integration test via API
pytest tests/api/ -v
```

## Troubleshooting

### "No module named 'core'"

Make sure you're running from the backend directory:
```bash
cd backend
python -m integrations.bootstrap
```

### "Database locked"

SQLite issue - close any open database connections:
```bash
# Kill the running app
pkill -f uvicorn

# Try again
python -m integrations.modulargrid_importer
```

### "Module already exists"

This is expected behavior (deduplication working). Use `--clear` to force re-import:
```bash
python -m integrations.modulargrid_importer --clear
```

## Future Enhancements

- [ ] User-contributed module submissions
- [ ] ModularGrid export parser (user-provided files)
- [ ] Enhanced I/O modeling (signal routing)
- [ ] Patch compatibility analysis
- [ ] Price tracking (if permitted)
- [ ] Firmware version tracking (digital modules)

## License & Legal

- Module specifications are publicly available facts (non-copyrightable)
- Product names and trademarks remain property of manufacturers
- No scraping or ToS violations
- Data used for informational purposes (fair use)

See `DATA_SOURCES.md` for complete legal compliance documentation.

## Support

- **Documentation**: See `DATA_SOURCES.md` and `BOOTSTRAP_LOG.md`
- **Issues**: https://github.com/scrimshawlife-ctrl/Patch-Hive/issues
- **API Docs**: http://localhost:8000/docs

---

**Version**: 1.0
**ABX-Core**: v1.3
**Last Updated**: 2025-12-05
