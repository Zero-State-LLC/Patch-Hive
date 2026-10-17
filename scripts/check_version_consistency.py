#!/usr/bin/env python3
"""Check that backend, frontend, and (optionally) a git tag agree on one SemVer version.

Usage: check_version_consistency.py [vX.Y.Z[-pre.N]]
pyproject uses PEP 440 (0.3.0a2); package.json and tags use SemVer (0.3.0-alpha.2).
"""
import json, re, sys, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PEP = {"a": "alpha", "b": "beta", "rc": "rc"}


def pep440_to_semver(v: str) -> str:
    m = re.fullmatch(r"(\d+\.\d+\.\d+)(?:(a|b|rc)(\d+))?", v)
    if not m:
        sys.exit(f"unparseable pyproject version: {v}")
    base, pre, n = m.groups()
    return base if not pre else f"{base}-{PEP[pre]}.{n}"


py = pep440_to_semver(tomllib.loads((ROOT / "backend/pyproject.toml").read_text())["project"]["version"])
fe = json.loads((ROOT / "frontend/package.json").read_text())["version"]
found = {"backend/pyproject.toml": py, "frontend/package.json": fe}
if len(sys.argv) > 1:
    found["tag"] = sys.argv[1].removeprefix("refs/tags/").removeprefix("v")
if len(set(found.values())) != 1:
    sys.exit("version mismatch: " + ", ".join(f"{k}={v}" for k, v in found.items()))
print(f"OK {py}")
