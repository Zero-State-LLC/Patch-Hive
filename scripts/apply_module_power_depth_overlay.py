#!/usr/bin/env python3
"""Apply OBSERVED power/depth overlay to modules (fill-null only)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--overlay",
        type=Path,
        default=REPO / "data/synth-catalog/overlays/module-power-depth-v9.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--receipt", type=Path, default=None)
    args = parser.parse_args(argv)

    data = json.loads(args.overlay.read_text(encoding="utf-8"))
    entries = data.get("entries") or []

    sys.path.insert(0, str(REPO / "backend"))
    from sqlalchemy import create_engine, text
    from core.config import settings

    engine = create_engine(settings.database_url)
    updated = 0
    skipped = 0
    missing = 0
    samples = []

    with engine.begin() as conn:
        for e in entries:
            mid = e.get("module_id")
            brand = (e.get("brand") or "").strip()
            name = (e.get("name") or "").strip()
            row = None
            if mid:
                row = conn.execute(
                    text(
                        "SELECT id, power_12v_ma, power_neg12v_ma, power_5v_ma, depth_mm "
                        "FROM modules WHERE id=:id"
                    ),
                    {"id": int(mid)},
                ).mappings().first()
            if not row and brand and name:
                row = conn.execute(
                    text(
                        "SELECT id, power_12v_ma, power_neg12v_ma, power_5v_ma, depth_mm "
                        "FROM modules WHERE brand=:b AND name=:n ORDER BY id LIMIT 1"
                    ),
                    {"b": brand, "n": name},
                ).mappings().first()
            if not row:
                missing += 1
                continue
            sets = []
            params = {"id": row["id"]}
            if row["power_12v_ma"] is None and e.get("power_12v_ma") is not None:
                sets.append("power_12v_ma=:p12")
                params["p12"] = int(e["power_12v_ma"])
            if row["power_neg12v_ma"] is None and e.get("power_neg12v_ma") is not None:
                sets.append("power_neg12v_ma=:pn12")
                params["pn12"] = int(e["power_neg12v_ma"])
            if row["power_5v_ma"] is None and e.get("power_5v_ma") is not None:
                sets.append("power_5v_ma=:p5")
                params["p5"] = int(e["power_5v_ma"])
            if row["depth_mm"] is None and e.get("depth_mm") is not None:
                sets.append("depth_mm=:d")
                params["d"] = float(e["depth_mm"])
            if not sets:
                skipped += 1
                continue
            sets.append("updated_at=NOW()")
            if not args.dry_run:
                conn.execute(text(f"UPDATE modules SET {', '.join(sets)} WHERE id=:id"), params)
            updated += 1
            if len(samples) < 20:
                samples.append({"id": row["id"], "brand": brand, "name": name, "fields": list(params.keys())})
        if args.dry_run:
            conn.rollback()

    receipt = {
        "status": "success",
        "dry_run": args.dry_run,
        "overlay": str(args.overlay),
        "entries": len(entries),
        "updated": updated,
        "skipped": skipped,
        "missing": missing,
        "samples": samples,
    }
    print(json.dumps(receipt, indent=2))
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
