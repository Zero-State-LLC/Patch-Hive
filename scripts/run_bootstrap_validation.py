#!/usr/bin/env python3
"""Idempotent bootstrap validation — write receipt JSON to --receipt."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overlays-dir",
        type=Path,
        default=REPO / "data/synth-catalog/overlays",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        default=REPO / "data/synth-catalog/receipts/staging-bootstrap-validation.json",
    )
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO / "backend"))
    sys.path.insert(0, str(REPO / "scripts"))

    # Full mapper registration for materialize batch
    from cases.models import Case  # noqa: F401
    from community.models import Comment, User, Vote  # noqa: F401
    from modules.catalog import ModuleCatalog  # noqa: F401
    from modules.models import Module  # noqa: F401
    from patches.models import Patch  # noqa: F401
    from racks.models import Rack, RackModule  # noqa: F401

    from core.config import settings
    from core.database import SessionLocal
    from modules.catalog_routes import materialize_catalog_batch
    from sqlalchemy import create_engine, text

    import apply_module_catalog_hp_overlay as hp_apply
    import apply_module_power_depth_overlay as power_apply

    def run_apply(fn, argv_list: list[str]) -> tuple[int, dict]:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = fn(argv_list)
        try:
            body = json.loads(buf.getvalue())
        except Exception:
            body = {"raw": buf.getvalue()[:800], "exit": code}
        return code, body if isinstance(body, dict) else {"value": body}

    receipt: dict = {
        "status": "success",
        "mode": "idempotent_rebuild_validation",
        "steps": [],
    }

    ov = args.overlays_dir
    code, body = run_apply(
        hp_apply.main,
        ["--overlay", str(ov / "module-catalog-hp-v1.json")],
    )
    receipt["steps"].append({"step": "hp_overlay", "exit": code, "result": body})

    db = SessionLocal()
    try:
        batch = materialize_catalog_batch(
            db, brand=None, hp_known_only=True, limit=2000
        )
    finally:
        db.close()
    receipt["steps"].append(
        {
            "step": "materialize_batch",
            "result": {
                "status": batch.get("status"),
                "scanned": batch.get("scanned"),
                "created": batch.get("created"),
                "exists": batch.get("exists"),
                "failed": batch.get("failed"),
            },
        }
    )

    for name in (
        "module-power-depth-v6.json",
        "module-power-depth-v7.json",
        "module-power-depth-v8.json",
        "module-power-depth-v9.json",
    ):
        path = ov / name
        if not path.is_file():
            receipt["steps"].append(
                {"step": "power_overlay", "overlay": name, "skipped": "missing"}
            )
            continue
        code, body = run_apply(power_apply.main, ["--overlay", str(path)])
        receipt["steps"].append(
            {
                "step": "power_overlay",
                "overlay": name,
                "exit": code,
                "result": {
                    k: body.get(k)
                    for k in ("status", "entries", "updated", "skipped", "missing")
                },
            }
        )

    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        cat = conn.execute(text("SELECT COUNT(*), COUNT(hp) FROM module_catalog")).one()
        mod = conn.execute(
            text(
                """
                SELECT COUNT(*),
                       COUNT(*) FILTER (WHERE source='ModuleCatalog'),
                       COUNT(*) FILTER (WHERE source='ModuleCatalog' AND power_12v_ma IS NOT NULL)
                FROM modules
                """
            )
        ).one()

    receipt["after"] = {
        "module_catalog_total": int(cat[0]),
        "module_catalog_hp_known": int(cat[1]),
        "hp_coverage_pct": round(100.0 * cat[1] / cat[0], 1) if cat[0] else 0,
        "modules_total": int(mod[0]),
        "modules_from_catalog": int(mod[1]),
        "modules_catalog_with_p12": int(mod[2]),
        "p12_coverage_pct": round(100.0 * mod[2] / mod[1], 1) if mod[1] else 0,
    }
    mat = receipt["steps"][1]["result"]
    receipt["validation"] = {
        "hp_known_ok": receipt["after"]["module_catalog_hp_known"] >= 404,
        "materialize_ok": receipt["after"]["modules_from_catalog"] >= 399,
        "power_ok": receipt["after"]["p12_coverage_pct"] >= 90.0,
        "idempotent_materialize": mat.get("created") == 0,
        "all_ok": False,
    }
    v = receipt["validation"]
    v["all_ok"] = all(
        [v["hp_known_ok"], v["materialize_ok"], v["power_ok"], v["idempotent_materialize"]]
    )
    if not v["all_ok"]:
        receipt["status"] = "partial"

    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0 if v["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
