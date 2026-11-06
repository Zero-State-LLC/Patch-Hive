"""Owner decision 16: a NOISE Module Category, for rows whose maker makes noise their main function."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "synth-catalog"
if str(CATALOG) not in sys.path:
    sys.path.insert(0, str(CATALOG))

import population as P  # noqa: E402
from patches.engine import ModuleAnalyzer  # noqa: E402

ROWS = json.loads((CATALOG / "provenance" / "category-corrections-v6.json").read_text(encoding="utf-8"))["rows"]


def test_noise_is_in_the_vocabulary_and_the_manifest_runs_after_the_overlays() -> None:
    assert "NOISE" in P.MODULE_CATEGORIES
    assert CATALOG / "provenance" / "category-corrections-v6.json" in P.CATEGORY_CORRECTION_MANIFESTS


def test_each_row_is_corrected_in_both_tables_and_cites_the_makers_page() -> None:
    catalog = [row for row in ROWS if row["table"] == "module_catalog"]
    modules = [row for row in ROWS if row["table"] == "modules"]
    assert len(catalog) == len(modules) == 17
    assert {row["name"] for row in catalog} == {row["name"] for row in modules}
    for row in catalog:
        item = row["fields"][0]
        assert item["value"] == "NOISE" and item["only_if_value"] != "NOISE"
        assert item["evidence_url"].startswith("https://") and "noise" in item["maker_quote"].lower()
        assert P._correction_problem("module_catalog", item) is None
    for row in modules:
        assert row["fields"][0]["field"] == "module_type"


def test_a_row_with_noise_among_other_functions_is_left_alone() -> None:
    named = {row.get("slug") for row in ROWS}
    assert not named & {
        "verbos-electronics-noise-filter",  # "combines a noise generator with a four-band fixed filter bank"
        "ajh-synth-minimod-glide-noise-mk2",
        "avonsynth-avs-s-h-1",
        "hinton-instruments-modmix-ii",
        "wildsync-noise",  # its page answered with a holding page, so nothing confirms it today
    }


def test_the_engine_counts_noise_as_a_noise_source_and_nothing_else() -> None:
    module = SimpleNamespace(id=1, name="Noise", module_type="NOISE", hp=4)
    session = SimpleNamespace(
        query=lambda *_: SimpleNamespace(
            filter=lambda *_: SimpleNamespace(
                first=lambda: module,
                order_by=lambda *_: SimpleNamespace(all=lambda: [SimpleNamespace(module_id=1)]),
                all=lambda: [SimpleNamespace(module_id=1)],
            )
        )
    )
    analyzer = ModuleAnalyzer(session, SimpleNamespace(id=1, modules=[SimpleNamespace(module_id=1)]))
    assert analyzer.noise_sources == [module]
    for pool in ("vcos", "vcfs", "vcas", "envelopes", "lfos", "sequencers", "mixers", "effects", "utilities"):
        assert getattr(analyzer, pool) == [], pool
