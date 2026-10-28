"""
Deterministic naming service for rigs and patches.
Rigs are descriptive based on core module and role.
Patches are structure-derived with humor gating.
"""

from __future__ import annotations

import hashlib
import json
import re
from hashlib import sha256
from typing import Any, Dict, Iterable

from core.ops.derive_patch_semantics import derive_patch_semantics

ADJECTIVES = [
    "Midnight",
    "Solar",
    "Cosmic",
    "Quantum",
    "Crystal",
    "Digital",
    "Analog",
    "Warm",
    "Cold",
    "Deep",
    "Bright",
    "Dark",
    "Neon",
    "Vintage",
    "Future",
    "Chaotic",
    "Ordered",
    "Strange",
    "Harmonic",
    "Dissonant",
    "Rhythmic",
    "Melodic",
    "Textural",
    "Ambient",
    "Industrial",
    "Organic",
    "Synthetic",
    "Ethereal",
    "Gritty",
    "Smooth",
    "Rough",
    "Glitchy",
    "Flowing",
    "Frozen",
    "Burning",
    "Electric",
    "Magnetic",
    "Gravitational",
    "Temporal",
    "Spatial",
    "Fractal",
    "Recursive",
    "Modular",
    "Linear",
    "Circular",
    "Spiral",
    "Prismatic",
    "Monochrome",
    "Iridescent",
    "Phosphorescent",
]

NOUNS = [
    "Swarm",
    "Lattice",
    "Matrix",
    "Cascade",
    "Vortex",
    "Nexus",
    "Prism",
    "Echo",
    "Pulse",
    "Wave",
    "Drift",
    "Storm",
    "Shimmer",
    "Resonance",
    "Sequence",
    "Pattern",
    "Circuit",
    "Signal",
    "Field",
    "Spectrum",
    "Harmonics",
    "Overtones",
    "Frequencies",
    "Oscillations",
    "Modulations",
    "Envelope",
    "Filter",
    "Distortion",
    "Reverb",
    "Delay",
    "Chorus",
    "Phaser",
    "Flanger",
    "Tremolo",
    "Vibrato",
    "Arpeggio",
    "Glissando",
    "Cluster",
    "Texture",
    "Atmosphere",
    "Landscape",
    "Terrain",
    "Horizon",
    "Nebula",
    "Galaxy",
    "Constellation",
    "Aurora",
    "Eclipse",
    "Supernova",
]

PATCH_PREFIXES = [
    "Deep",
    "Bright",
    "Warm",
    "Cold",
    "Soft",
    "Hard",
    "Wide",
    "Narrow",
    "Fast",
    "Slow",
    "Evolving",
    "Static",
    "Random",
    "Sequenced",
    "Clock-Rhythm",
    "Free",
    "Chaotic",
    "Ordered",
    "Dense",
    "Sparse",
    "Rich",
    "Minimal",
]

PATCH_TYPES = [
    "Bass",
    "Lead",
    "Pad",
    "Pluck",
    "Drone",
    "Percussion",
    "FX",
    "Noise",
    "Sweep",
    "Stab",
    "Chord",
    "Arpeggio",
    "Sequence",
    "Texture",
    "Atmosphere",
    "Glitch",
    "Loop",
    "Burst",
    "Pulse",
    "Wave",
    "Grain",
    "Cloud",
]

MECHANISM_TOKENS = [
    "Cross-Mod",
    "Clock-Lattice",
    "Gate-Choir",
    "Slew-Pulse",
    "Sample-Loop",
    "Reset Bloom",
    "Feedback Lace",
    "Accent Stack",
    "Drift Engine",
]

DESCRIPTORS = {
    "Beginner": ["Clean", "Basic", "First", "Pocket", "Plain"],
    "Intermediate": ["Swing", "Spiral", "Hinge", "Cascade", "Offset"],
    "Advanced": ["Fractal", "Recursive", "Hydra", "Nonlinear", "Entropic"],
}

HUMOR_TAGS = [
    "Gremlin",
    "Polite Chaos",
    "Oops-All-Clocks",
    "Angry Envelope",
    "Too Many LFOs",
    "Budget Buchla",
    "Department of Unnecessary Modulation",
]


def generate_rack_name(seed: int) -> str:
    """
    Generate a deterministic rack name from a seed.

    Args:
        seed: Integer seed for deterministic generation

    Returns:
        A name like "Midnight Swarm" or "Solar Lattice"
    """
    # Use hash of seed to pick words
    hash_bytes = hashlib.sha256(str(seed).encode()).digest()
    adj_idx = int.from_bytes(hash_bytes[0:4], "big") % len(ADJECTIVES)
    noun_idx = int.from_bytes(hash_bytes[4:8], "big") % len(NOUNS)

    return f"{ADJECTIVES[adj_idx]} {NOUNS[noun_idx]}"


def generate_rig_suggested_name(modules: Iterable[Any]) -> str:
    """Generate a deterministic rig name from module metadata."""
    modules_list = [m for m in modules if m]
    if not modules_list:
        return "Modular Starter Rack"

    def hp_value(module: Any) -> int:
        return int(getattr(module, "hp", 0) or 0)

    core_module = sorted(
        modules_list,
        key=lambda m: (hp_value(m), str(getattr(m, "name", "")), int(getattr(m, "id", 0))),
        reverse=True,
    )[0]

    module_name = str(getattr(core_module, "name", "Core Module"))
    nickname = _module_nickname(module_name)
    role = _rig_role_from_module(core_module)
    return f"{nickname} {role} Rack"


def generate_patch_name(
    seed: int,
    category: str,
) -> str:
    """
    Generate a deterministic patch name from a seed and category.

    Args:
        seed: Integer seed for deterministic generation
        category: Patch category to influence naming

    Returns:
        A name like "Deep Evolving Pad" or "Bright Fast Lead"
    """
    # Use hash of seed to pick words
    hash_bytes = hashlib.sha256(str(seed).encode()).digest()
    prefix_idx = int.from_bytes(hash_bytes[0:4], "big") % len(PATCH_PREFIXES)
    type_idx = int.from_bytes(hash_bytes[4:8], "big") % len(PATCH_TYPES)

    # Sometimes add a prefix, sometimes just use type
    use_prefix = int.from_bytes(hash_bytes[8:9], "big") % 2 == 0

    if use_prefix:
        return f"{PATCH_PREFIXES[prefix_idx]} {PATCH_TYPES[type_idx]}"
    else:
        # Use category-based name
        # The canonical categories (core.ir.PatchCategory); anything else is "Patch".
        category_names = {
            "Voice": "Voice",
            "Clock-Rhythm": "Clock-Rhythm",
            "Generative": "Generative",
            "Texture-FX": "Texture-FX",
            "Utility": "Utility",
        }
        return f"{PATCH_PREFIXES[prefix_idx]} {category_names.get(category, 'Patch')}"


def name_patch_v2(
    patch_id: int | str,
    modules_by_id: Dict[int, Any],
    connections: Iterable[Any],
) -> str:
    features = build_patch_feature_vector(modules_by_id, connections)
    difficulty = _difficulty_from_features(features)
    descriptor = _select_descriptor(difficulty, patch_id, features)
    mechanism = _select_mechanism(modules_by_id, connections, features, patch_id)
    humor_tag = _select_humor_tag(modules_by_id, connections, features, patch_id)

    if humor_tag:
        return f"{descriptor} {mechanism} ({humor_tag})"
    return f"{descriptor} {mechanism}"


def hash_string_to_seed(input_str: str) -> int:
    """Convert a string to a deterministic non-negative 31-bit integer seed.

    Postgres ``INTEGER`` is signed 32-bit; raw 4-byte big-endian digests can
    overflow (``NumericValueOutOfRange``) when written to ``racks.generation_seed``.
    """
    return int.from_bytes(hashlib.sha256(input_str.encode()).digest()[:4], "big") & 0x7FFFFFFF

def build_patch_feature_vector(
    modules_by_id: Dict[int, Any],
    connections: Iterable[Any],
) -> Dict[str, int | bool]:
    edges = list(connections)
    modulation_edges = [c for c in edges if _get_attr(c, "cable_type") in {"cv", "gate", "clock"}]
    clock_edges = [c for c in edges if _get_attr(c, "cable_type") == "clock"]
    cycle_present = _detect_cycle(edges)
    utility_count = sum(1 for m in modules_by_id.values() if _is_utility_module(m))
    voice_count = sum(1 for m in modules_by_id.values() if _is_voice_module(m))
    symmetry_score = _symmetry_score(edges)
    clock_module_count = sum(1 for m in modules_by_id.values() if _is_clock_module(m))
    clock_reset_edges = sum(
        1
        for c in edges
        if "reset" in str(_get_attr(c, "from_port", "")).lower()
        or "reset" in str(_get_attr(c, "to_port", "")).lower()
    )

    return {
        "modules": len(modules_by_id),
        "edges": len(edges),
        "modulation_edges": len(modulation_edges),
        "clock_edges": len(clock_edges),
        "clock_modules": clock_module_count,
        "clock_resets": clock_reset_edges,
        "cycle_present": cycle_present,
        "utility_count": utility_count,
        "voice_count": voice_count,
        "symmetry_score": symmetry_score,
    }


def _difficulty_from_features(features: Dict[str, int | bool]) -> str:
    edges = int(features.get("edges", 0))
    if edges <= 4:
        return "Beginner"
    if edges <= 8:
        return "Intermediate"
    return "Advanced"


def _select_descriptor(difficulty: str, patch_id: int | str, features: Dict[str, Any]) -> str:
    options = DESCRIPTORS.get(difficulty, DESCRIPTORS["Intermediate"])
    seed = _stable_hash_seed("descriptor", patch_id, features)
    return options[seed % len(options)]


def _select_mechanism(
    modules_by_id: Dict[int, Any],
    connections: Iterable[Any],
    features: Dict[str, Any],
    patch_id: int | str,
) -> str:
    if features.get("cycle_present"):
        return "Feedback Lace"
    if int(features.get("clock_edges", 0)) >= 2 and int(features.get("clock_modules", 0)) >= 2:
        return "Clock-Lattice"
    if int(features.get("modulation_edges", 0)) >= 8:
        return "Cross-Mod"

    for conn in connections:
        if _get_attr(conn, "cable_type") == "gate":
            return "Gate-Choir"

    for conn in connections:
        from_port = str(_get_attr(conn, "from_port", "")).lower()
        to_port = str(_get_attr(conn, "to_port", "")).lower()
        if "slew" in from_port or "slew" in to_port:
            return "Slew-Pulse"
        if "sample" in from_port or "sample" in to_port:
            return "Sample-Loop"
        if "reset" in from_port or "reset" in to_port:
            return "Reset Bloom"

    for module in modules_by_id.values():
        if "ACCENT" in _module_type(module):
            return "Accent Stack"

    seed = _stable_hash_seed("mechanism", patch_id, features)
    return MECHANISM_TOKENS[seed % len(MECHANISM_TOKENS)]


def _select_humor_tag(
    modules_by_id: Dict[int, Any],
    connections: Iterable[Any],
    features: Dict[str, Any],
    patch_id: int | str,
) -> str | None:
    if not _humor_allowed(modules_by_id, connections, features):
        return None
    seed = _stable_hash_seed("humor", patch_id, features)
    return HUMOR_TAGS[seed % len(HUMOR_TAGS)]


def _humor_allowed(
    modules_by_id: Dict[int, Any],
    connections: Iterable[Any],
    features: Dict[str, Any],
) -> bool:
    modulation_edges = int(features.get("modulation_edges", 0))
    clock_edges = int(features.get("clock_edges", 0))
    clock_modules = int(features.get("clock_modules", 0))
    clock_resets = int(features.get("clock_resets", 0))
    cycle_present = bool(features.get("cycle_present"))
    utility_count = int(features.get("utility_count", 0))
    voice_count = int(features.get("voice_count", 0))
    symmetry_score = int(features.get("symmetry_score", 0))

    excess_modulation = modulation_edges > 12
    clock_spaghetti = clock_edges >= 4 and clock_modules >= 3 and clock_resets > 0
    feedback_loop = cycle_present
    over_utility = utility_count > voice_count and utility_count > 0
    symmetry_weirdness = symmetry_score >= 3
    contradictory_routing = _has_contradictory_routing(modules_by_id, connections)

    return any(
        [
            excess_modulation,
            clock_spaghetti,
            feedback_loop,
            over_utility,
            symmetry_weirdness,
            contradictory_routing,
        ]
    )


def _stable_hash_seed(label: str, patch_id: int | str, features: Dict[str, Any]) -> int:
    payload = json.dumps(features, sort_keys=True)
    digest = sha256(f"{label}:{patch_id}:{payload}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def _get_attr(conn: Any, key: str, default: Any = None) -> Any:
    if isinstance(conn, dict):
        return conn.get(key, default)
    return getattr(conn, key, default)


def _module_type(module: Any) -> str:
    return str(getattr(module, "module_type", "") or "").upper()


def _module_nickname(name: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9]+", name)
    if not tokens:
        return "Core"
    return " ".join(tokens[:2])


def _rig_role_from_module(module: Any) -> str:
    module_type = _module_type(module)
    name = str(getattr(module, "name", "")).upper()
    for key, role in [
        ("CLOCK", "Clockwork"),
        ("SEQ", "Control"),
        ("MIDI", "Control"),
        ("UTILITY", "Utility"),
        ("MIX", "Mix"),
        ("FILTER", "Texture"),
        ("FX", "Texture"),
        ("VCO", "Voice"),
        ("OSC", "Voice"),
        ("VOICE", "Voice"),
    ]:
        if key in module_type or key in name:
            return role
    return "Modular"


def _is_clock_module(module: Any) -> bool:
    module_type = _module_type(module)
    return any(key in module_type for key in ["CLOCK", "DIV", "MULT", "SEQ"])


def _is_utility_module(module: Any) -> bool:
    module_type = _module_type(module)
    return any(key in module_type for key in ["UTILITY", "MIX", "MULT", "ATTEN", "LOGIC", "SWITCH"])


def _is_voice_module(module: Any) -> bool:
    module_type = _module_type(module)
    return any(key in module_type for key in ["VCO", "OSC", "VOICE", "FILTER", "VCA", "NOISE"])


def _detect_cycle(connections: Iterable[Any]) -> bool:
    adjacency: Dict[int, set[int]] = {}
    for conn in connections:
        from_id = _get_attr(conn, "from_module_id")
        to_id = _get_attr(conn, "to_module_id")
        if from_id is None or to_id is None:
            continue
        adjacency.setdefault(int(from_id), set()).add(int(to_id))

    visited: set[int] = set()
    stack: set[int] = set()

    def dfs(node: int) -> bool:
        visited.add(node)
        stack.add(node)
        for neighbor in adjacency.get(node, set()):
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in stack:
                return True
        stack.remove(node)
        return False

    for node in adjacency:
        if node not in visited and dfs(node):
            return True
    return False


def _symmetry_score(connections: Iterable[Any]) -> int:
    counts: Dict[tuple[int, str, str], int] = {}
    score = 0
    for conn in connections:
        key = (
            int(_get_attr(conn, "from_module_id") or 0),
            str(_get_attr(conn, "from_port", "")),
            str(_get_attr(conn, "cable_type", "")),
        )
        counts[key] = counts.get(key, 0) + 1
    for count in counts.values():
        if count > 1:
            score += count
    return score


def _has_contradictory_routing(modules_by_id: Dict[int, Any], connections: Iterable[Any]) -> bool:
    clock_to_env = False
    env_to_clock = False
    for conn in connections:
        from_id = _get_attr(conn, "from_module_id")
        to_id = _get_attr(conn, "to_module_id")
        from_module = modules_by_id.get(from_id)
        to_module = modules_by_id.get(to_id)
        from_type = _module_type(from_module)
        to_type = _module_type(to_module)
        cable_type = _get_attr(conn, "cable_type")

        if "ENV" in from_type and _is_clock_module(to_module):
            env_to_clock = True
        if (
            _is_clock_module(from_module)
            and "ENV" in to_type
            and cable_type in {"clock", "gate", "cv"}
        ):
            clock_to_env = True
    return clock_to_env and env_to_clock
