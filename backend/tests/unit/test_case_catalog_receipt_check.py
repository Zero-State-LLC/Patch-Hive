"""The seed dry-run check in CI must refuse a bad or mismatched receipt (#264)."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "check_case_catalog_receipt", ROOT / "scripts" / "check_case_catalog_receipt.py"
)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

SEED = b'{"cases": []}'
GOOD = {
    "status": "success",
    "rejected": 0,
    "input_records": 50,
    "input_sha256": hashlib.sha256(SEED).hexdigest(),
}


def test_a_clean_receipt_passes() -> None:
    assert check.problems(GOOD, SEED) == []


def test_a_bad_receipt_is_refused() -> None:
    assert check.problems({**GOOD, "status": "failed"}, SEED)
    assert check.problems({**GOOD, "rejected": 1}, SEED)
    assert check.problems({**GOOD, "input_records": 0}, SEED)
    assert check.problems(GOOD, b"another seed")


def test_ci_runs_the_seed_dry_run() -> None:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "--input ../data/cases/seed-v1.json --dry-run" in text
    assert "check_case_catalog_receipt.py" in text
