"""Single source of truth for the API version.

The version lives in ``backend/pyproject.toml`` (``project.version``), which Release Please
bumps. The Docker image copies the backend directory to ``/app``, so ``pyproject.toml`` sits
beside this package at runtime; the package itself is not pip-installed, so
``importlib.metadata`` is not available there.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"
UNKNOWN_VERSION = "unknown"


def read_package_version(pyproject: Path = PYPROJECT_PATH) -> str:
    """Return ``project.version`` from pyproject, or ``"unknown"`` if it cannot be read."""
    try:
        version = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return UNKNOWN_VERSION
    return str(version) if version else UNKNOWN_VERSION
