"""
Seed the Golden Demo fixture into the database.

Runs in test/demo environments only.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, asdict, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from core.config import Settings
from core.security import get_password_hash
from modules.models import Module
from cases.models import Case
from racks.models import Rack, RackModule
from patches.models import Patch
from runs.models import Run
from community.models import User
from patches.engine import generate_patches_with_ir, PatchEngineConfig

# Register SQLAlchemy relationship targets used by User / ledger / exports.
from account.models import CreditLedgerEntry, ExportRecord  # noqa: E402, F401
from canon.models import CanonicalCreditLedgerEntryRecord, CanonicalExportRecord  # noqa: E402, F401
from monetization.models import CreditsLedger  # noqa: E402, F401

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "golden_demo_seed.json"

# Demo/test-only seeded accounts (Spec 008 T030). These are fixture credentials for
# local and staging demo hosts, not secrets. The seeder is the single source of
# truth: staging walkthroughs log in with exactly these and never patch hashes.
DEMO_USER_USERNAME = "golden_demo"
DEMO_USER_PASSWORD = "demo-pass"
DEMO_USER_ROLE = "User"
DEMO_ADMIN_USERNAME = "admin_demo"
DEMO_ADMIN_PASSWORD = "admin-pass"
DEMO_ADMIN_ROLE = "Admin"


@dataclass(frozen=True)
class SeedResult:
    user_id: int
    username: str
    password: str = field(repr=False)
    rig_id: int
    run_id: int
    patch_count: int
    run_fingerprint: str
    admin_username: str = DEMO_ADMIN_USERNAME
    admin_password: str = field(default=DEMO_ADMIN_PASSWORD, repr=False)


MODULE_FIXTURES: dict[int, dict[str, Any]] = {
    1001: {
        "brand": "Mutable Instruments",
        "name": "Plaits",
        "hp": 12,
        "module_type": "VCO",
        "power_12v_ma": 70,
        "power_neg12v_ma": 5,
        "io_ports": [
            {"name": "V/Oct", "type": "cv_in"},
            {"name": "FM", "type": "cv_in"},
            {"name": "Out", "type": "audio_out"},
            {"name": "Aux", "type": "audio_out"},
        ],
        "tags": ["digital", "oscillator", "macro-oscillator"],
        "description": "Macro oscillator with multiple synthesis models",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    1002: {
        "brand": "Mutable Instruments",
        "name": "Ripples",
        "hp": 8,
        "module_type": "VCF",
        "power_12v_ma": 50,
        "power_neg12v_ma": 50,
        "io_ports": [
            {"name": "In", "type": "audio_in"},
            {"name": "Cutoff CV", "type": "cv_in"},
            {"name": "Resonance CV", "type": "cv_in"},
            {"name": "LP Out", "type": "audio_out"},
            {"name": "BP Out", "type": "audio_out"},
        ],
        "tags": ["analog", "filter", "multimode"],
        "description": "Multimode analog filter",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    1003: {
        "brand": "Intellijel",
        "name": "Quad VCA",
        "hp": 12,
        "module_type": "VCA",
        "power_12v_ma": 60,
        "power_neg12v_ma": 60,
        "io_ports": [
            {"name": "In 1", "type": "audio_in"},
            {"name": "CV 1", "type": "cv_in"},
            {"name": "Out 1", "type": "audio_out"},
            {"name": "In 2", "type": "audio_in"},
            {"name": "CV 2", "type": "cv_in"},
            {"name": "Out 2", "type": "audio_out"},
        ],
        "tags": ["analog", "vca", "quad"],
        "description": "Quad voltage controlled amplifier",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    1004: {
        "brand": "Make Noise",
        "name": "Maths",
        "hp": 20,
        "module_type": "ENV",
        "power_12v_ma": 60,
        "power_neg12v_ma": 60,
        "io_ports": [
            {"name": "Trig 1", "type": "gate_in"},
            {"name": "Out 1", "type": "cv_out"},
            {"name": "Trig 4", "type": "gate_in"},
            {"name": "Out 4", "type": "cv_out"},
            {"name": "Sum Out", "type": "cv_out"},
        ],
        "tags": ["analog", "envelope", "function-generator", "utility"],
        "description": "Dual envelope generator and function generator",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    1005: {
        "brand": "Mutable Instruments",
        "name": "Batumi",
        "hp": 10,
        "module_type": "LFO",
        "power_12v_ma": 70,
        "power_neg12v_ma": 10,
        "io_ports": [
            {"name": "LFO 1 Out", "type": "cv_out"},
            {"name": "LFO 2 Out", "type": "cv_out"},
            {"name": "LFO 3 Out", "type": "cv_out"},
            {"name": "LFO 4 Out", "type": "cv_out"},
        ],
        "tags": ["digital", "lfo", "quad"],
        "description": "Quad LFO with multiple waveforms",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    1006: {
        "brand": "Make Noise",
        "name": "Rene 2",
        "hp": 34,
        "module_type": "SEQ",
        "power_12v_ma": 150,
        "power_neg12v_ma": 30,
        "io_ports": [
            {"name": "Clock In", "type": "clock_in"},
            {"name": "CV X", "type": "cv_out"},
            {"name": "CV Y", "type": "cv_out"},
            {"name": "Gate Out", "type": "gate_out"},
        ],
        "tags": ["digital", "sequencer", "cartesian"],
        "description": "Cartesian sequencer with X/Y control",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    1007: {
        "brand": "Intellijel",
        "name": "Mixup",
        "hp": 6,
        "module_type": "MIX",
        "power_12v_ma": 40,
        "power_neg12v_ma": 40,
        "io_ports": [
            {"name": "In 1", "type": "audio_in"},
            {"name": "In 2", "type": "audio_in"},
            {"name": "In 3", "type": "audio_in"},
            {"name": "Mix Out", "type": "audio_out"},
        ],
        "tags": ["analog", "mixer", "utility"],
        "description": "Simple 3-channel mixer",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    1008: {
        "brand": "Mutable Instruments",
        "name": "Clouds",
        "hp": 18,
        "module_type": "FX",
        "power_12v_ma": 100,
        "power_neg12v_ma": 20,
        "io_ports": [
            {"name": "In L", "type": "audio_in"},
            {"name": "In R", "type": "audio_in"},
            {"name": "Out L", "type": "audio_out"},
            {"name": "Out R", "type": "audio_out"},
            {"name": "Position CV", "type": "cv_in"},
            {"name": "Size CV", "type": "cv_in"},
        ],
        "tags": ["digital", "granular", "reverb", "effect"],
        "description": "Granular processor and reverb",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    1009: {
        "brand": "Noise Engineering",
        "name": "Ataraxic Iteritas",
        "hp": 6,
        "module_type": "NOISE",
        "power_12v_ma": 42,
        "power_neg12v_ma": 22,
        "io_ports": [
            {"name": "Noise Out", "type": "audio_out"},
            {"name": "Random CV", "type": "cv_out"},
        ],
        "tags": ["digital", "noise", "random"],
        "description": "Noise and random source",
        "source": "Manual",
        "source_reference": "Seed data",
    },
    # Added for issue #95 so the demo shows ten or more patches the engine can justify.
    # HP and power from the catalog (SynthCatalogResearch); jack names are not on file.
    1010: {
        "brand": "Doepfer",
        "name": "A-110-1",
        "hp": 10,
        "module_type": "VCO",
        "power_12v_ma": 90,
        "power_neg12v_ma": 20,
        "io_ports": [],
        "tags": ["analog", "oscillator"],
        "description": "Standard analog VCO",
        "source": "SynthCatalogResearch",
        "source_reference": "module catalog",
    },
    1011: {
        "brand": "Befaco",
        "name": "Even VCO",
        "hp": 8,
        "module_type": "VCO",
        "power_12v_ma": 36,
        "power_neg12v_ma": 26,
        "io_ports": [],
        "tags": ["analog", "oscillator"],
        "description": "Analog VCO",
        "source": "SynthCatalogResearch",
        "source_reference": "module catalog",
    },
}

CASE_FIXTURE = {
    "id": 2001,
    "brand": "Intellijel",
    "name": "7U Performance Case",
    "total_hp": 208,
    "rows": 2,
    "hp_per_row": [104, 104],
    "power_12v_ma": 3000,
    "power_neg12v_ma": 1500,
    "power_5v_ma": 500,
    "description": "Professional 7U case with 104HP rows",
    "source": "Manual",
    "source_reference": "Seed data",
}


def _load_fixture(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _ensure_case(db: Session, fixture: dict[str, Any]) -> Case:
    case = db.query(Case).filter(Case.id == fixture["rig"]["case"]["id"]).first()
    if case:
        return case
    case = Case(**CASE_FIXTURE)
    db.add(case)
    db.commit()
    return case


def _ensure_modules(db: Session, modules: Iterable[dict[str, Any]]) -> list[Module]:
    created: list[Module] = []
    for module in modules:
        module_id = module["module_id"]
        existing = db.query(Module).filter(Module.id == module_id).first()
        if existing:
            created.append(existing)
            continue
        payload = MODULE_FIXTURES[module_id]
        module_obj = Module(id=module_id, **payload)
        db.add(module_obj)
        created.append(module_obj)
    db.commit()
    return created


def _ensure_user(db: Session, username: str, password: str, role: str) -> User:
    """Create or refresh demo account so re-seed always restores known passwords."""
    user = db.query(User).filter(User.username == username).first()
    if user:
        user.password_hash = get_password_hash(password)
        user.role = role
        db.commit()
        return user
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=get_password_hash(password),
        display_name=username,
        role=role,
        referral_code=f"{username}-ref",
    )
    db.add(user)
    db.commit()
    return user


def _truncate_runs(db: Session, rack_id: int) -> None:
    db.query(Patch).filter(Patch.rack_id == rack_id).delete()
    db.query(Run).filter(Run.rack_id == rack_id).delete()
    db.commit()


def _difficulty_from_connections(connections: list[dict[str, Any]]) -> str:
    connection_count = len(connections)
    has_feedback = any(c["from_module_id"] == c["to_module_id"] for c in connections)
    if connection_count <= 2 and not has_feedback:
        return "Easy"
    if connection_count <= 4 and not has_feedback:
        return "Medium"
    return "Hard"


def _fingerprint_patch(patch: Patch) -> str:
    cables_json = json.dumps(patch.connections, sort_keys=True)
    difficulty = _difficulty_from_connections(patch.connections)
    payload = f"{cables_json}|{patch.name}|{patch.category}|{difficulty}"
    return sha256(payload.encode()).hexdigest()


def seed_golden_demo(db: Session, fixture_path: Path = FIXTURE_PATH) -> SeedResult:
    fixture = _load_fixture(fixture_path)
    _ensure_case(db, fixture)
    _ensure_modules(db, fixture["rig"]["modules"])

    user = _ensure_user(db, DEMO_USER_USERNAME, DEMO_USER_PASSWORD, DEMO_USER_ROLE)
    # Canonical staging admin (avoid username "admin" — acceptance fixtures use that).
    _ensure_user(db, DEMO_ADMIN_USERNAME, DEMO_ADMIN_PASSWORD, DEMO_ADMIN_ROLE)

    existing_rack = db.query(Rack).filter(Rack.user_id == user.id).first()
    if existing_rack:
        rack = existing_rack
    else:
        rack = Rack(
            user_id=user.id,
            case_id=fixture["rig"]["case"]["id"],
            name=fixture["rig"]["suggested_name_hint"],
            description="Golden demo rig",
            tags=["golden-demo"],
            is_public=False,
            generation_seed=fixture["seed"],
        )
        db.add(rack)
        db.commit()

    _truncate_runs(db, rack.id)

    rack_modules = fixture["rig"]["modules"]
    db.query(RackModule).filter(RackModule.rack_id == rack.id).delete()

    row_hp = fixture["rig"]["case"]["row_hp"]
    row = 0
    hp_cursor = 0
    for module in rack_modules:
        module_id = module["module_id"]
        module_obj = db.query(Module).filter(Module.id == module_id).first()
        if not module_obj:
            continue
        if hp_cursor + module_obj.hp > row_hp:
            row += 1
            hp_cursor = 0
        db.add(
            RackModule(
                rack_id=rack.id,
                module_id=module_id,
                row_index=row,
                start_hp=hp_cursor,
            )
        )
        hp_cursor += module_obj.hp
    db.commit()

    run = Run(rack_id=rack.id, status="succeeded")
    db.add(run)
    db.commit()
    db.refresh(run)

    config = PatchEngineConfig(max_patches=20, allow_feedback=True, prefer_simple=False)
    generation_ir, patch_graphs, provenance = generate_patches_with_ir(
        db, rack, seed=fixture["seed"], config=config
    )

    patches: list[Patch] = []
    for graph in patch_graphs:
        patch = Patch(
            rack_id=rack.id,
            run_id=run.id,
            name=graph.patch_name,
            suggested_name=graph.patch_name,
            category=graph.category,
            description=graph.description,
            connections=[c.to_dict() for c in graph.connections],
            generation_seed=graph.generation_seed,
            generation_version=generation_ir.engine_version,
            engine_config=asdict(generation_ir.params),
            provenance=provenance.to_dict(),
            generation_ir=generation_ir.to_dict(),
            generation_ir_hash=graph.generation_ir_hash,
            is_public=False,
            tags=[],
        )
        db.add(patch)
        patches.append(patch)
    db.commit()

    for patch in patches:
        if any(conn["from_module_id"] == conn["to_module_id"] for conn in patch.connections):
            patch.tags = ["humor"]
    db.commit()

    fingerprint_list = sorted(_fingerprint_patch(patch) for patch in patches)
    run_fingerprint = sha256("".join(fingerprint_list).encode()).hexdigest()

    return SeedResult(
        user_id=user.id,
        username=user.username,
        password=DEMO_USER_PASSWORD,
        rig_id=rack.id,
        run_id=run.id,
        patch_count=len(patches),
        run_fingerprint=run_fingerprint,
    )


def _print_result(result: SeedResult) -> None:
    print(
        json.dumps(
            {
                "user_id": result.user_id,
                "username": result.username,
                "password": result.password,
                "rig_id": result.rig_id,
                "run_id": result.run_id,
                "patch_count": result.patch_count,
                "run_fingerprint": result.run_fingerprint,
            },
            indent=2,
        )
    )


def _update_fixture_hashes(fixture_path: Path, result: SeedResult) -> None:
    fixture = _load_fixture(fixture_path)
    fixture["expected_hashes"] = {
        "run_fingerprint": result.run_fingerprint,
        "patch_count": result.patch_count,
    }
    fixture_path.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--fixture-path", default=str(FIXTURE_PATH))
    parser.add_argument("--print-hashes", action="store_true")
    parser.add_argument("--update-fixture", action="store_true")
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    settings = Settings()
    engine = create_engine(settings.database_url)
    session_local = sessionmaker(bind=engine)

    with session_local() as db:
        result = seed_golden_demo(db, Path(args.fixture_path))
        if args.update_fixture:
            _update_fixture_hashes(Path(args.fixture_path), result)
        _print_result(result)


if __name__ == "__main__":
    main()
