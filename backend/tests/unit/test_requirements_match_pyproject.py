"""The image installs requirements.txt; CI tests and audits pyproject.toml. They must not drift."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]


def _pins(lines: list[str]) -> dict[str, tuple[list[str], str]]:
    pins = {}
    for raw in lines:
        line = raw.split("#")[0].strip()
        if line:
            name, extras, spec = re.match(
                r"([A-Za-z0-9_.-]+)(?:\[([^\]]*)\])?\s*(.*)", line
            ).groups()
            pins[re.sub(r"[-_.]+", "-", name).lower()] = (sorted((extras or "").split(",")), spec)
    return pins


def test_a_dropped_extra_counts_as_drift() -> None:
    # core/security.py needs both hashers, which only the extras install.
    assert _pins(["pwdlib[argon2,bcrypt]==0.3.1"]) != _pins(["pwdlib==0.3.1"])
    assert _pins(["pwdlib[argon2,bcrypt]==0.3.1"]) == _pins(["pwdlib[bcrypt,argon2]==0.3.1"])


def test_requirements_txt_matches_pyproject_dependencies() -> None:
    project = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert _pins(requirements) == _pins(project["dependencies"])
