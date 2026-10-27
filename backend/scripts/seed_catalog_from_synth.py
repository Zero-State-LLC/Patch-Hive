#!/usr/bin/env python3
"""Seed catalog rows and registry links from a SynthCatalog export."""

import main  # ensure all models are registered
import json
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy.orm import Session
from core.database import SessionLocal
from modules.catalog import ModuleCatalog
from registry.models import Manufacturer, DeviceModel, DeviceFamily

def create_slug(brand: str, name: str) -> str:
    import re
    combined = f"{brand}-{name}".lower()
    slug = re.sub(r"[^a-z0-9]+", "-", combined).strip("-")
    return slug or "unknown"

def main(seed_path: str = "/app/data/synth-catalog/seed-phase2-v1.json"):
    seed = Path(seed_path)
    if not seed.exists():
        print(f"Seed not found: {seed}")
        sys.exit(1)

    data = json.loads(seed.read_text())
    modules = data.get("catalog_modules") or data.get("modules") or []
    print(f"Loaded {len(modules)} catalog modules from seed")

    db: Session = SessionLocal()


    # Build better lookups (manufacturers + families for improved matching)
    man_by_lower = {m.canonical_name.lower(): m.slug for m in db.query(Manufacturer).all()}
    man_by_lower.update({m.slug.lower(): m.slug for m in db.query(Manufacturer).all()})

    fam_by_lower = {}
    for f in db.query(DeviceFamily).all():
        fam_by_lower[f.canonical_name.lower()] = f.slug
        fam_by_lower[f.slug.lower()] = f.slug

    dev_lookup = {}
    for dm in db.query(DeviceModel).all():
        man_name = dm.manufacturer.canonical_name.lower() if dm.manufacturer else ""
        dev_lookup[(man_name, dm.canonical_name.lower())] = (dm.slug, getattr(dm, "family", None) and dm.family.slug)
        dev_lookup[(man_name, dm.slug.lower())] = (dm.slug, getattr(dm, "family", None) and dm.family.slug)

    inserted = 0
    updated = 0

    for m in modules:
        brand = m.get("brand") or m.get("manufacturer") or "Unknown"
        name = m.get("name") or "Unknown Module"
        slug = m.get("slug") or create_slug(brand, name)
        hp = m.get("hp")
        category = m.get("category") or m.get("category_raw")

        existing = db.query(ModuleCatalog).filter_by(slug=slug).first()

        reg_man_slug = None
        brand_lower = brand.lower().replace(" ", "-")
        if brand_lower in man_by_lower:
            reg_man_slug = man_by_lower[brand_lower]
        else:
            for k, v in man_by_lower.items():
                if brand_lower in k or k in brand_lower or brand.lower() in k:
                    reg_man_slug = v
                    break

        reg_dev_slug = None
        reg_fam_slug = None
        if reg_man_slug:
            key = (brand.lower(), name.lower())
            hit = dev_lookup.get(key)
            if hit:
                reg_dev_slug, reg_fam_slug = hit if isinstance(hit, tuple) else (hit, None)
            else:
                for (b, n), val in dev_lookup.items():
                    if reg_man_slug in b or b in reg_man_slug or brand.lower() in b:
                        if name.lower() in n or n in name.lower() or name.lower()[:10] in n:
                            if isinstance(val, tuple):
                                reg_dev_slug, reg_fam_slug = val
                            else:
                                reg_dev_slug = val
                            break

        if existing:
            existing.brand = brand
            existing.name = name
            existing.hp = hp
            existing.category = category
            existing.is_available = m.get("is_available", "available")
            existing.source = m.get("source", "SynthCatalogResearch")
            existing.registry_manufacturer_slug = reg_man_slug
            existing.registry_device_slug = reg_dev_slug
            existing.image_url = m.get("image_url") or m.get("image")
            existing.updated_at = datetime.utcnow().isoformat()
            updated += 1
        else:
            row = ModuleCatalog(
                slug=slug,
                brand=brand,
                name=name,
                hp=hp,
                category=category,
                is_available=m.get("is_available", "available"),
                source=m.get("source", "SynthCatalogResearch"),
                manufacturer_url=m.get("manufacturer_url"),
                access_basis=m.get("access_basis"),
                evidence_status=m.get("evidence_status"),
                registry_manufacturer_slug=reg_man_slug,
                registry_device_slug=reg_dev_slug,
            )
            db.add(row)
            inserted += 1

        if (inserted + updated) % 50 == 0:
            db.commit()

    db.commit()
    db.close()

    print(f"Inserted: {inserted}, Updated: {updated}")
    print("ModuleCatalog seeded with registry links.")

    # Seed richer full Modules from full_spec_modules (if present)
    full_specs = data.get("full_spec_modules", []) or []
    if full_specs:
        print(f"Processing {len(full_specs)} full_spec modules...")
        from modules.models import Module
        full_inserted = 0
        full_updated = 0
        for fs in full_specs:
            b = fs.get("brand") or fs.get("manufacturer")
            n = fs.get("name")
            if not b or not n:
                continue
            slug = fs.get("slug") or create_slug(b, n)
            existing_full = db.query(Module).filter(Module.brand == b, Module.name == n).first()
            # reuse reg match logic simplified
            reg_man = None
            bl = b.lower().replace(" ", "-")
            if bl in man_by_lower:
                reg_man = man_by_lower[bl]
            else:
                for k, v in man_by_lower.items():
                    if bl in k or k in bl:
                        reg_man = v
                        break
            reg_dev = None
            if reg_man:
                for (bb, nn), val in list(dev_lookup.items())[:200]:
                    if b.lower() in bb or bb in b.lower():
                        if n.lower()[:12] in nn or nn[:12] in n.lower():
                            if isinstance(val, tuple):
                                reg_dev = val[0]
                            else:
                                reg_dev = val
                            break
            data_dict = {
                "brand": b,
                "name": n,
                "hp": fs.get("hp") or 10,
                "module_type": fs.get("module_type", "VCO"),
                "power_12v_ma": fs.get("power_12v_ma"),
                "power_neg12v_ma": fs.get("power_neg12v_ma"),
                "power_5v_ma": fs.get("power_5v_ma"),
                "depth_mm": fs.get("depth_mm"),
                "io_ports": fs.get("io_ports", []),
                "tags": fs.get("tags", []),
                "description": fs.get("description"),
                "manufacturer_url": fs.get("manufacturer_url"),
                "registry_manufacturer_slug": reg_man,
                "registry_device_slug": reg_dev,
                "source": fs.get("source", "full_spec_seed"),
                "source_reference": fs.get("source_reference"),
                "image_url": fs.get("image_url") or fs.get("image"),
            }
            if existing_full:
                for k, v in data_dict.items():
                    if hasattr(existing_full, k) and v is not None:
                        setattr(existing_full, k, v)
                full_updated += 1
            else:
                db.add(Module(**{k: v for k, v in data_dict.items() if hasattr(Module, k) or k in ["power_12v_ma", "power_neg12v_ma"]}))
                full_inserted += 1
        db.commit()
        print(f"Full-spec: inserted {full_inserted}, updated {full_updated}")

    db.close()


if __name__ == "__main__":
    main()
