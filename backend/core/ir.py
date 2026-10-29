"""
Deterministic Intermediate Representation (IR) for PatchHive.

ABX-Core v1.3 compliance: The IR is a first-class, typed object that represents
the complete state of a patch generation pipeline. It is:
- Serializable (can be stored/transmitted)
- Deterministic (same inputs → same IR)
- Replayable (IR → same patch graph)

This satisfies the ABX-Core v1.3 requirement that "deterministic IR be a first-class object."
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

# The canonical category set (spec 001 FR-012, OQ-03 resolved 2026-10-28). Subtypes
# such as Pad, Lead, Bass and Drone are not categories; they belong in a separate
# optional field once a generator produces them.
PatchCategory = Literal[
    "Voice",
    "Clock-Rhythm",
    "Generative",
    "Texture-FX",
    "Utility",
]


@dataclass
class ModuleIR:
    """IR representation of a module in the rack."""

    module_id: int
    module_name: str
    module_type: str  # "vco", "vcf", "vca", etc.
    position_hp: int
    row: int


@dataclass
class RackStateIR:
    """IR representation of the rack state at generation time."""

    rack_id: int
    rack_name: str
    case_hp: int
    case_rows: int
    modules: List[ModuleIR] = field(default_factory=list)
    total_modules: int = 0

    def __post_init__(self):
        self.total_modules = len(self.modules)


@dataclass
class PatchGenerationParams:
    """Parameters for patch generation."""

    max_patches: int = 20
    allow_feedback: bool = False
    prefer_simple: bool = False
    target_category: Optional[PatchCategory] = None


@dataclass
class PatchGenerationIR:
    """
    Complete Intermediate Representation for a patch generation run.

    This is the deterministic IR required by ABX-Core v1.3.
    Given the same IR, the system must produce the same patch graph.

    Complexity note: This structure adds explicit typing and serializability
    to the patch generation pipeline, reducing entropy and improving debuggability
    (satisfies ABX-Core v1.3 complexity rule).
    """

    # Core identifiers
    run_id: str  # UUID for this generation run
    rack_state: RackStateIR
    seed: int
    params: PatchGenerationParams

    # Version tracking
    engine_version: str  # PatchHive version
    abx_core_version: str  # ABX-Core version

    # Timestamps
    created_at: str  # ISO8601 UTC timestamp

    # Optional metadata
    git_commit: Optional[str] = None
    host: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize IR to dictionary."""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize IR to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatchGenerationIR":
        """Deserialize IR from dictionary."""
        # Reconstruct nested dataclasses
        rack_state_data = data["rack_state"]
        modules = [ModuleIR(**m) for m in rack_state_data["modules"]]
        rack_state = RackStateIR(
            rack_id=rack_state_data["rack_id"],
            rack_name=rack_state_data["rack_name"],
            case_hp=rack_state_data["case_hp"],
            case_rows=rack_state_data["case_rows"],
            modules=modules,
        )

        params = PatchGenerationParams(**data["params"])

        return cls(
            run_id=data["run_id"],
            rack_state=rack_state,
            seed=data["seed"],
            params=params,
            engine_version=data["engine_version"],
            abx_core_version=data["abx_core_version"],
            created_at=data["created_at"],
            git_commit=data.get("git_commit"),
            host=data.get("host"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "PatchGenerationIR":
        """Deserialize IR from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def get_canonical_hash(self) -> str:
        """
        Get a canonical hash of the IR for deduplication/comparison.

        Hashes the canonical JSON (sorted keys) of the IR without the fields that
        describe one run rather than its inputs: run id, timestamp, commit and host.
        Inventory, seed, params and the engine and ABX-Core versions all count
        (spec 001 FR-001).
        """
        import hashlib

        data = self.to_dict()
        for name in ("run_id", "created_at", "git_commit", "host"):
            data.pop(name, None)
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:32]


@dataclass
class ConnectionIR:
    """IR representation of a cable connection."""

    from_module_id: int
    from_port: str
    to_module_id: int
    to_port: str
    cable_type: str  # "audio", "cv", "gate", "clock"
    # "declared": both ends are jacks the modules declare; "generic": a role name used
    # because a module's jacks are not on file (spec 001 OQ-04). None before resolution.
    port_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data["port_status"] is None:
            del data["port_status"]
        return data


@dataclass
class PatchGraphIR:
    """
    IR representation of a generated patch graph.

    This is the output of the patch generation pipeline.
    """

    patch_name: str
    category: PatchCategory
    connections: List[ConnectionIR] = field(default_factory=list)
    description: str = ""

    # Link to generation IR
    generation_ir_hash: str = ""
    generation_seed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_name": self.patch_name,
            "category": self.category,
            "connections": [c.to_dict() for c in self.connections],
            "description": self.description,
            "generation_ir_hash": self.generation_ir_hash,
            "generation_seed": self.generation_seed,
        }
