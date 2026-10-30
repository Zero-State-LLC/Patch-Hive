"""Canon export pack writes sealed artifacts + hashed manifest."""

from __future__ import annotations

from pathlib import Path

from canon.export_pack import export_compilation_pack
from tests.canon_demo_pipeline import run_canon_pipeline


def test_export_pack_writes_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    bundle = run_canon_pipeline(seed=7)
    manifest = export_compilation_pack(bundle.compilation, out_dir=out_dir)

    assert (out_dir / "patch_graph.json").exists()
    assert (out_dir / "patch_plan.json").exists()
    assert (out_dir / "validation_report.json").exists()
    assert (out_dir / "manifest.json").exists()
    assert (out_dir / "svgs").exists()
    assert any(p.suffix == ".svg" for p in (out_dir / "svgs").iterdir())
    assert "hashes" in manifest and manifest["hashes"]
    assert manifest["compilation_hash"] == bundle.compilation.canonical_hash_value()
    assert manifest["valid"] is True
