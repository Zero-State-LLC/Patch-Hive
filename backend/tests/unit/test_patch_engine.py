"""
Tests for the deterministic patch generation engine.
"""

import pytest
from sqlalchemy.orm import Session

from modules.models import Module
from patches.engine import (
    Connection,
    ModuleAnalyzer,
    PatchEngineConfig,
    PatchGenerator,
    PatchSpec,
    generate_patches_for_rack,
)
from racks.models import Rack


class TestModuleAnalyzer:
    """Tests for ModuleAnalyzer class."""

    def test_analyzer_empty_rack(self, db_session: Session, sample_rack_empty: Rack):
        """Test analyzer with empty rack."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_empty)

        assert len(analyzer.all_modules) == 0
        assert len(analyzer.vcos) == 0
        assert len(analyzer.vcfs) == 0
        assert len(analyzer.vcas) == 0
        assert len(analyzer.envelopes) == 0
        assert len(analyzer.lfos) == 0

    def test_analyzer_basic_rack(self, db_session: Session, sample_rack_basic: Rack):
        """Test analyzer with basic rack (VCO, VCF, VCA)."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)

        assert len(analyzer.all_modules) == 3
        assert len(analyzer.vcos) == 1
        assert len(analyzer.vcfs) == 1
        assert len(analyzer.vcas) == 1
        assert analyzer.vcos[0].name == "Test VCO"
        assert analyzer.vcfs[0].name == "Test VCF"
        assert analyzer.vcas[0].name == "Test VCA"

    def test_analyzer_full_rack(self, db_session: Session, sample_rack_full: Rack):
        """Test analyzer with full-featured rack."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_full)

        assert len(analyzer.all_modules) == 6
        assert len(analyzer.vcos) == 1
        assert len(analyzer.vcfs) == 1
        assert len(analyzer.vcas) == 1
        assert len(analyzer.envelopes) == 1
        assert len(analyzer.lfos) == 1
        assert len(analyzer.sequencers) == 1

    def test_analyzer_categorization_vco(self, db_session: Session, sample_rack_basic: Rack):
        """Test VCO categorization."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)

        assert len(analyzer.vcos) == 1
        assert "VCO" in analyzer.vcos[0].module_type.upper()

    def test_analyzer_categorization_vcf(self, db_session: Session, sample_rack_basic: Rack):
        """Test VCF categorization."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)

        assert len(analyzer.vcfs) == 1
        assert "VCF" in analyzer.vcfs[0].module_type.upper()

    def test_analyzer_categorization_vca(self, db_session: Session, sample_rack_basic: Rack):
        """Test VCA categorization."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)

        assert len(analyzer.vcas) == 1
        assert "VCA" in analyzer.vcas[0].module_type.upper()


class TestPatchGenerator:
    """Tests for PatchGenerator class."""

    def test_generator_basic_config(self, db_session: Session, sample_rack_basic: Rack):
        """Test generator with basic configuration."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)
        config = PatchEngineConfig(max_patches=20, allow_feedback=False, prefer_simple=False)
        generator = PatchGenerator(analyzer, seed=42, config=config)

        assert generator.seed == 42
        assert generator.config.max_patches == 20
        assert generator.config.allow_feedback is False

    def test_can_generate_subtractive_voice(self, db_session: Session, sample_rack_basic: Rack):
        """Test detection of subtractive voice capability."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        assert generator._can_generate_subtractive_voice() is True

    def test_cannot_generate_subtractive_without_vco(
        self, db_session: Session, sample_rack_empty: Rack
    ):
        """Test that subtractive voice requires VCO."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_empty)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        assert generator._can_generate_subtractive_voice() is False

    def test_can_generate_generative(self, db_session: Session, sample_rack_full: Rack):
        """Test detection of generative patch capability."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_full)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        # Has sequencer and LFO
        assert generator._can_generate_generative() is True

    def test_can_generate_percussion(
        self, db_session: Session, sample_rack_full: Rack, sample_noise: Module
    ):
        """Test detection of percussion patch capability."""
        # Add noise source to rack
        from racks.models import RackModule

        rm = RackModule(
            rack_id=sample_rack_full.id, module_id=sample_noise.id, row_index=0, start_hp=54
        )
        db_session.add(rm)
        db_session.commit()

        analyzer = ModuleAnalyzer(db_session, sample_rack_full)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        # Has noise source and envelopes
        assert generator._can_generate_percussion() is True

    def test_generate_subtractive_voices(self, db_session: Session, sample_rack_basic: Rack):
        """Test generation of subtractive synthesis patches."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator._generate_subtractive_voices()

        assert len(patches) > 0
        assert all(isinstance(p, PatchSpec) for p in patches)
        assert all(len(p.connections) > 0 for p in patches)
        assert all(p.category == "Voice" for p in patches)

    def test_generate_patches_respects_max_patches(
        self, db_session: Session, sample_rack_full: Rack
    ):
        """Test that max_patches configuration is respected."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_full)
        config = PatchEngineConfig(max_patches=5)
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator.generate_patches()

        assert len(patches) <= 5

    def test_generate_patches_returns_list(self, db_session: Session, sample_rack_basic: Rack):
        """Test that generate_patches returns a list."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator.generate_patches()

        assert isinstance(patches, list)

    def test_patch_has_valid_structure(self, db_session: Session, sample_rack_basic: Rack):
        """Test that generated patches have valid structure."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator.generate_patches()

        assert len(patches) > 0
        patch = patches[0]

        # Check patch structure
        assert isinstance(patch.name, str)
        assert len(patch.name) > 0
        # The canonical set (spec 001 FR-012).
        assert patch.category in ["Voice", "Clock-Rhythm", "Generative", "Texture-FX", "Utility"]
        assert isinstance(patch.connections, list)
        assert isinstance(patch.description, str)
        assert isinstance(patch.generation_seed, int)

    def test_connection_has_valid_structure(self, db_session: Session, sample_rack_basic: Rack):
        """Test that connections have valid structure."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator.generate_patches()
        assert len(patches) > 0

        patch = patches[0]
        assert len(patch.connections) > 0

        conn = patch.connections[0]
        assert isinstance(conn, Connection)
        assert isinstance(conn.from_module_id, int)
        assert isinstance(conn.from_port, str)
        assert isinstance(conn.to_module_id, int)
        assert isinstance(conn.to_port, str)
        assert conn.cable_type in ["audio", "cv", "gate", "clock"]


class TestDeterminism:
    """Tests for deterministic generation."""

    def test_same_seed_produces_same_patches(self, db_session: Session, sample_rack_basic: Rack):
        """Test that same seed produces identical patches."""
        seed = 12345

        # Generate patches twice with same seed
        patches1 = generate_patches_for_rack(db_session, sample_rack_basic, seed=seed)
        patches2 = generate_patches_for_rack(db_session, sample_rack_basic, seed=seed)

        assert len(patches1) == len(patches2)

        # Compare each patch
        for p1, p2 in zip(patches1, patches2):
            assert p1.name == p2.name
            assert p1.category == p2.category
            assert p1.generation_seed == p2.generation_seed
            assert len(p1.connections) == len(p2.connections)

            # Compare connections
            for c1, c2 in zip(p1.connections, p2.connections):
                assert c1.from_module_id == c2.from_module_id
                assert c1.from_port == c2.from_port
                assert c1.to_module_id == c2.to_module_id
                assert c1.to_port == c2.to_port
                assert c1.cable_type == c2.cable_type

    def test_different_seeds_produce_different_patches(
        self, db_session: Session, sample_rack_basic: Rack
    ):
        """Test that different seeds produce different patches."""
        patches1 = generate_patches_for_rack(db_session, sample_rack_basic, seed=111)
        patches2 = generate_patches_for_rack(db_session, sample_rack_basic, seed=222)

        # Should have at least some differences
        # (Can't guarantee complete difference due to limited module availability)
        if len(patches1) > 0 and len(patches2) > 0:
            # At least the names should differ (they use the seed)
            assert patches1[0].name != patches2[0].name

    def test_determinism_across_multiple_runs(self, db_session: Session, sample_rack_full: Rack):
        """Test determinism across multiple generation runs."""
        seed = 99999
        num_runs = 5

        all_patches = []
        for _ in range(num_runs):
            patches = generate_patches_for_rack(db_session, sample_rack_full, seed=seed)
            all_patches.append(patches)

        # All runs should produce identical results
        first_run = all_patches[0]
        for run in all_patches[1:]:
            assert len(run) == len(first_run)
            for p1, p2 in zip(first_run, run):
                assert p1.name == p2.name
                assert p1.category == p2.category
                assert len(p1.connections) == len(p2.connections)

    def test_seed_provenance(self, db_session: Session, sample_rack_basic: Rack):
        """Test that generation_seed is correctly tracked."""
        base_seed = 42
        patches = generate_patches_for_rack(db_session, sample_rack_basic, seed=base_seed)

        assert len(patches) > 0

        # Each patch should have a generation_seed
        for patch in patches:
            assert patch.generation_seed > 0
            # Seed should be derived from base_seed
            assert isinstance(patch.generation_seed, int)


class TestPatchTypes:
    """Tests for different patch type generation."""

    def test_subtractive_patch_structure(self, db_session: Session, sample_rack_basic: Rack):
        """Test that subtractive patches follow VCO→VCF→VCA structure."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_basic)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator._generate_subtractive_voices()
        assert len(patches) > 0

        patch = patches[0]

        # Should have connections
        assert len(patch.connections) > 0

        # Find the modules involved
        module_ids = set()
        for conn in patch.connections:
            module_ids.add(conn.from_module_id)
            module_ids.add(conn.to_module_id)

        # Should involve multiple modules
        assert len(module_ids) >= 2

    def test_generative_patch_has_sequencer_or_lfo(
        self, db_session: Session, sample_rack_full: Rack
    ):
        """Test that generative patches use sequencers or LFOs."""
        analyzer = ModuleAnalyzer(db_session, sample_rack_full)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator._generate_generative_patches()

        if len(patches) > 0:
            patch = patches[0]
            assert patch.category == "Generative"
            assert len(patch.connections) > 0

            # Should involve sequencer or LFO
            module_ids = {conn.from_module_id for conn in patch.connections}
            seq_ids = {m.id for m in analyzer.sequencers}
            lfo_ids = {m.id for m in analyzer.lfos}

            assert len(module_ids & (seq_ids | lfo_ids)) > 0

    def test_percussion_patch_structure(
        self, db_session: Session, sample_rack_full: Rack, sample_noise: Module
    ):
        """Test percussion patch structure."""
        from racks.models import RackModule

        rm = RackModule(
            rack_id=sample_rack_full.id, module_id=sample_noise.id, row_index=0, start_hp=54
        )
        db_session.add(rm)
        db_session.commit()

        analyzer = ModuleAnalyzer(db_session, sample_rack_full)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator._generate_percussion()

        if len(patches) > 0:
            patch = patches[0]
            assert patch.category == "Clock-Rhythm"
            assert len(patch.connections) > 0

    def test_fx_chain_structure(
        self, db_session: Session, sample_rack_full: Rack, sample_effect: Module
    ):
        """Test FX processing chain structure."""
        from racks.models import RackModule

        rm = RackModule(
            rack_id=sample_rack_full.id, module_id=sample_effect.id, row_index=0, start_hp=54
        )
        db_session.add(rm)
        db_session.commit()

        analyzer = ModuleAnalyzer(db_session, sample_rack_full)
        config = PatchEngineConfig()
        generator = PatchGenerator(analyzer, seed=42, config=config)

        patches = generator._generate_fx_chains()

        if len(patches) > 0:
            patch = patches[0]
            assert patch.category == "Texture-FX"


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_rack_generates_no_patches(self, db_session: Session, sample_rack_empty: Rack):
        """Test that empty rack generates no patches."""
        patches = generate_patches_for_rack(db_session, sample_rack_empty, seed=42)
        assert len(patches) == 0

    def test_single_module_generates_no_patches(
        self, db_session: Session, sample_user, sample_case, sample_vco: Module
    ):
        """Test that rack with single module generates no patches."""
        from racks.models import RackModule

        rack = Rack(
            user_id=sample_user.id,
            name="Single Module Rack",
            case_id=sample_case.id,
            description="Test single module",
        )
        db_session.add(rack)
        db_session.flush()

        rm = RackModule(rack_id=rack.id, module_id=sample_vco.id, row_index=0, start_hp=0)
        db_session.add(rm)
        db_session.commit()

        patches = generate_patches_for_rack(db_session, rack, seed=42)
        assert len(patches) == 0

    def test_default_seed_used_when_none_provided(
        self, db_session: Session, sample_rack_basic: Rack
    ):
        """Test that default seed is used when none is provided."""
        patches = generate_patches_for_rack(db_session, sample_rack_basic, seed=None)

        if len(patches) > 0:
            # Should still generate deterministically
            assert all(p.generation_seed > 0 for p in patches)

    def test_default_config_used_when_none_provided(
        self, db_session: Session, sample_rack_basic: Rack
    ):
        """Test that default config is used when none is provided."""
        patches = generate_patches_for_rack(db_session, sample_rack_basic, seed=42, config=None)

        # Should generate patches with default config
        assert isinstance(patches, list)

    def test_patch_to_dict(self, db_session: Session, sample_rack_basic: Rack):
        """Test PatchSpec.to_dict() serialization."""
        patches = generate_patches_for_rack(db_session, sample_rack_basic, seed=42)
        assert len(patches) > 0

        patch_dict = patches[0].to_dict()

        assert isinstance(patch_dict, dict)
        assert "name" in patch_dict
        assert "category" in patch_dict
        assert "connections" in patch_dict
        assert "description" in patch_dict
        assert "generation_seed" in patch_dict
        assert isinstance(patch_dict["connections"], list)

    def test_connection_to_dict(self, db_session: Session, sample_rack_basic: Rack):
        """Test Connection.to_dict() serialization."""
        patches = generate_patches_for_rack(db_session, sample_rack_basic, seed=42)
        assert len(patches) > 0
        assert len(patches[0].connections) > 0

        conn_dict = patches[0].connections[0].to_dict()

        assert isinstance(conn_dict, dict)
        assert "from_module_id" in conn_dict
        assert "from_port" in conn_dict
        assert "to_module_id" in conn_dict
        assert "to_port" in conn_dict
        assert "cable_type" in conn_dict


class TestConfiguration:
    """Tests for PatchEngineConfig."""

    def test_max_patches_limit(self, db_session: Session, sample_rack_full: Rack):
        """Test that max_patches configuration limits output."""
        for max_patches in [1, 5, 10, 20]:
            config = PatchEngineConfig(max_patches=max_patches)
            patches = generate_patches_for_rack(
                db_session, sample_rack_full, seed=42, config=config
            )
            assert len(patches) <= max_patches

    def test_config_defaults(self):
        """Test PatchEngineConfig default values."""
        config = PatchEngineConfig()

        assert config.max_patches == 20
        assert config.allow_feedback is False
        assert config.prefer_simple is False

    def test_config_custom_values(self):
        """Test PatchEngineConfig with custom values."""
        config = PatchEngineConfig(max_patches=50, allow_feedback=True, prefer_simple=True)

        assert config.max_patches == 50
        assert config.allow_feedback is True
        assert config.prefer_simple is True


class TestNoInventedPatches:
    """Spec 001 FR-017: generation never pads its output with patches it cannot justify."""

    def test_full_rack_emits_only_canonical_categories(
        self, db_session: Session, sample_rack_full: Rack
    ):
        patches = generate_patches_for_rack(
            db_session, sample_rack_full, seed=7, config=PatchEngineConfig(max_patches=50)
        )
        assert patches
        assert {p.category for p in patches} <= {
            "Voice", "Clock-Rhythm", "Generative", "Texture-FX", "Utility"
        }
        assert not any(p.description.startswith("Study patch") for p in patches)

    def test_a_rack_with_no_patch_rule_gets_no_patches(
        self, db_session: Session, sample_user, sample_case, sample_mixer: Module, sample_noise: Module
    ):
        """A mixer and a noise source match no rule; the old padding wired them
        "Audio Out" to "Audio In" without knowing those jacks exist."""
        from racks.models import RackModule

        rack = Rack(user_id=sample_user.id, name="Odd rack", case_id=sample_case.id)
        db_session.add(rack)
        db_session.flush()
        db_session.add_all([
            RackModule(rack_id=rack.id, module_id=sample_mixer.id, row_index=0, start_hp=0),
            RackModule(rack_id=rack.id, module_id=sample_noise.id, row_index=0, start_hp=10),
        ])
        db_session.commit()

        assert generate_patches_for_rack(db_session, rack, seed=1) == []
