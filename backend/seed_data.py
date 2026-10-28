"""
Seed data loader for development and testing.
Creates minimal example data: users, modules, cases.
"""

from sqlalchemy.orm import Session

from cases.models import Case
from community.models import User
from core.database import SessionLocal
from core.security import get_password_hash
from modules.models import Module
from monetization.referrals import generate_referral_code


def load_seed_data(db: Session) -> None:
    """Load seed data into the database."""
    # The seed creates an Admin with a published password; never on a hosted database.
    from core import settings
    from core.security import is_dev_environment

    if not is_dev_environment(settings.environment):
        raise RuntimeError(
            f"seed_data.py creates a demo Admin and runs only in development "
            f"(ENVIRONMENT={settings.environment})"
        )
    print("Loading seed data...")

    # Check if data already exists
    if db.query(User).count() > 0:
        print("Seed data already exists. Skipping.")
        return

    # Create test user
    test_user = User(
        username="testuser",
        email="test@patchhive.io",
        password_hash=get_password_hash("testpass123"),
        display_name="Test User",
        role="Admin",
        referral_code=generate_referral_code(db),
        bio="Test user for development",
    )
    db.add(test_user)

    # Create example modules
    modules_data = [
        {
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
        {
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
        {
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
        {
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
        {
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
        {
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
        {
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
        {
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
        {
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
    ]

    for module_data in modules_data:
        module = Module(**module_data)
        db.add(module)

    # Create example cases
    cases_data = [
        {
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
        },
        {
            "brand": "TipTop Audio",
            "name": "Mantis",
            "total_hp": 208,
            "rows": 2,
            "hp_per_row": [104, 104],
            "power_12v_ma": 2500,
            "power_neg12v_ma": 1200,
            "power_5v_ma": 500,
            "description": "Popular affordable case with great power",
            "source": "Manual",
            "source_reference": "Seed data",
        },
        {
            "brand": "Make Noise",
            "name": "Skiff",
            "total_hp": 104,
            "rows": 1,
            "hp_per_row": [104],
            "power_12v_ma": 1200,
            "power_neg12v_ma": 1200,
            "description": "Compact 104HP single-row case",
            "source": "Manual",
            "source_reference": "Seed data",
        },
    ]

    for case_data in cases_data:
        case = Case(**case_data)
        db.add(case)

    db.commit()
    print("Seed data loaded successfully!")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        load_seed_data(db)
    finally:
        db.close()
