"""ModularGrid provenance: archive every listed value, then null/flag/relabel.

Runs against a throwaway Postgres database (CI service). Nothing is deleted:
row counts never drop and every cleared value is kept in catalog_value_archive.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import population as P  # noqa: E402
from test_catalog_population import _admin, _migrate, _recreate  # noqa: E402

MANIFEST = ROOT / "data" / "synth-catalog" / "provenance" / "modulargrid-reverify-v1.json"
DB_NAME = "patchhive_provenance_test"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _pick(pred):
    return next(row for row in _manifest()["rows"] if pred(row))


def test_manifest_has_no_values_and_expected_counts():
    manifest = _manifest()
    assert manifest["batch"] == "modulargrid-provenance-v1"
    for row in manifest["rows"]:
        for item in row["fields"]:
            assert set(item) == {"field", "source_tag", "maker_check", "action"}
    by_action = manifest["counts"]["by_action"]
    assert by_action["null"] + by_action["keep"] + 168 == 2281  # 168 candidate HP are flag-only
    assert by_action["keep"] == 60


def test_no_modulargrid_inputs_left():
    catalog = ROOT / "data" / "synth-catalog"
    for name in (
        "phase2-major-br.md",
        "brand-index-modulargrid.txt",
        "overlays/catalog-new-brand-candidates-v1.json",
        "overlays/module-power-depth-v1.json",
        "overlays/module-power-depth-v5.json",
        "receipts/population-upsert.sql",
    ):
        assert not (catalog / name).exists(), name
    assert not (ROOT / "backend" / "integrations" / "modulargrid_data.py").exists()
    sources = json.loads((catalog / "seed-phase2-v1.sources.json").read_text())
    assert sources["license_status"].startswith("ModularGrid-derived")
    seed = json.loads((catalog / "seed-phase2-v1.json").read_text())
    assert all(row.get("hp") is None for row in seed["catalog_modules"])


@pytest.fixture()
def url():
    admin = _admin()
    try:
        target = _recreate(admin, DB_NAME)
    finally:
        admin.dispose()
    _migrate(target)
    return target


def _counts(engine):
    tables = ("modules", "module_catalog", "manufacturers", "catalog_value_archive")
    with engine.connect() as conn:
        return {t: int(conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one()) for t in tables}


def _row(conn, brand, name):
    return conn.execute(
        text("SELECT * FROM modules WHERE brand = :b AND name = :n"), {"b": brand, "n": name}
    ).mappings().one()


def test_archive_then_null_relabel_and_rerun(url, tmp_path):
    nulled = _pick(
        lambda r: r["table"] == "modules"
        and any(f["action"] == "null" for f in r["fields"])
        and all(f["maker_check"] == "no_maker_match" for f in r["fields"] if f["action"] == "null")
        and not any(f["action"] == "relabel" for f in r["fields"])
    )
    relabel = _pick(lambda r: r["table"] == "modules" and any(f["action"] == "relabel" for f in r["fields"]))
    kept = _pick(lambda r: r["table"] == "modules" and any(f["action"] == "keep" for f in r["fields"]))
    cat = _pick(lambda r: r["table"] == "module_catalog" and r["fields"][0]["action"] == "null")
    engine = create_engine(url)
    insert = text(
        "INSERT INTO modules (brand, name, hp, module_type, power_12v_ma, power_neg12v_ma, power_5v_ma, depth_mm, "
        "io_ports, tags, source, source_reference, status, verification_status, verification_source_url, "
        "imported_at, created_at, updated_at) VALUES (:b, :n, 10, 'UNKNOWN', 111, 22, 3, 44.5, '[]', '[]', "
        "'SynthCatalogResearch', NULL, 'active', :v, :u, NOW(), NOW(), NOW())"
    )
    seen = set()
    with engine.begin() as conn:
        for row, status, src in (
            (nulled, "unverified", None),
            (relabel, "verified", "https://example.invalid/mg"),
            (kept, "unverified", None),
        ):
            if (row["brand"], row["name"]) in seen:
                continue
            seen.add((row["brand"], row["name"]))
            conn.execute(insert, {"b": row["brand"], "n": row["name"], "v": status, "u": src})
        conn.execute(
            text("INSERT INTO module_catalog (slug, brand, name, hp, source) VALUES (:s, :b, :n, 12, 'SynthCatalogResearch')"),
            {"s": cat["slug"], "b": cat["brand"], "n": cat["name"]},
        )
    before = _counts(engine)
    dry = P.populate(url, apply=False, verification_path=tmp_path / "none.json")
    stats = dry["provenance"]["modulargrid-provenance-v1"]
    assert stats["archived_values"] > 0 and stats["nulled_values"] > 0
    assert _counts(engine) == before

    P.populate(url, apply=True, verification_path=tmp_path / "none.json")
    after = _counts(engine)
    for table in ("modules", "module_catalog", "manufacturers"):
        assert after[table] >= before[table]
    batch = {"b": _manifest()["batch"]}
    with engine.connect() as conn:
        values = conn.execute(
            text("SELECT COUNT(*) FROM catalog_value_archive WHERE batch = :b AND field <> '*'"), batch
        ).scalar_one()
        markers = conn.execute(
            text("SELECT COUNT(*) FROM catalog_value_archive WHERE batch = :b AND field = '*'"), batch
        ).scalar_one()
    assert values == stats["archived_values"]
    assert markers == len(_manifest()["rows"])  # one processed marker per row
    with engine.connect() as conn:
        row = _row(conn, nulled["brand"], nulled["name"])
        for item in nulled["fields"]:
            if item["action"] != "null":
                continue
            assert row[item["field"]] is None
            old = conn.execute(
                text("SELECT old_value, source_tag FROM catalog_value_archive WHERE row_key = :k AND field = :f"),
                {"k": P.module_row_key(nulled["brand"], nulled["name"]), "f": item["field"]},
            ).mappings().one()
            assert old["old_value"] is not None and old["source_tag"] == item["source_tag"]
        assert row["needs_reverify"] is True
        rel = _row(conn, relabel["brand"], relabel["name"])
        assert rel["verification_status"] == "unverified" and rel["verification_source_url"] is None
        assert rel["hp"] == 10 and rel["needs_reverify"] is True
        keep_row = _row(conn, kept["brand"], kept["name"])
        for item in kept["fields"]:
            if item["action"] == "keep":
                assert keep_row[item["field"]] is not None
        crow = conn.execute(
            text("SELECT hp, needs_reverify FROM module_catalog WHERE slug = :s"), {"s": cat["slug"]}
        ).mappings().one()
        assert crow["hp"] is None and crow["needs_reverify"] is True
        old_hp = conn.execute(
            text("SELECT old_value FROM catalog_value_archive WHERE table_name = 'module_catalog' AND row_key = :s AND field = 'hp'"),
            {"s": cat["slug"]},
        ).scalar_one()
        assert old_hp == "12"

    again = P.populate(url, apply=True, verification_path=tmp_path / "none.json")
    stats = again["provenance"]["modulargrid-provenance-v1"]
    assert stats["archived_values"] == 0 and stats["nulled_values"] == 0
    assert stats["rows_already_processed"] == len(_manifest()["rows"])
    assert _counts(engine) == after
    engine.dispose()


RAIL_FIX = ROOT / "data" / "synth-catalog" / "provenance" / "maker-crawl-v2-rail-fix-v1.json"
POWER_V11 = ROOT / "data" / "synth-catalog" / "overlays" / "module-power-depth-v11.json"


def test_rail_fix_clears_only_the_misread_value_and_refills_it(url, tmp_path):
    manifest = json.loads(RAIL_FIX.read_text(encoding="utf-8"))
    assert manifest["flag_reverify"] is False
    assert all(f["action"] == "null" and f["only_if_value"] is not None for r in manifest["rows"] for f in r["fields"])
    fixed = {(e["brand"], e["name"]): e for e in json.loads(POWER_V11.read_text(encoding="utf-8"))["entries"]}
    rows = [
        r for r in manifest["rows"]
        if r["fields"][0]["field"] == "power_neg12v_ma"
        and fixed.get((r["brand"], r["name"]), {}).get("power_neg12v_ma") is not None
    ]
    loaded, untouched = rows[0], rows[1]  # staging loaded the misread value; prod holds another
    wrong = loaded["fields"][0]["only_if_value"]
    engine = create_engine(url)
    insert = text(
        "INSERT INTO modules (brand, name, hp, module_type, power_12v_ma, power_neg12v_ma, io_ports, tags, source, "
        "status, verification_status, verification_source_url, imported_at, created_at, updated_at) VALUES "
        "(:b, :n, 10, 'UNKNOWN', 100, :neg, '[]', '[]', 'SynthCatalogResearch', 'active', 'verified', :u, "
        "NOW(), NOW(), NOW())"
    )
    other = untouched["fields"][0]["only_if_value"] + 1
    with engine.begin() as conn:
        conn.execute(insert, {"b": loaded["brand"], "n": loaded["name"], "neg": wrong, "u": "https://example.invalid/a"})
        conn.execute(insert, {"b": untouched["brand"], "n": untouched["name"], "neg": other, "u": "https://example.invalid/b"})

    report = P.populate(url, apply=True, verification_path=tmp_path / "none.json")
    stats = report["provenance"][manifest["batch"]]
    assert stats["nulled_values"] >= 1 and stats["value_not_matched"] >= 1 and stats["flagged_rows"] == 0
    with engine.connect() as conn:
        row = _row(conn, loaded["brand"], loaded["name"])
        assert row["power_neg12v_ma"] == fixed[(loaded["brand"], loaded["name"])]["power_neg12v_ma"]
        assert row["needs_reverify"] is False and row["power_12v_ma"] == 100
        archived = conn.execute(
            text("SELECT old_value FROM catalog_value_archive WHERE batch = :b AND row_key = :k AND field = 'power_neg12v_ma'"),
            {"b": manifest["batch"], "k": P.module_row_key(loaded["brand"], loaded["name"])},
        ).scalar_one()
        assert float(archived) == float(wrong)
        kept = _row(conn, untouched["brand"], untouched["name"])
        assert kept["power_neg12v_ma"] == other and kept["needs_reverify"] is False

    again = P.populate(url, apply=True, verification_path=tmp_path / "none.json")
    assert again["provenance"][manifest["batch"]]["nulled_values"] == 0
    engine.dispose()
