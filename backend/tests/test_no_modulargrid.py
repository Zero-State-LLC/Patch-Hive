from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "data" / "synth-catalog"))

import check_no_modulargrid as guard  # noqa: E402
from catalog_scrape import denied_host  # noqa: E402


def test_repo_head_has_no_modulargrid_data():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_no_modulargrid.py")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


def test_guard_flags_extracts_and_fetch_code(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.json").write_text('{"u": "https://www.modulargrid.net/e/foo"}')
    (tmp_path / "s.py").write_text('URL = "https://modulargrid.net/e/" + slug\n')
    (tmp_path / "ok.py").write_text("# ModularGrid is never fetched\n")
    bad = guard.violations(["data/x.json", "s.py", "ok.py", "patchhive-replit.zip"])
    assert len(bad) == 3


def test_fetch_layer_denies_modulargrid():
    assert denied_host("https://www.modulargrid.net/e/x")
    assert denied_host("https://modulargrid.net/")
    assert not denied_host("https://www.doepfer.de/a100.htm")
