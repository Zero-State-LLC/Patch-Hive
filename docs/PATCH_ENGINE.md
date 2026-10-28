# Patch Generation Engine

> Canonical alignment notice: `backend/canon/compiler.py` is the authoritative deterministic boundary. It emits `PatchGraph`, the five-phase `PatchPlan`, `ValidationReport`, deterministic variation identity, `StageReceipt` records, and `ArtifactManifest`. Older generator details below are compatibility implementation notes.

This document provides a deep dive into PatchHive's deterministic patch generation engine.

## Overview

The patch generation engine analyzes a rack's modules and generates plausible patch configurations using rule-based heuristics. The engine is **fully deterministic**: given the same rack and seed, it will always produce the same patches.

## Core Principles

### 1. Determinism
- Uses Python's `random.Random` with explicit seeds
- No system randomness or time-based entropy
- Same input → Same output, always

### 2. Signal Flow Logic
- Follows Eurorack signal flow conventions:
  - **Sources**: VCOs, noise, sequencers
  - **Processors**: Filters, effects, utilities
  - **Modulators**: LFOs, envelopes
  - **Amplifiers**: VCAs, mixers
  - **Outputs**: Final audio path

### 3. Category Detection
- Patches are categorized using the canonical PatchHive category set:
  - **Voice**: Primary synth voice paths
  - **Clock-Rhythm**: Percussive or clock-driven structures
  - **Generative**: Self-evolving modulation
  - **Texture-FX**: Effect-centric processing
  - **Utility**: Processing-only patches

## Architecture

### Entry Point

```python
generate_patches_for_rack(
    db: Session,
    rack: Rack,
    seed: Optional[int] = None,
    config: Optional[PatchEngineConfig] = None
) -> List[PatchSpec]
```

Located in: `backend/patches/engine.py`

### Data Structures

#### PatchSpec
```python
@dataclass
class PatchSpec:
    name: str                    # Auto-generated deterministic name
    category: PatchCategory      # Voice/Clock-Rhythm/Generative/Texture-FX/Utility (spec 001 FR-012)
    connections: List[Connection]
    description: str
    generation_seed: int
```

#### Connection
```python
@dataclass
class Connection:
    from_module_id: int
    from_port: str
    to_module_id: int
    to_port: str
    cable_type: str  # "audio", "cv", "gate", "clock"
```

#### PatchEngineConfig
```python
@dataclass
class PatchEngineConfig:
    max_patches: int = 20
    allow_feedback: bool = False
    prefer_simple: bool = False
```

## Generation Process

### Step 1: Module Analysis

The `ModuleAnalyzer` categorizes modules by type:

```python
analyzer = ModuleAnalyzer(db, rack)
# Populates:
analyzer.vcos          # Oscillators
analyzer.vcfs          # Filters
analyzer.vcas          # VCAs
analyzer.envelopes     # Envelopes/ADSRs
analyzer.lfos          # LFOs
analyzer.sequencers    # Sequencers
analyzer.mixers        # Mixers
analyzer.effects       # Effects
analyzer.utilities     # Utilities
analyzer.noise_sources # Noise generators
```

**Categorization Logic**:
- Based on `module.module_type` field (e.g., "VCO", "VCF", "VCA")
- Case-insensitive substring matching
- Modules can belong to multiple categories

### Step 2: Patch Type Selection

The `PatchGenerator` determines which patch types are feasible:

```python
if _can_generate_subtractive_voice():
    # Requires: VCO + VCA
    patches.extend(_generate_subtractive_voices())

if _can_generate_generative():
    # Requires: Sequencer OR multiple LFOs
    patches.extend(_generate_generative_patches())

if _can_generate_percussion():
    # Requires: Noise source OR envelopes
    patches.extend(_generate_percussion())

if _can_generate_fx_chain():
    # Requires: FX modules
    patches.extend(_generate_fx_chains())
```

### Step 3: Connection Generation

For each patch type, the engine builds connection graphs:

#### Subtractive Synthesis Voice

**Basic signal chain**:
```
VCO → [VCF] → VCA → OUT
         ↑      ↑
         |      └── ENV (CV)
         └── LFO (CV, optional)
```

**Implementation**:
```python
# VCO to VCF (if available)
if vcfs:
    connections.append(Connection(
        from_module_id=vco.id,
        from_port="Audio Out",
        to_module_id=vcf.id,
        to_port="Audio In",
        cable_type="audio"
    ))

# VCF (or VCO) to VCA
connections.append(Connection(
    from_module_id=current_module.id,
    from_port="Audio Out",
    to_module_id=vca.id,
    to_port="Audio In",
    cable_type="audio"
))

# Envelope to VCA
if envelopes:
    connections.append(Connection(
        from_module_id=env.id,
        from_port="Envelope Out",
        to_module_id=vca.id,
        to_port="CV In",
        cable_type="cv"
    ))

# Optional: LFO modulation
if lfos and rng.random() > 0.5:
    connections.append(Connection(
        from_module_id=lfo.id,
        from_port="LFO Out",
        to_module_id=target.id,
        to_port="CV In",
        cable_type="cv"
    ))
```

**Category Logic**:
- More connections → "Pad"
- Envelope present → Random choice of "Lead", "Bass", "Pad"
- No envelope → "Drone" (continuous tone)

#### Generative Patches

**Concept**: Self-evolving patches with modulation sources driving oscillators and filters.

**Signal chain example**:
```
SEQUENCER → VCO (V/Oct)
LFO1 → VCO (FM)
LFO2 → VCF (Cutoff)
```

**Implementation**:
```python
if sequencers:
    seq = rng.choice(sequencers)
    vco = rng.choice(vcos)
    connections.append(Connection(
        from_module_id=seq.id,
        from_port="CV Out",
        to_module_id=vco.id,
        to_port="V/Oct",
        cable_type="cv"
    ))

if len(lfos) >= 2:
    lfo1, lfo2 = lfos[0], lfos[1]
    # LFO1 → VCO FM
    # LFO2 → VCF Cutoff
```

#### Clock-Rhythm

**Concept**: Short, rhythmic structures using noise and envelopes.

**Signal chain**:
```
NOISE → [VCF] → VCA
                 ↑
                 └── ENV (short)
```

**Category**: Always "Clock-Rhythm"

#### Texture-FX Chains

**Concept**: Processing chains for external signals.

**Signal chain**:
```
MIXER → FX → OUT
```

**Category**: Always "Texture-FX"

#### Further rules (issue #95)

These run after the four rules above. Each draws from its own generator (`seed + offset`), so adding them left the earlier patches unchanged. A rule fires only when the rack holds every module it wires; nothing pads a run to `max_patches` (spec 001 FR-017).

| Rule | Needs | Category | Seed |
|---|---|---|---|
| Sequenced voice, one per VCO (up to 3): sequencer CV to V/Oct, gate to an envelope on the VCA, through a filter when present | sequencer, VCO, VCA, envelope | Voice | `seed + 5000 + i` |
| Plucked voice: one envelope on both filter cutoff and VCA | VCO, VCF, VCA, envelope | Voice | `seed + 6000` |
| Drone: an LFO sweeps the filter, no envelope | VCO, VCF, VCA, LFO | Voice | `seed + 7000` |
| Sequenced hats: the sequencer gate fires an envelope on (filtered) noise | sequencer, envelope, noise, VCA | Clock-Rhythm | `seed + 8000` |
| Voice through an effect | VCO, VCA, effect | Texture-FX | `seed + 9000` |
| Two oscillators into a mixer | 2 VCOs, mixer | Utility | `seed + 9500` |

Port names are still generic ("Audio Out", "Gate In"): most modules have no jack data on file (spec 001 OQ-04).

## Deterministic Naming

Each patch gets a deterministic name using the `generate_patch_name()` function:

```python
name = generate_patch_name(seed=patch_seed, category="Voice")
# Examples: "Deep Evolving Voice", "Bright Fast Voice"
```

**Name generation**:
1. Hash the seed using SHA-256
2. Use hash bytes to pick from word lists:
   - PATCH_PREFIXES: "Deep", "Bright", "Warm", etc.
   - PATCH_TYPES: "Bass", "Lead", "Pad", etc.
   - Category names: "Pad", "Lead", "Bass", etc.
3. Combine prefix + type OR prefix + category

## Provenance & Metadata

Each generated patch stores:

```json
{
  "generation_seed": 42,
  "generation_version": "1.0.0",
  "engine_config": {
    "max_patches": 20,
    "allow_feedback": false,
    "prefer_simple": false
  }
}
```

This enables:
- **Reproducibility**: Re-generate exact same patches
- **Debugging**: Understand why a patch was created
- **Versioning**: Track engine evolution over time

## Waveform Approximation (symbolic visualization only)

After patch generation, **symbolic** waveform thumbnails may be approximated for documentation. This is not audio processing, DSP, or sonic prediction. Language in product surfaces must say "approximation" or "expected structural envelope," never claim an observed sound.

### Inference from Patch

```python
def infer_waveform_params_from_patch(
    patch_category: str,
    has_lfo: bool,
    has_envelope: bool
) -> WaveformParams
```

**Category-based defaults**:
- **Voice**: Complex waveform, slow attack/release, high sustain
- **Modulation**: Saw wave, fast attack, medium sustain
- **Clock-Rhythm**: Square wave, very fast attack, short decay
- **Generative**: Noise with modulation
- **Texture-FX**: Complex wave with noise

### Waveform Generation

```python
def generate_waveform_svg(
    params: WaveformParams,
    width: int = 800,
    height: int = 200,
    samples: int = 500,
    seed: int = 42
) -> str
```

**Process**:
1. Generate base waveform (sine/saw/square/triangle/noise/complex)
2. Apply modulation (LFO-like)
3. Apply ADSR envelope
4. Add noise if specified
5. Render as SVG path

**Output**: SVG with waveform visualization and glow effect

## Extension Points

### Adding New Patch Types

1. Add detection method:
```python
def _can_generate_new_type(self) -> bool:
    return len(self.analyzer.required_modules) > 0
```

2. Add generation method:
```python
def _generate_new_type(self) -> List[PatchSpec]:
    patches = []
    # Build connections
    return patches
```

3. Call from `generate_patches()`:
```python
if self._can_generate_new_type():
    patches.extend(self._generate_new_type())
```

### Adding Module Type Recognition

Update `ModuleAnalyzer._analyze()`:
```python
if "NEW_TYPE" in mtype:
    self.new_type_modules.append(module)
```

### Customizing Generation Rules

Modify `PatchEngineConfig`:
```python
@dataclass
class PatchEngineConfig:
    max_patches: int = 20
    allow_feedback: bool = False
    prefer_simple: bool = False
    # Add new config options:
    min_connections: int = 2
    prefer_stereo: bool = False
```

## Limitations

### Current Version (1.0.0)

- **Port matching**: Uses generic port names ("Audio Out", "CV In")
  - Real modules have specific port names
  - Future: Port name mapping database

- **Signal validation**: No electrical/spec validation
  - Assumes all connections are electrically valid
  - Future: Voltage range and impedance checking

- **Polyphony**: Single-voice patches only
  - No multi-voice or chord generation
  - Future: Polyphonic patch support

- **Timing**: No temporal/rhythmic patterns
  - Patches are "one-shot" configurations
  - Future: Sequence programming and timing

### Design Trade-offs

- **Simplicity vs. Realism**: Prioritizes clear, understandable patches over complex "realistic" ones
- **Determinism vs. Variety**: Determinism limits randomness exploration (by design)
- **Rule-based vs. ML**: Uses heuristics instead of machine learning (for transparency and predictability)

## Future Enhancements

### Phase 2
- **Port name database**: Accurate port mapping for real modules
- **Multi-voice patches**: Polyphonic configurations
- **Feedback loop detection**: Safe feedback routing
- **Constraint solver**: Optimize patch creation with constraints

### Phase 3
- **ML-assisted generation**: Learn from community-rated patches (optional research track)
- ~~**Audio simulation**~~: **OUT OF SCOPE** — PatchHive does not synthesize, record, or analyze audio. Waveform SVGs are symbolic approximations only, never sonic ground truth.
- ~~**Hardware integration**~~: **OUT OF SCOPE** — no MIDI/CV activation or physical equipment control
