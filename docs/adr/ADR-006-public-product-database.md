# ADR-006 — Expose the Device Registry as the Public Product Database

Status: Superseded by [ADR-007](ADR-007-photo-first-product.md) on 2026-11-07

Date: 2026-07-20

## Context

PatchHive already has a Module Gallery, versioned gallery schemas, deterministic module identifiers, ModularGrid-compatible ingestion, enrichment operations, matching, admin workflows, and a broader Device Registry specification. These assets are necessary for photo recognition and patch generation but are not yet defined as a complete public product surface.

Users need to browse the full available catalog of brands, modules, products, revisions, ports, controls, capabilities, images, and documentation independently of system ingestion.

## Decision

The canonical Device Registry will also power a first-class public Product Database and Product Explorer.

The Product Explorer is a read model and user interface, not a second source of truth. Existing Module Gallery infrastructure will be preserved, audited, and upgraded through compatibility adapters and versioned migrations.

The public hierarchy is:

```text
Manufacturer -> ProductFamily -> DeviceModel -> DeviceRevision -> PanelVariant
```

The Product Database must support all imported brands and products and must expose measured coverage. It must not claim universal completeness without a defined reference universe and retained evidence.

## Required consequences

- add global Product Explorer navigation
- add manufacturer and product detail pages
- expose versioned product/manufacturer/search/coverage APIs
- migrate or adapt existing gallery and module-library records
- preserve stable IDs, provenance, aliases, and immutable referenced revisions
- make unknown field states visible
- use the same canonical products for vision recognition, inventory confirmation, patch generation, and Patch Books
- upgrade admin/gallery operations into a registry workbench
- publish deterministic coverage and snapshot receipts

## Rejected alternatives

### Separate public catalog database

Rejected because it would duplicate identity, drift from patch-generation constraints, and weaken provenance.

### Keep the registry internal only

Rejected because product discovery, transparency, education, and correction workflows are core user value.

### Replace existing gallery infrastructure immediately

Rejected because the repository already contains useful versioning, ingestion, enrichment, and frontend integrations. Migration must be evidence-driven and compatibility-preserving.

## Scope boundary

The Product Database does not add audio capture, audio analysis, DSP, synthesis emulation, or hardware control.
