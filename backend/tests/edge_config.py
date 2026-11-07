"""The edge's deploy config, as tests read it."""

from __future__ import annotations

import json
import re
from pathlib import Path

EDGE_API = Path(__file__).resolve().parents[2] / "edge" / "api"


def wrangler() -> dict:
    """edge/api/wrangler.jsonc with its // comments removed (no comment markers in strings)."""
    text = (EDGE_API / "wrangler.jsonc").read_text(encoding="utf-8")
    return json.loads(re.sub(r"^\s*//.*$|\s+//[^\"\n]*$", "", text, flags=re.MULTILINE))


def edge_source() -> str:
    """edge/api/src/index.ts, which decides what the API container receives."""
    return (EDGE_API / "src" / "index.ts").read_text(encoding="utf-8")
