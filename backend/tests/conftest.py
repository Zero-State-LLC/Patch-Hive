"""
Pytest configuration and fixtures for PatchHive backend tests.
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Keep regression coverage for isolated historical routes without enabling them by default.
os.environ.setdefault("ENABLE_LEGACY_SOCIAL", "true")
os.environ.setdefault("ENABLE_LEGACY_PUBLISHING", "true")
os.environ.setdefault("ENABLE_LEGACY_LEADERBOARDS", "true")
os.environ.setdefault("ENABLE_LEGACY_REFERRALS", "true")

from account.models import CreditLedgerEntry, ExportRecord  # noqa: F401
from admin.models import AdminAuditLog  # Import to ensure tables are created
from admin.models import PendingFunction
from cases.models import Case
from canon.models import ArtifactManifestRecord  # noqa: F401
from canon.models import CanonicalAdminAuditEventRecord  # noqa: F401
from canon.models import CanonicalCreditLedgerEntryRecord  # noqa: F401
from canon.models import CanonicalExportRecord  # noqa: F401
from canon.models import GeneratedPatchRecord  # noqa: F401
from canon.models import GenerationJobRecord  # noqa: F401
from canon.models import GenerationRunRecord  # noqa: F401
from canon.models import ModuleRevisionRecord  # noqa: F401
from canon.models import PatchLibraryRecord  # noqa: F401
from canon.models import RigRevisionRecord  # noqa: F401
from canon.models import StageReceiptRecord  # noqa: F401
from canon.models import StripeEventRecordModel  # noqa: F401
from canon.models import UserPatchAnnotationRecord  # noqa: F401
from canon.models import SystemInventoryRevisionRecord  # noqa: F401
from canon.models import ImageAssetRecord  # noqa: F401
from canon.models import ClassificationEvidenceRecord  # noqa: F401
from canon.models import PatchUserOverlayRecord  # noqa: F401
from canon.models import UserStyleRecipeRecord  # noqa: F401
from community.models import Comment  # Import to ensure tables are created
from community.models import User, Vote
from core.database import Base
from gallery.models import GalleryRevision  # noqa: F401
from intelligence.models import DecisionReceiptRecord  # noqa: F401
from modules.models import Module
from monetization.models import CreditsLedger, Export, License, Referral  # noqa: F401
from patches.models import Patch  # Import to ensure patches table is created
from publishing.models import Publication, PublicationReport  # Import to ensure tables are created
from racks.models import Rack, RackModule
from runs.models import Run  # noqa: F401


@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine) -> Session:
    """Create a database session for testing."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_vco(db_session: Session) -> Module:
    """Create a sample VCO module."""
    module = Module(
        brand="Test Mfg",
        name="Test VCO",
        module_type="VCO",
        hp=10,
        power_12v_ma=50,
        power_neg12v_ma=30,
        power_5v_ma=0,
        description="Test oscillator",
        io_ports=[
            {"name": "V/Oct", "type": "cv_in"},
            {"name": "FM In", "type": "cv_in"},
            {"name": "CV In", "type": "cv_in"},
            {"name": "Audio Out", "type": "audio_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_vcf(db_session: Session) -> Module:
    """Create a sample VCF module."""
    module = Module(
        brand="Test Mfg",
        name="Test VCF",
        module_type="VCF",
        hp=8,
        power_12v_ma=40,
        power_neg12v_ma=20,
        power_5v_ma=0,
        description="Test filter",
        io_ports=[
            {"name": "Audio In", "type": "audio_in"},
            {"name": "Cutoff CV", "type": "cv_in"},
            {"name": "Resonance CV", "type": "cv_in"},
            {"name": "Audio Out", "type": "audio_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_vca(db_session: Session) -> Module:
    """Create a sample VCA module."""
    module = Module(
        brand="Test Mfg",
        name="Test VCA",
        module_type="VCA",
        hp=6,
        power_12v_ma=30,
        power_neg12v_ma=15,
        power_5v_ma=0,
        description="Test amplifier",
        io_ports=[
            {"name": "Audio In", "type": "audio_in"},
            {"name": "CV In", "type": "cv_in"},
            {"name": "Audio Out", "type": "audio_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_envelope(db_session: Session) -> Module:
    """Create a sample envelope generator module."""
    module = Module(
        brand="Test Mfg",
        name="Test ADSR",
        module_type="ENVELOPE",
        hp=8,
        power_12v_ma=25,
        power_neg12v_ma=10,
        power_5v_ma=0,
        description="Test envelope generator",
        io_ports=[
            {"name": "Gate In", "type": "gate_in"},
            {"name": "Trigger In", "type": "trigger_in"},
            {"name": "Envelope Out", "type": "cv_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_lfo(db_session: Session) -> Module:
    """Create a sample LFO module."""
    module = Module(
        brand="Test Mfg",
        name="Test LFO",
        module_type="LFO",
        hp=6,
        power_12v_ma=20,
        power_neg12v_ma=10,
        power_5v_ma=0,
        description="Test LFO",
        io_ports=[
            {"name": "Rate CV", "type": "cv_in"},
            {"name": "LFO Out", "type": "cv_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_sequencer(db_session: Session) -> Module:
    """Create a sample sequencer module."""
    module = Module(
        brand="Test Mfg",
        name="Test Sequencer",
        module_type="SEQUENCER",
        hp=16,
        power_12v_ma=80,
        power_neg12v_ma=40,
        power_5v_ma=0,
        description="Test sequencer",
        io_ports=[
            {"name": "Clock In", "type": "clock_in"},
            {"name": "Reset In", "type": "trigger_in"},
            {"name": "CV Out", "type": "cv_out"},
            {"name": "Gate Out", "type": "gate_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_noise(db_session: Session) -> Module:
    """Create a sample noise source module."""
    module = Module(
        brand="Test Mfg",
        name="Test Noise",
        module_type="NOISE",
        hp=4,
        power_12v_ma=15,
        power_neg12v_ma=5,
        power_5v_ma=0,
        description="Test noise source",
        io_ports=[
            {"name": "Noise Out", "type": "audio_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_effect(db_session: Session) -> Module:
    """Create a sample effects module."""
    module = Module(
        brand="Test Mfg",
        name="Test Reverb",
        module_type="EFFECT",
        hp=12,
        power_12v_ma=60,
        power_neg12v_ma=30,
        power_5v_ma=0,
        description="Test reverb effect",
        io_ports=[
            {"name": "FX In", "type": "audio_in"},
            {"name": "FX Out", "type": "audio_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_mixer(db_session: Session) -> Module:
    """Create a sample mixer module."""
    module = Module(
        brand="Test Mfg",
        name="Test Mixer",
        module_type="MIXER",
        hp=10,
        power_12v_ma=45,
        power_neg12v_ma=25,
        power_5v_ma=0,
        description="Test mixer",
        io_ports=[
            {"name": "Ch1 In", "type": "audio_in"},
            {"name": "Ch2 In", "type": "audio_in"},
            {"name": "Ch3 In", "type": "audio_in"},
            {"name": "Ch4 In", "type": "audio_in"},
            {"name": "Mix Out", "type": "audio_out"},
        ],
        source="test",
    )
    db_session.add(module)
    db_session.commit()
    db_session.refresh(module)
    return module


@pytest.fixture
def sample_user(db_session: Session) -> User:
    """Create a sample test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="$2b$12$dummyhash",  # Dummy bcrypt hash
        referral_code="samplecode",
        role="User",
        display_name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_case(db_session: Session) -> Case:
    """Create a sample Eurorack case."""
    case = Case(
        brand="Test Mfg",
        name="Test Case 84HP",
        total_hp=84,
        rows=1,
        hp_per_row=[84],
        power_12v_ma=1000,
        power_neg12v_ma=1000,
        power_5v_ma=1000,
        description="Test case",
        source="test",
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture
def sample_rack_empty(db_session: Session, sample_user: User, sample_case: Case) -> Rack:
    """Create an empty rack."""
    rack = Rack(
        user_id=sample_user.id,
        name="Empty Rack",
        case_id=sample_case.id,
        description="Test empty rack",
    )
    db_session.add(rack)
    db_session.commit()
    db_session.refresh(rack)
    return rack


@pytest.fixture
def sample_rack_basic(
    db_session: Session,
    sample_user: User,
    sample_case: Case,
    sample_vco: Module,
    sample_vcf: Module,
    sample_vca: Module,
) -> Rack:
    """Create a basic rack with VCO, VCF, VCA."""
    rack = Rack(
        user_id=sample_user.id,
        name="Basic Rack",
        case_id=sample_case.id,
        description="Test basic rack",
    )
    db_session.add(rack)
    db_session.flush()

    # Add modules to rack
    rm1 = RackModule(rack_id=rack.id, module_id=sample_vco.id, row_index=0, start_hp=0)
    rm2 = RackModule(rack_id=rack.id, module_id=sample_vcf.id, row_index=0, start_hp=10)
    rm3 = RackModule(rack_id=rack.id, module_id=sample_vca.id, row_index=0, start_hp=18)

    db_session.add_all([rm1, rm2, rm3])
    db_session.commit()
    db_session.refresh(rack)
    return rack


@pytest.fixture
def sample_rack_full(
    db_session: Session,
    sample_user: User,
    sample_case: Case,
    sample_vco: Module,
    sample_vcf: Module,
    sample_vca: Module,
    sample_envelope: Module,
    sample_lfo: Module,
    sample_sequencer: Module,
) -> Rack:
    """Create a full-featured rack with multiple module types."""
    rack = Rack(
        user_id=sample_user.id,
        name="Full Rack",
        case_id=sample_case.id,
        description="Test full rack",
    )
    db_session.add(rack)
    db_session.flush()

    # Add modules
    modules = [
        (sample_vco, 0),
        (sample_vcf, 10),
        (sample_vca, 18),
        (sample_envelope, 24),
        (sample_lfo, 32),
        (sample_sequencer, 38),
    ]

    for module, pos in modules:
        rm = RackModule(rack_id=rack.id, module_id=module.id, row_index=0, start_hp=pos)
        db_session.add(rm)

    db_session.commit()
    db_session.refresh(rack)
    return rack
