"""
Tests for SQLAlchemy database models.
"""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cases.models import Case
from community.models import Comment, User, Vote
from modules.models import Module
from racks.models import Rack, RackModule


class TestModuleModel:
    """Tests for Module model."""

    def test_create_module(self, db_session: Session):
        """Test creating a basic module."""
        module = Module(
            brand="Mutable Instruments",
            name="Plaits",
            hp=12,
            module_type="VCO",
            power_12v_ma=50,
            power_neg12v_ma=5,
            power_5v_ma=0,
            io_ports=[
                {"name": "V/Oct", "type": "cv_in"},
                {"name": "Out", "type": "audio_out"},
            ],
            description="Macro oscillator",
            source="test",
        )
        db_session.add(module)
        db_session.commit()

        assert module.id is not None
        assert module.brand == "Mutable Instruments"
        assert module.name == "Plaits"
        assert module.hp == 12
        assert module.module_type == "VCO"
        assert len(module.io_ports) == 2

    def test_module_timestamps(self, db_session: Session):
        """Test that timestamps are set automatically."""
        module = Module(
            brand="Test",
            name="Test Module",
            hp=10,
            module_type="VCO",
            io_ports=[],
            source="test",
        )
        db_session.add(module)
        db_session.commit()

        assert module.created_at is not None
        assert module.updated_at is not None
        assert isinstance(module.created_at, datetime)
        assert isinstance(module.updated_at, datetime)

    def test_module_brand_required(self, db_session: Session):
        """Test that brand is required."""
        module = Module(
            name="Test Module",
            hp=10,
            module_type="VCO",
            io_ports=[],
            source="test",
        )
        db_session.add(module)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_module_name_required(self, db_session: Session):
        """Test that name is required."""
        module = Module(
            brand="Test",
            hp=10,
            module_type="VCO",
            io_ports=[],
            source="test",
        )
        db_session.add(module)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_module_hp_required(self, db_session: Session):
        """Test that HP is required."""
        module = Module(
            brand="Test",
            name="Test Module",
            module_type="VCO",
            io_ports=[],
            source="test",
        )
        db_session.add(module)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_module_io_ports_json(self, db_session: Session):
        """Test that IO ports are stored as JSON."""
        ports = [
            {"name": "CV In 1", "type": "cv_in"},
            {"name": "CV In 2", "type": "cv_in"},
            {"name": "Audio Out", "type": "audio_out"},
        ]
        module = Module(
            brand="Test",
            name="Test Module",
            hp=10,
            module_type="VCO",
            io_ports=ports,
            source="test",
        )
        db_session.add(module)
        db_session.commit()
        db_session.refresh(module)

        assert module.io_ports == ports
        assert len(module.io_ports) == 3

    def test_module_tags_default_empty(self, db_session: Session):
        """Test that tags default to empty list."""
        module = Module(
            brand="Test",
            name="Test Module",
            hp=10,
            module_type="VCO",
            io_ports=[],
            source="test",
        )
        db_session.add(module)
        db_session.commit()

        assert module.tags == []


class TestCaseModel:
    """Tests for Case model."""

    def test_create_case(self, db_session: Session):
        """Test creating a basic case."""
        case = Case(
            brand="TipTop Audio",
            name="Mantis",
            total_hp=208,
            rows=2,
            hp_per_row=[104, 104],
            power_12v_ma=2000,
            power_neg12v_ma=1200,
            power_5v_ma=2000,
            description="Mantis case",
            source="test",
        )
        db_session.add(case)
        db_session.commit()

        assert case.id is not None
        assert case.brand == "TipTop Audio"
        assert case.name == "Mantis"
        assert case.total_hp == 208
        assert case.rows == 2
        assert case.hp_per_row == [104, 104]

    def test_case_hp_per_row_json(self, db_session: Session):
        """Test that hp_per_row is stored as JSON array."""
        case = Case(
            brand="Test",
            name="Test Case",
            total_hp=84,
            rows=1,
            hp_per_row=[84],
            source="test",
        )
        db_session.add(case)
        db_session.commit()
        db_session.refresh(case)

        assert case.hp_per_row == [84]
        assert isinstance(case.hp_per_row, list)

    def test_case_brand_required(self, db_session: Session):
        """Test that brand is required."""
        case = Case(
            name="Test Case",
            total_hp=84,
            rows=1,
            hp_per_row=[84],
            source="test",
        )
        db_session.add(case)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_case_timestamps(self, db_session: Session):
        """Test that timestamps are set automatically."""
        case = Case(
            brand="Test",
            name="Test Case",
            total_hp=84,
            rows=1,
            hp_per_row=[84],
            source="test",
        )
        db_session.add(case)
        db_session.commit()

        assert case.created_at is not None
        assert case.updated_at is not None


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, db_session: Session):
        """Test creating a basic user."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="$2b$12$hashedpassword",
            referral_code="refcode",
            role="User",
            display_name="Test User",
        )
        db_session.add(user)
        db_session.commit()

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password_hash == "$2b$12$hashedpassword"

    def test_user_username_unique(self, db_session: Session):
        """Test that username must be unique."""
        user1 = User(
            username="testuser",
            email="test1@example.com",
            password_hash="hash1",
            referral_code="refcode1",
            role="User",
        )
        user2 = User(
            username="testuser",  # Same username
            email="test2@example.com",
            password_hash="hash2",
            referral_code="refcode2",
            role="User",
        )
        db_session.add(user1)
        db_session.commit()

        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_email_unique(self, db_session: Session):
        """Test that email must be unique."""
        user1 = User(
            username="user1",
            email="test@example.com",
            password_hash="hash1",
            referral_code="refcode3",
            role="User",
        )
        user2 = User(
            username="user2",
            email="test@example.com",  # Same email
            password_hash="hash2",
            referral_code="refcode4",
            role="User",
        )
        db_session.add(user1)
        db_session.commit()

        db_session.add(user2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_user_timestamps(self, db_session: Session):
        """Test that timestamps are set automatically."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hash",
            referral_code="refcode5",
            role="User",
        )
        db_session.add(user)
        db_session.commit()

        assert user.created_at is not None
        assert isinstance(user.created_at, datetime)


class TestRackModel:
    """Tests for Rack model."""

    def test_create_rack(self, db_session: Session, sample_user: User, sample_case: Case):
        """Test creating a basic rack."""
        rack = Rack(
            user_id=sample_user.id,
            case_id=sample_case.id,
            name="My Rack",
            description="Test rack",
        )
        db_session.add(rack)
        db_session.commit()

        assert rack.id is not None
        assert rack.user_id == sample_user.id
        assert rack.case_id == sample_case.id
        assert rack.name == "My Rack"

    def test_rack_user_relationship(
        self, db_session: Session, sample_user: User, sample_case: Case
    ):
        """Test rack-user relationship."""
        rack = Rack(
            user_id=sample_user.id,
            case_id=sample_case.id,
            name="Test Rack",
        )
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        assert rack.user.id == sample_user.id
        assert rack.user.username == sample_user.username

    def test_rack_case_relationship(
        self, db_session: Session, sample_user: User, sample_case: Case
    ):
        """Test rack-case relationship."""
        rack = Rack(
            user_id=sample_user.id,
            case_id=sample_case.id,
            name="Test Rack",
        )
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        assert rack.case.id == sample_case.id
        assert rack.case.name == sample_case.name

    def test_rack_user_id_required(self, db_session: Session, sample_case: Case):
        """Test that user_id is required."""
        rack = Rack(
            case_id=sample_case.id,
            name="Test Rack",
        )
        db_session.add(rack)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_rack_case_id_optional(self, db_session: Session, sample_user: User):
        """A Rig started from a photo has no Case until its owner names one (spec 009)."""
        rack = Rack(
            user_id=sample_user.id,
            name="Test Rack",
        )
        db_session.add(rack)
        db_session.commit()
        db_session.refresh(rack)

        assert rack.case_id is None
        assert rack.case is None

    def test_rack_default_public_false(
        self, db_session: Session, sample_user: User, sample_case: Case
    ):
        """Test that is_public defaults to False."""
        rack = Rack(
            user_id=sample_user.id,
            case_id=sample_case.id,
            name="Test Rack",
        )
        db_session.add(rack)
        db_session.commit()

        assert rack.is_public is False

    def test_rack_tags_default_empty(
        self, db_session: Session, sample_user: User, sample_case: Case
    ):
        """Test that tags default to empty list."""
        rack = Rack(
            user_id=sample_user.id,
            case_id=sample_case.id,
            name="Test Rack",
        )
        db_session.add(rack)
        db_session.commit()

        assert rack.tags == []


class TestRackModuleModel:
    """Tests for RackModule model (module placement in rack)."""

    def test_create_rack_module(
        self, db_session: Session, sample_rack_empty: Rack, sample_vco: Module
    ):
        """Test creating a rack module placement."""
        rm = RackModule(
            rack_id=sample_rack_empty.id,
            module_id=sample_vco.id,
            row_index=0,
            start_hp=0,
        )
        db_session.add(rm)
        db_session.commit()

        assert rm.id is not None
        assert rm.rack_id == sample_rack_empty.id
        assert rm.module_id == sample_vco.id
        assert rm.row_index == 0
        assert rm.start_hp == 0

    def test_rack_module_relationship(
        self, db_session: Session, sample_rack_empty: Rack, sample_vco: Module
    ):
        """Test rack module relationships."""
        rm = RackModule(
            rack_id=sample_rack_empty.id,
            module_id=sample_vco.id,
            row_index=0,
            start_hp=0,
        )
        db_session.add(rm)
        db_session.commit()
        db_session.refresh(rm)

        assert rm.rack.id == sample_rack_empty.id
        assert rm.module.id == sample_vco.id
        assert rm.module.name == sample_vco.name

    def test_rack_id_required(self, db_session: Session, sample_vco: Module):
        """Test that rack_id is required."""
        rm = RackModule(
            module_id=sample_vco.id,
            row_index=0,
            start_hp=0,
        )
        db_session.add(rm)

        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_module_id_required(self, db_session: Session, sample_rack_empty: Rack):
        """Test that module_id is required."""
        rm = RackModule(
            rack_id=sample_rack_empty.id,
            row_index=0,
            start_hp=0,
        )
        db_session.add(rm)

        with pytest.raises(IntegrityError):
            db_session.commit()


class TestVoteModel:
    """Tests for Vote model."""

    def test_create_upvote(self, db_session: Session, sample_user: User, sample_rack_basic: Rack):
        """Test creating a vote on a patch."""
        from patches.models import Patch

        # Create a patch first
        patch = Patch(
            rack_id=sample_rack_basic.id,
            name="Test Patch",
            category="Voice",
            connections=[],
            generation_seed=42,
            generation_version="v1.0",
        )
        db_session.add(patch)
        db_session.commit()

        vote = Vote(
            user_id=sample_user.id,
            patch_id=patch.id,
        )
        db_session.add(vote)
        db_session.commit()

        assert vote.id is not None
        assert vote.user_id == sample_user.id
        assert vote.patch_id == patch.id

    def test_create_vote_on_rack(
        self, db_session: Session, sample_user: User, sample_rack_basic: Rack
    ):
        """Test creating a vote on a rack."""
        vote = Vote(
            user_id=sample_user.id,
            rack_id=sample_rack_basic.id,
        )
        db_session.add(vote)
        db_session.commit()

        assert vote.id is not None
        assert vote.user_id == sample_user.id
        assert vote.rack_id == sample_rack_basic.id

    def test_vote_unique_per_user_patch(
        self, db_session: Session, sample_user: User, sample_rack_basic: Rack
    ):
        """Test that each user can only vote once per patch."""
        from patches.models import Patch

        patch = Patch(
            rack_id=sample_rack_basic.id,
            name="Test Patch",
            category="Voice",
            connections=[],
            generation_seed=42,
            generation_version="v1.0",
        )
        db_session.add(patch)
        db_session.commit()

        vote1 = Vote(
            user_id=sample_user.id,
            patch_id=patch.id,
        )
        db_session.add(vote1)
        db_session.commit()

        # Try to vote again on same patch
        vote2 = Vote(
            user_id=sample_user.id,
            patch_id=patch.id,
        )
        db_session.add(vote2)

        with pytest.raises(IntegrityError):
            db_session.commit()


class TestCommentModel:
    """Tests for Comment model."""

    def test_create_comment(self, db_session: Session, sample_user: User, sample_rack_basic: Rack):
        """Test creating a comment."""
        from patches.models import Patch

        patch = Patch(
            rack_id=sample_rack_basic.id,
            name="Test Patch",
            category="Voice",
            connections=[],
            generation_seed=42,
            generation_version="v1.0",
        )
        db_session.add(patch)
        db_session.commit()

        comment = Comment(
            user_id=sample_user.id,
            patch_id=patch.id,
            content="Great patch!",
        )
        db_session.add(comment)
        db_session.commit()

        assert comment.id is not None
        assert comment.user_id == sample_user.id
        assert comment.patch_id == patch.id
        assert comment.content == "Great patch!"

    def test_comment_timestamps(
        self, db_session: Session, sample_user: User, sample_rack_basic: Rack
    ):
        """Test that comment timestamps are set."""
        from patches.models import Patch

        patch = Patch(
            rack_id=sample_rack_basic.id,
            name="Test Patch",
            category="Voice",
            connections=[],
            generation_seed=42,
            generation_version="v1.0",
        )
        db_session.add(patch)
        db_session.commit()

        comment = Comment(
            user_id=sample_user.id,
            patch_id=patch.id,
            content="Test comment",
        )
        db_session.add(comment)
        db_session.commit()

        assert comment.created_at is not None
        assert isinstance(comment.created_at, datetime)


class TestCascadeDeletes:
    """Tests for cascade delete behavior."""

    def test_delete_user_cascades_to_racks(
        self, db_session: Session, sample_user: User, sample_case: Case
    ):
        """Test that deleting a user deletes their racks."""
        rack = Rack(
            user_id=sample_user.id,
            case_id=sample_case.id,
            name="Test Rack",
        )
        db_session.add(rack)
        db_session.commit()

        rack_id = rack.id

        # Delete user
        db_session.delete(sample_user)
        db_session.commit()

        # Rack should be deleted
        deleted_rack = db_session.query(Rack).filter(Rack.id == rack_id).first()
        assert deleted_rack is None

    def test_delete_rack_cascades_to_modules(
        self, db_session: Session, sample_rack_empty: Rack, sample_vco: Module
    ):
        """Test that deleting a rack deletes rack modules."""
        rm = RackModule(
            rack_id=sample_rack_empty.id,
            module_id=sample_vco.id,
            row_index=0,
            start_hp=0,
        )
        db_session.add(rm)
        db_session.commit()

        rm_id = rm.id

        # Delete rack
        db_session.delete(sample_rack_empty)
        db_session.commit()

        # RackModule should be deleted
        deleted_rm = db_session.query(RackModule).filter(RackModule.id == rm_id).first()
        assert deleted_rm is None

    def test_delete_case_cascades_to_racks(
        self, db_session: Session, sample_user: User, sample_case: Case
    ):
        """Test that deleting a case deletes racks using it."""
        rack = Rack(
            user_id=sample_user.id,
            case_id=sample_case.id,
            name="Test Rack",
        )
        db_session.add(rack)
        db_session.commit()

        rack_id = rack.id

        # Delete case
        db_session.delete(sample_case)
        db_session.commit()

        # Rack should be deleted
        deleted_rack = db_session.query(Rack).filter(Rack.id == rack_id).first()
        assert deleted_rack is None
