"""
Deterministic Patch Generation Engine.
Generates plausible patch configurations based on module types and connections.

ABX-Core v1.3: This engine now produces first-class IR objects and full provenance
tracking for every generation run. The IR is serializable and replayable.
"""

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from cases.models import Case
from core import (
    ConnectionIR,
    ModuleIR,
    PatchGenerationIR,
    PatchGenerationParams,
    PatchCategory,
    PatchGraphIR,
    Provenance,
    RackStateIR,
    get_git_commit,
    name_patch_v2,
    settings,
)
from modules.models import Module
from racks.models import Rack, RackModule



@dataclass
class Connection:
    """Represents a cable connection between two module ports."""

    from_module_id: int
    from_port: str
    to_module_id: int
    to_port: str
    cable_type: str  # "audio", "cv", "gate", "clock"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_module_id": self.from_module_id,
            "from_port": self.from_port,
            "to_module_id": self.to_module_id,
            "to_port": self.to_port,
            "cable_type": self.cable_type,
        }


@dataclass
class PatchSpec:
    """Specification for a patch."""

    name: str
    category: PatchCategory
    connections: List[Connection] = field(default_factory=list)
    description: str = ""
    generation_seed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "connections": [c.to_dict() for c in self.connections],
            "description": self.description,
            "generation_seed": self.generation_seed,
        }


@dataclass
class PatchEngineConfig:
    """Configuration for patch generation."""

    max_patches: int = 20
    allow_feedback: bool = False
    prefer_simple: bool = False


class ModuleAnalyzer:
    """Analyzes modules in a rack to categorize them by function."""

    def __init__(self, db: Session, rack: Rack):
        self.db = db
        self.rack = rack
        self._analyze()

    def _analyze(self) -> None:
        """Categorize modules by type."""
        rack_modules = self.db.query(RackModule).filter(RackModule.rack_id == self.rack.id).all()

        self.all_modules: List[Module] = []
        self.vcos: List[Module] = []
        self.vcfs: List[Module] = []
        self.vcas: List[Module] = []
        self.envelopes: List[Module] = []
        self.lfos: List[Module] = []
        self.sequencers: List[Module] = []
        self.mixers: List[Module] = []
        self.effects: List[Module] = []
        self.utilities: List[Module] = []
        self.noise_sources: List[Module] = []

        for rm in rack_modules:
            module = self.db.query(Module).filter(Module.id == rm.module_id).first()
            if not module:
                continue

            self.all_modules.append(module)

            # Categorize by type
            mtype = module.module_type.upper()
            if "VCO" in mtype or "OSCILLATOR" in mtype:
                self.vcos.append(module)
            if "VCF" in mtype or "FILTER" in mtype:
                self.vcfs.append(module)
            if "VCA" in mtype or "AMPLIFIER" in mtype:
                self.vcas.append(module)
            if "ENV" in mtype or "ENVELOPE" in mtype or "ADSR" in mtype:
                self.envelopes.append(module)
            if "LFO" in mtype:
                self.lfos.append(module)
            if "SEQ" in mtype or "SEQUENCER" in mtype:
                self.sequencers.append(module)
            if "MIX" in mtype or "MIXER" in mtype:
                self.mixers.append(module)
            if "FX" in mtype or "EFFECT" in mtype or "REVERB" in mtype or "DELAY" in mtype:
                self.effects.append(module)
            if "UTIL" in mtype or "MULT" in mtype:
                self.utilities.append(module)
            if "NOISE" in mtype:
                self.noise_sources.append(module)


class PatchGenerator:
    """Generates patches based on module availability."""

    def __init__(self, analyzer: ModuleAnalyzer, seed: int, config: PatchEngineConfig):
        self.analyzer = analyzer
        self.seed = seed
        self.config = config
        self.rng = random.Random(seed)
        self.modules_by_id = {module.id: module for module in analyzer.all_modules}

    def generate_patches(self) -> List[PatchSpec]:
        """Generate all possible patches for the rack."""
        patches: List[PatchSpec] = []

        # Try different patch types based on available modules
        if self._can_generate_subtractive_voice():
            patches.extend(self._generate_subtractive_voices())

        if self._can_generate_generative():
            patches.extend(self._generate_generative_patches())

        if self._can_generate_percussion():
            patches.extend(self._generate_percussion())

        if self._can_generate_fx_chain():
            patches.extend(self._generate_fx_chains())

        # Further rules (issue #95). Each needs every module it wires, draws from its
        # own seeded generator, and runs after the rules above, so their output is
        # unchanged for any rack.
        patches.extend(self._generate_sequenced_voices())
        patches.extend(self._generate_plucked_voice())
        patches.extend(self._generate_filter_drone())
        patches.extend(self._generate_sequenced_hats())
        patches.extend(self._generate_voice_through_fx())
        patches.extend(self._generate_oscillator_mix())

        # No padding to reach max_patches: a patch the rules above cannot justify would
        # have to invent its jacks (spec 001 FR-017). Fewer patches, or none, is honest.
        if self.config.prefer_simple:
            # Stable sort: patches with equal cable counts keep their generation order.
            patches.sort(key=lambda patch: len(patch.connections))
        # Limit to max patches
        return patches[: self.config.max_patches]

    def _can_generate_subtractive_voice(self) -> bool:
        """Check if we can generate a basic subtractive synthesis voice."""
        return len(self.analyzer.vcos) > 0 and len(self.analyzer.vcas) > 0

    def _generate_subtractive_voices(self) -> List[PatchSpec]:
        """Generate subtractive synthesis patches."""
        patches: List[PatchSpec] = []

        for i, vco in enumerate(self.analyzer.vcos[: min(3, len(self.analyzer.vcos))]):
            connections: List[Connection] = []

            # VCO → VCF → VCA → OUT (if filter available, otherwise VCO → VCA)
            current_module = vco

            # Optional filter
            if self.analyzer.vcfs:
                vcf = self.rng.choice(self.analyzer.vcfs)
                connections.append(
                    Connection(
                        from_module_id=current_module.id,
                        from_port="Audio Out",
                        to_module_id=vcf.id,
                        to_port="Audio In",
                        cable_type="audio",
                    )
                )
                current_module = vcf

            # VCA (required)
            if self.analyzer.vcas:
                vca = self.rng.choice(self.analyzer.vcas)
                connections.append(
                    Connection(
                        from_module_id=current_module.id,
                        from_port="Audio Out",
                        to_module_id=vca.id,
                        to_port="Audio In",
                        cable_type="audio",
                    )
                )

                # Envelope to VCA
                if self.analyzer.envelopes:
                    env = self.rng.choice(self.analyzer.envelopes)
                    connections.append(
                        Connection(
                            from_module_id=env.id,
                            from_port="Envelope Out",
                            to_module_id=vca.id,
                            to_port="CV In",
                            cable_type="cv",
                        )
                    )

            # LFO modulation (50% chance)
            if self.analyzer.lfos and self.rng.random() > 0.5:
                lfo = self.rng.choice(self.analyzer.lfos)
                target = self.rng.choice([vco, current_module])
                connections.append(
                    Connection(
                        from_module_id=lfo.id,
                        from_port="LFO Out",
                        to_module_id=target.id,
                        to_port="CV In",
                        cable_type="cv",
                    )
                )

            # Determine category based on envelope characteristics
            category: PatchCategory = "Voice"

            patch_seed = self.seed + i
            patch = PatchSpec(
                name=name_patch_v2(patch_seed, self.modules_by_id, connections),
                category=category,
                connections=connections,
                description=f"Subtractive synthesis voice using {vco.name}",
                generation_seed=patch_seed,
            )
            patches.append(patch)

        return patches

    def _can_generate_generative(self) -> bool:
        """Check if we can generate generative patches."""
        return len(self.analyzer.sequencers) > 0 or len(self.analyzer.lfos) > 1

    def _generate_generative_patches(self) -> List[PatchSpec]:
        """Generate generative/evolving patches."""
        patches: List[PatchSpec] = []

        if not self.analyzer.sequencers and not self.analyzer.lfos:
            return patches

        connections: List[Connection] = []

        # Use sequencer or LFO as clock/modulation source
        if self.analyzer.sequencers:
            seq = self.rng.choice(self.analyzer.sequencers)

            # Sequence to VCO pitch
            if self.analyzer.vcos:
                vco = self.rng.choice(self.analyzer.vcos)
                connections.append(
                    Connection(
                        from_module_id=seq.id,
                        from_port="CV Out",
                        to_module_id=vco.id,
                        to_port="V/Oct",
                        cable_type="cv",
                    )
                )

        # Multiple LFOs for generative modulation
        if len(self.analyzer.lfos) >= 2:
            lfo1, lfo2 = self.analyzer.lfos[0], self.analyzer.lfos[1]

            if self.analyzer.vcos:
                vco = self.rng.choice(self.analyzer.vcos)
                connections.append(
                    Connection(
                        from_module_id=lfo1.id,
                        from_port="LFO Out",
                        to_module_id=vco.id,
                        to_port="FM In",
                        cable_type="cv",
                    )
                )

            if self.analyzer.vcfs:
                vcf = self.rng.choice(self.analyzer.vcfs)
                connections.append(
                    Connection(
                        from_module_id=lfo2.id,
                        from_port="LFO Out",
                        to_module_id=vcf.id,
                        to_port="Cutoff CV",
                        cable_type="cv",
                    )
                )

        if connections:
            patch_seed = self.seed + 1000
            patch = PatchSpec(
                name=name_patch_v2(patch_seed, self.modules_by_id, connections),
                category="Generative",
                connections=connections,
                description="Self-evolving generative patch with modulation",
                generation_seed=patch_seed,
            )
            patches.append(patch)

        return patches

    def _can_generate_percussion(self) -> bool:
        """Check if we can generate percussion patches."""
        return len(self.analyzer.noise_sources) > 0 or len(self.analyzer.envelopes) > 0

    def _generate_percussion(self) -> List[PatchSpec]:
        """Generate percussion-style patches."""
        patches: List[PatchSpec] = []

        if not (self.analyzer.noise_sources or self.analyzer.envelopes):
            return patches

        connections: List[Connection] = []

        # Noise → VCF → VCA (classic snare/hi-hat)
        if self.analyzer.noise_sources and self.analyzer.vcas:
            noise = self.analyzer.noise_sources[0]
            vca = self.rng.choice(self.analyzer.vcas)

            if self.analyzer.vcfs:
                vcf = self.rng.choice(self.analyzer.vcfs)
                connections.append(
                    Connection(
                        from_module_id=noise.id,
                        from_port="Noise Out",
                        to_module_id=vcf.id,
                        to_port="Audio In",
                        cable_type="audio",
                    )
                )
                connections.append(
                    Connection(
                        from_module_id=vcf.id,
                        from_port="Audio Out",
                        to_module_id=vca.id,
                        to_port="Audio In",
                        cable_type="audio",
                    )
                )
            else:
                connections.append(
                    Connection(
                        from_module_id=noise.id,
                        from_port="Noise Out",
                        to_module_id=vca.id,
                        to_port="Audio In",
                        cable_type="audio",
                    )
                )

            # Short envelope
            if self.analyzer.envelopes:
                env = self.analyzer.envelopes[0]
                connections.append(
                    Connection(
                        from_module_id=env.id,
                        from_port="Envelope Out",
                        to_module_id=vca.id,
                        to_port="CV In",
                        cable_type="cv",
                    )
                )

        if connections:
            patch_seed = self.seed + 2000
            patch = PatchSpec(
                name=name_patch_v2(patch_seed, self.modules_by_id, connections),
                category="Clock-Rhythm",
                connections=connections,
                description="Clock-Rhythm voice using noise and envelope",
                generation_seed=patch_seed,
            )
            patches.append(patch)

        return patches

    def _can_generate_fx_chain(self) -> bool:
        """Check if we can generate FX processing chains."""
        return len(self.analyzer.effects) > 0

    def _generate_fx_chains(self) -> List[PatchSpec]:
        """Generate FX processing patches."""
        patches: List[PatchSpec] = []

        if not self.analyzer.effects:
            return patches

        connections: List[Connection] = []

        # Simple FX chain: IN → FX → OUT
        fx = self.analyzer.effects[0]

        # If there's a mixer, use it
        if self.analyzer.mixers:
            mixer = self.analyzer.mixers[0]
            connections.append(
                Connection(
                    from_module_id=mixer.id,
                    from_port="Mix Out",
                    to_module_id=fx.id,
                    to_port="FX In",
                    cable_type="audio",
                )
            )

        if connections:
            patch_seed = self.seed + 3000
            patch = PatchSpec(
                name=name_patch_v2(patch_seed, self.modules_by_id, connections),
                category="Texture-FX",
                connections=connections,
                description=f"Texture-FX processing chain using {fx.name}",
                generation_seed=patch_seed,
            )
            patches.append(patch)

        return patches


    # --- Further rules (issue #95) -------------------------------------------------

    def _rule_rng(self, offset: int) -> random.Random:
        return random.Random(self.seed + offset)

    def _audio(self, src: Module, dst: Module, from_port: str = "Audio Out") -> Connection:
        return Connection(
            from_module_id=src.id, from_port=from_port, to_module_id=dst.id,
            to_port="Audio In", cable_type="audio",
        )

    def _cv(self, src: Module, from_port: str, dst: Module, to_port: str) -> Connection:
        return Connection(
            from_module_id=src.id, from_port=from_port, to_module_id=dst.id,
            to_port=to_port, cable_type="cv",
        )

    def _gate(self, src: Module, dst: Module) -> Connection:
        return Connection(
            from_module_id=src.id, from_port="Gate Out", to_module_id=dst.id,
            to_port="Gate In", cable_type="gate",
        )

    def _spec(
        self, patch_seed: int, category: PatchCategory, connections: List[Connection], description: str
    ) -> PatchSpec:
        return PatchSpec(
            name=name_patch_v2(patch_seed, self.modules_by_id, connections),
            category=category,
            connections=connections,
            description=description,
            generation_seed=patch_seed,
        )

    def _generate_sequenced_voices(self) -> List[PatchSpec]:
        """A sequencer plays each VCO (up to three): pitch to V/Oct, gate to an
        envelope that opens the VCA, through a filter when there is one."""
        a = self.analyzer
        if not (a.sequencers and a.vcos and a.vcas and a.envelopes):
            return []
        rng = self._rule_rng(5000)
        patches: List[PatchSpec] = []
        for i, vco in enumerate(a.vcos[:3]):
            seq, vca, env = rng.choice(a.sequencers), rng.choice(a.vcas), rng.choice(a.envelopes)
            connections = [self._cv(seq, "CV Out", vco, "V/Oct"), self._gate(seq, env)]
            if a.vcfs:
                vcf = rng.choice(a.vcfs)
                connections += [self._audio(vco, vcf), self._audio(vcf, vca)]
            else:
                connections.append(self._audio(vco, vca))
            connections.append(self._cv(env, "Envelope Out", vca, "CV In"))
            patches.append(
                self._spec(self.seed + 5000 + i, "Voice", connections, f"{seq.name} sequences {vco.name}")
            )
        return patches

    def _generate_plucked_voice(self) -> List[PatchSpec]:
        """One envelope shapes both the filter cutoff and the VCA: a plucked voice."""
        a = self.analyzer
        if not (a.vcos and a.vcfs and a.vcas and a.envelopes):
            return []
        rng = self._rule_rng(6000)
        vco, vcf, vca, env = (rng.choice(a.vcos), rng.choice(a.vcfs), rng.choice(a.vcas), rng.choice(a.envelopes))
        connections = [
            self._audio(vco, vcf),
            self._audio(vcf, vca),
            self._cv(env, "Envelope Out", vcf, "Cutoff CV"),
            self._cv(env, "Envelope Out", vca, "CV In"),
        ]
        return [self._spec(self.seed + 6000, "Voice", connections, f"Plucked voice: {env.name} shapes filter and level")]

    def _generate_filter_drone(self) -> List[PatchSpec]:
        """No envelope: an LFO slowly sweeps the filter over a sustained oscillator."""
        a = self.analyzer
        if not (a.vcos and a.vcfs and a.vcas and a.lfos):
            return []
        rng = self._rule_rng(7000)
        vco, vcf, vca, lfo = (rng.choice(a.vcos), rng.choice(a.vcfs), rng.choice(a.vcas), rng.choice(a.lfos))
        connections = [
            self._audio(vco, vcf),
            self._audio(vcf, vca),
            self._cv(lfo, "LFO Out", vcf, "Cutoff CV"),
        ]
        return [self._spec(self.seed + 7000, "Voice", connections, f"Drone: {lfo.name} sweeps {vcf.name}")]

    def _generate_sequenced_hats(self) -> List[PatchSpec]:
        """The sequencer's gate fires a short envelope on noise: a clocked hat."""
        a = self.analyzer
        if not (a.sequencers and a.envelopes and a.noise_sources and a.vcas):
            return []
        rng = self._rule_rng(8000)
        seq, env, noise, vca = (
            rng.choice(a.sequencers), rng.choice(a.envelopes), a.noise_sources[0], rng.choice(a.vcas),
        )
        connections = [self._gate(seq, env)]
        if a.vcfs:
            vcf = rng.choice(a.vcfs)
            connections += [self._audio(noise, vcf, "Noise Out"), self._audio(vcf, vca)]
        else:
            connections.append(self._audio(noise, vca, "Noise Out"))
        connections.append(self._cv(env, "Envelope Out", vca, "CV In"))
        return [self._spec(self.seed + 8000, "Clock-Rhythm", connections, f"{seq.name} clocks noise hits")]

    def _generate_voice_through_fx(self) -> List[PatchSpec]:
        """An oscillator through a VCA into the effect, with no mixer needed."""
        a = self.analyzer
        if not (a.vcos and a.vcas and a.effects):
            return []
        rng = self._rule_rng(9000)
        vco, vca, fx = rng.choice(a.vcos), rng.choice(a.vcas), a.effects[0]
        connections = [
            self._audio(vco, vca),
            Connection(
                from_module_id=vca.id, from_port="Audio Out", to_module_id=fx.id,
                to_port="FX In", cable_type="audio",
            ),
        ]
        return [self._spec(self.seed + 9000, "Texture-FX", connections, f"{vco.name} through {fx.name}")]

    def _generate_oscillator_mix(self) -> List[PatchSpec]:
        """Two oscillators blended in a mixer."""
        a = self.analyzer
        if not (len(a.vcos) >= 2 and a.mixers):
            return []
        first, second, mixer = a.vcos[0], a.vcos[1], a.mixers[0]
        connections = [
            Connection(
                from_module_id=first.id, from_port="Audio Out", to_module_id=mixer.id,
                to_port="In 1", cable_type="audio",
            ),
            Connection(
                from_module_id=second.id, from_port="Audio Out", to_module_id=mixer.id,
                to_port="In 2", cable_type="audio",
            ),
        ]
        return [self._spec(self.seed + 9500, "Utility", connections, f"{first.name} and {second.name} mixed")]


def generate_patches_for_rack(
    db: Session, rack: Rack, seed: Optional[int] = None, config: Optional[PatchEngineConfig] = None
) -> List[PatchSpec]:
    """
    Main entry point for patch generation.

    Args:
        db: Database session
        rack: Rack to generate patches for
        seed: Random seed for deterministic generation
        config: Engine configuration

    Returns:
        List of generated patch specifications
    """
    if seed is None:
        seed = settings.default_generation_seed

    if config is None:
        config = PatchEngineConfig()

    # Analyze rack modules
    analyzer = ModuleAnalyzer(db, rack)

    # Check if rack has enough modules
    if len(analyzer.all_modules) < 2:
        return []

    # Generate patches
    generator = PatchGenerator(analyzer, seed, config)
    patches = generator.generate_patches()

    return patches


# ================================================================================
# ABX-Core v1.3: IR-Aware Generation with Provenance
# ================================================================================


def build_rack_state_ir(db: Session, rack: Rack) -> RackStateIR:
    """
    Build a RackStateIR from a Rack model.

    This extracts the complete rack state into a deterministic IR representation.
    """
    # Get rack modules
    rack_modules = db.query(RackModule).filter(RackModule.rack_id == rack.id).all()

    modules_ir: List[ModuleIR] = []
    for rm in rack_modules:
        module = db.query(Module).filter(Module.id == rm.module_id).first()
        if module:
            modules_ir.append(
                ModuleIR(
                    module_id=module.id,
                    module_name=module.name,
                    module_type=module.module_type,
                    position_hp=rm.start_hp,
                    row=rm.row_index,
                )
            )

    # Get case info
    case = db.query(Case).filter(Case.id == rack.case_id).first()
    case_hp = case.total_hp if case else 104
    case_rows = case.rows if case else 1

    return RackStateIR(
        rack_id=rack.id,
        rack_name=rack.name,
        case_hp=case_hp,
        case_rows=case_rows,
        modules=modules_ir,
    )


def generate_patches_with_ir(
    db: Session,
    rack: Rack,
    seed: Optional[int] = None,
    config: Optional[PatchEngineConfig] = None,
) -> Tuple[PatchGenerationIR, List[PatchGraphIR], Provenance]:
    """
    ABX-Core v1.3 compliant patch generation with full IR and provenance.

    This function:
    1. Creates a PatchGenerationIR (deterministic IR)
    2. Tracks provenance for the run
    3. Calls the existing generation logic
    4. Converts output to PatchGraphIR format
    5. Returns (IR, patches, provenance) for storage

    Args:
        db: Database session
        rack: Rack to generate patches for
        seed: Random seed
        config: Engine configuration

    Returns:
        Tuple of (generation_ir, patch_graphs, provenance)
    """
    start_time = time.time()

    # Default seed and config
    if seed is None:
        seed = settings.default_generation_seed
    if config is None:
        config = PatchEngineConfig()

    # Build IR
    rack_state = build_rack_state_ir(db, rack)
    params = PatchGenerationParams(
        max_patches=config.max_patches,
        allow_feedback=config.allow_feedback,
        prefer_simple=config.prefer_simple,
    )

    generation_ir = PatchGenerationIR(
        run_id=f"patchgen-{rack.id}-{seed}",  # Deterministic run_id
        rack_state=rack_state,
        seed=seed,
        params=params,
        engine_version=settings.patch_engine_version,
        abx_core_version=settings.abx_core_version,
        created_at=datetime.now(timezone.utc).isoformat(),
        git_commit=get_git_commit(),
        host=None,  # Will be filled by Provenance
    )

    # Create provenance
    provenance = Provenance.create(
        entity_type="patch_batch",
        pipeline="patch_generation",
        engine_version=settings.patch_engine_version,
        git_commit=get_git_commit(),
    )

    # Confirmed-inventory gate: rack placements are manual USER_CONFIRMED.
    # Generation must not invent modules outside the placed inventory.
    from canon.inventory_persist import persist_system_inventory_revision
    from patches.inventory_gate import evaluate_rack_inventory_gate

    gate_report, _ = evaluate_rack_inventory_gate(db, rack)
    persist_system_inventory_revision(
        db, gate_report.inventory, rack_id=int(rack.id)  # type: ignore[arg-type]
    )
    provenance.add_metric("inventory_gate", gate_report.provenance_dict())

    if not gate_report.ready:
        # Fail closed: no confirmed modules → empty library, explicit NOT_COMPUTABLE.
        end_time = time.time()
        provenance.mark_completed()
        provenance.add_metric("duration_ms", (end_time - start_time) * 1000)
        provenance.add_metric("patch_count", 0)
        provenance.add_metric("connection_count", 0)
        provenance.add_metric("generation_status", "NOT_COMPUTABLE")
        provenance.add_metric("inventory_revision_id", gate_report.inventory.inventory_revision_id)
        return generation_ir, [], provenance

    # Generate patches using existing logic
    patch_specs = generate_patches_for_rack(db, rack, seed, config)

    # Drop any patch that escapes confirmed catalog modules (defense in depth).
    # Reuse the same inventory revision (stable id) for filter metrics.
    from patches.inventory_gate import filter_patches_to_confirmed_modules
    from patches.inventory_gate import InventoryGateReport

    kept_specs, dropped, messages = filter_patches_to_confirmed_modules(
        patch_specs, gate_report.allowed_catalog_module_ids
    )
    gate_report = InventoryGateReport(
        inventory=gate_report.inventory,
        allowed_catalog_module_ids=gate_report.allowed_catalog_module_ids,
        ready=True,
        code="FILTERED" if dropped else "OK",
        messages=messages,
        dropped_patch_count=dropped,
    )
    provenance.add_metric("inventory_gate", gate_report.provenance_dict())

    # Convert to PatchGraphIR
    patch_graphs: List[PatchGraphIR] = []
    ir_hash = generation_ir.get_canonical_hash()

    for spec in kept_specs:
        connections_ir = [
            ConnectionIR(
                from_module_id=c.from_module_id,
                from_port=c.from_port,
                to_module_id=c.to_module_id,
                to_port=c.to_port,
                cable_type=c.cable_type,
            )
            for c in spec.connections
        ]

        graph = PatchGraphIR(
            patch_name=spec.name,
            category=spec.category,  # type: ignore
            connections=connections_ir,
            description=spec.description,
            generation_ir_hash=ir_hash,
            generation_seed=spec.generation_seed,
        )
        patch_graphs.append(graph)

    # Resolve generic roles to declared jacks and validate (spec 001 FR-016/017/019).
    from patches.validation import resolve_and_validate

    modules_by_id = {
        int(m.id): m  # type: ignore[arg-type]
        for m in db.query(Module)
        .join(RackModule, RackModule.module_id == Module.id)
        .filter(RackModule.rack_id == rack.id)
        .all()
    }
    patch_graphs, validation = resolve_and_validate(
        patch_graphs, modules_by_id, allowed_module_ids=set(gate_report.allowed_catalog_module_ids)
    )
    if not config.allow_feedback:
        from patches.validation import drop_feedback_patches

        patch_graphs, feedback_dropped = drop_feedback_patches(patch_graphs, validation)
        provenance.add_metric("feedback_dropped_count", feedback_dropped)
    if dropped:
        # The inventory filter removed patches that wired modules outside the confirmed
        # inventory. That is a contradiction, so it fails the run (OQ-08), not just a filter.
        from patches.validation import Finding

        validation.add(
            Finding(
                "block",
                "MODULE_NOT_IN_INVENTORY",
                f"{dropped} generated patch(es) wired modules outside the confirmed inventory.",
            )
        )
    provenance.add_metric("validation", validation.to_dict())

    # Complete provenance
    end_time = time.time()
    provenance.mark_completed()
    provenance.add_metric("duration_ms", (end_time - start_time) * 1000)
    provenance.add_metric("patch_count", len(patch_graphs))
    provenance.add_metric("connection_count", sum(len(p.connections) for p in patch_graphs))
    if validation.blocking:
        status = "VALIDATION_FAILED"
    else:
        status = "FILTERED" if gate_report.code == "FILTERED" else "OK"
    provenance.add_metric("generation_status", status)
    provenance.add_metric("inventory_revision_id", gate_report.inventory.inventory_revision_id)

    return generation_ir, patch_graphs, provenance
