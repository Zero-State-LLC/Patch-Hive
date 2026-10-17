# PatchHive Constitution

**Version:** 1.0.0  
**Ratified:** 2026-09-25  
**Authority:** product-wide engineering constitution

## Purpose

PatchHive converts evidence about a Eurorack rig into verified inventory, deterministic patch artifacts, and reproducible publications. This constitution constrains every feature specification and implementation.

## Non-negotiable principles

1. **Canon is deterministic.** Fixed normalized canonical input, schema/generator versions, layout profile, and seed MUST produce canonical-equivalent output.
2. **Evidence is not canon.** Provider output, OCR, retrieval, probabilistic classifications, community records, and inferred facts are evidence only.
3. **Unknown remains unknown.** Missing physical or functional facts MUST NOT be invented to satisfy generation, validation, or presentation.
4. **Probabilistic systems propose; deterministic policy disposes.** A model may rank, classify, score, or recommend a next action. It MUST NOT directly establish physical truth or mutate canonical inventory.
5. **Confirmation is explicit.** Where policy requires confirmation, canonicalization MUST be blocked until the required human or authoritative-source transition occurs.
6. **Provenance is mandatory.** Canon-affecting proposals MUST bind to evidence identifiers/hashes, provider identity/version, decision-contract version, policy version, and disposition.
7. **Providers are replaceable adapters.** Canonical schemas MUST NOT depend on Jev or any other provider-specific response type.
8. **Generation is inventory-bounded.** Patch generation MUST use confirmed inventory/capabilities only.
9. **Fail closed at trust boundaries.** Missing evidence, incompatible versions, malformed packets, unavailable providers, or insufficient confidence MUST become an explicit unresolved/error state, never an implicit pass.
10. **One-page publishing law remains binding.** Decision intelligence cannot weaken page-fit, accessibility, signal, provenance, or standalone-execution requirements.

## Required specification chain

Every new product capability MUST trace:

`Journey -> Workflow -> State Transition -> Contract -> Acceptance Test -> Implementation Task`.

A feature specification MUST also identify domain entities, data changes, security/privacy effects, observability, rollback, and authority boundaries.

## Decision-intelligence authority boundary

The decision layer MAY:
- classify normalized evidence;
- rank bounded candidates;
- score confidence or ambiguity;
- detect conflicts;
- route work to catalog lookup, retrieval, another model, or human review;
- reduce candidate search space.

The decision layer MUST NOT:
- self-confirm a module;
- invent a module, jack, voltage, mode, or capability;
- overwrite source evidence;
- mutate a canonical rig or patch;
- bypass deterministic validators;
- convert low-confidence absence into a negative fact.

## Evidence labels

Engineering analysis and receipts use:
- **OBSERVED** — directly supported by retained evidence.
- **INFERRED** — derived by an explicit rule/model from observed inputs.
- **SPECULATIVE** — hypothesis only; never canonical.
- **NOT_COMPUTABLE** — required evidence is absent or insufficient.

## Change control

A feature spec may strengthen this constitution but may not weaken it. Any weakening requires an explicit constitution version change, migration/impact analysis, and operator approval.
