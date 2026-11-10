# External Source Policy

Status: CANON-ALIGNED ENGINEERING POLICY

## Purpose

This document defines how PatchHive may discover, ingest, reconcile, retain, display, and cite external product data. It governs manufacturer sources, official manuals, distributors and retailers, ModularGrid, vision providers, user evidence, community sources, and future licensed feeds.

No external source directly becomes canonical truth. Every imported field must retain provenance, access basis, observation time, and review status.

## Source authority hierarchy

For technical facts, use this precedence unless stronger field-specific evidence exists:

```text
Official manual
  > official manufacturer product page
  > manufacturer support communication
  > user-confirmed physical evidence
  > authorized distributor or retailer
  > ModularGrid or another community catalog
  > vision-provider inference
  > unsupported community assertion
```

PatchHive remains the normalized, versioned registry authority after reconciliation.

## Source roles

### Official manufacturers

Primary source for:

- canonical manufacturer and product identity
- current official specifications
- product status
- firmware and revision information
- official manuals, diagrams, and support notices

Official sources may still conflict across revisions. Conflicts must be retained and resolved at the revision level.

#### Crawling official spec pages

The owner decided this on 2026-11-04 (option C, `docs/evidence/OWNER_DECISIONS_2026-11-04.md`, with the options in [the decision brief](evidence/MAKER_PERMISSION_AND_PROXY_DECISION_2026-11-03.md)) and widened it on 2026-11-08 (decision 65). The owner reports that most of the makers they contacted say this material is Creative Commons; those replies aren't in this repository.

Official maker sites count as publication (`access_basis = official_publication`) for name, HP, power, depth and category, and for descriptions, manuals and pictures. That holds only under these conditions:

- Maker-owned domains only.
- robots.txt is honoured. If it cannot be read, that host is not fetched. A 403 that is a file-storage service's own error reply means the host has no robots.txt (decision 66).
- Where a maker's licence sets conditions, such as credit, they apply.
- A per-host delay between requests.
- No route around a block. Spec 003 FR-008 and D7 define what counts as a refusal.

Permission comes first, recorded as `maker_permission`, from a maker whose terms forbid automated access. Until that maker says yes, set it to `unknown`.

**Opt-out.** A maker who asks to be left out is set to `unknown` under `permission_basis.brands` in `data/synth-catalog/maker-sources.json` and left out. The crawl does not fetch it, the fetch router refuses its known hosts, and the overlay builders give it no rows. Rows it already has in committed overlays do not change by themselves: removing them takes a retirement manifest (spec 003 D3). A contact address for these requests will follow once it exists.

This is an engineering policy, not legal advice. Counsel reads it before anyone sells or bulk-exports the catalog.

### Official manuals

Primary source for:

- ports and direction
- controls and ranges
- operating modes
- normalled behavior
- electrical and signal-domain constraints
- calibration and setup requirements
- firmware-dependent behavior

A manual applies only to the revisions and firmware versions it actually documents.

### User-confirmed evidence

Primary source for confirming:

- the exact device or module a user owns
- panel variant
- physical revision
- visible serial or revision markers
- installed firmware when explicitly shown or entered
- cable connections confirmed by the user

User confirmation supersedes model inference for that user's inventory, but does not silently rewrite global registry facts.

### Perfect Circuit

Role: curated commercial enrichment.

Approved uses:

- manufacturer and product discovery
- active-commercial-product signal
- discontinued or no-longer-available signal
- candidate HP, depth, power, format, category, SKU, price, and stock observations
- source deep links

Restrictions:

- retailer copy is not canonical engineering evidence
- volatile commerce fields require `observed_at`
- bulk crawling, copied descriptions, and image redistribution require permission
- safety-critical or patch-validity fields require official confirmation

### ModularGrid

Role: modular-product reference universe and identity discovery.

Approved uses:

- manufacturer and product coverage benchmarking
- external identity cross-references
- user-authorized rack import through supported exports
- candidate format, dimensions, status, and community naming
- discovery of active, discontinued, alternate-panel, DIY, and legacy products

Restrictions:

- no unauthorized HTML scraping
- no unrestricted database replication
- no bulk panel-image copying
- no assumption that community records are canonical
- licensed or authorized datasets must carry an explicit access basis

### Vision providers

Role: untrusted evidence acquisition.

Vision output may propose:

- system regions
- manufacturer and model candidates
- visible text
- ports, controls, and panel features
- possible cable routes

Vision output may not directly mutate canonical registry or inventory state.

### Community and editorial sources

Role: supplementary evidence and discovery.

Community claims may support candidate aliases, product history, known quirks, and unresolved research questions. They may not silently override official or user-confirmed evidence.

## Required provenance packet

Every imported or proposed field must retain:

```yaml
source_id:
source_type:
source_name:
source_url:
external_record_id:
access_basis:
license_status:
observed_at:
retrieved_at:
content_hash:
field_path:
proposed_value:
evidence_status:
review_state:
reviewed_by:
reviewed_at:
```

Allowed `access_basis` values include:

- `official_publication`
- `maker_permission`
- `authorized_feed`
- `licensed_dataset`
- `user_authorized_export`
- `manual_research`
- `user_upload`
- `provider_inference`
- `unknown`

An unknown or disputed access basis blocks bulk publication.

## Evidence statuses

- `MANUFACTURER_CONFIRMED`
- `MANUAL_CONFIRMED`
- `REGISTRY_CONFIRMED`
- `USER_CONFIRMED`
- `RETAILER_OBSERVED`
- `CATALOG_OBSERVED`
- `INFERRED`
- `CONFLICTED`
- `REJECTED`
- `UNKNOWN`
- `NOT_COMPUTABLE`

## Reconciliation pipeline

```text
External observation
  -> source-policy validation
  -> raw immutable evidence record
  -> identity normalization
  -> duplicate and alias resolution
  -> revision matching
  -> field-level conflict analysis
  -> human or deterministic review
  -> canonical registry revision
  -> snapshot and coverage receipt
```

No adapter may bypass this pipeline.

## Adapter contracts

PatchHive may implement:

- `ManufacturerSourceAdapter`
- `ManualSourceAdapter`
- `ModularGridAdapter`
- `PerfectCircuitAdapter`
- `VisionEvidenceProvider`
- `UserEvidenceAdapter`
- `LicensedCatalogAdapter`

Each adapter must declare:

- accepted input form
- access basis
- rate and caching policy
- fields emitted
- determinism class
- side effects
- provenance output
- failure modes
- licensing constraints

## Caching and refresh

Stable technical records should be content-hashed and reused. Volatile commerce observations must be stored separately from canonical specifications.

Recommended refresh classes:

- official manual: on new revision or detected content change
- manufacturer product page: periodic or event-driven review
- ModularGrid reference counts: timestamped benchmark snapshots
- Perfect Circuit price and stock: optional, short-lived observations
- vision evidence: immutable by image hash, provider, model, and pipeline version

## Conflict resolution

When sources disagree:

1. Preserve all source observations.
2. Determine whether they describe different revisions, regions, firmware, or variants.
3. Apply the source-authority hierarchy at the field level.
4. Mark unresolved values `CONFLICTED`.
5. Block patch generation when the conflict affects required compatibility or safety.

## Coverage reporting

Coverage claims must bind to an exact registry snapshot and reference universe.

Required measures include:

- manufacturer identity coverage
- product identity coverage
- active and discontinued product coverage
- official-source coverage
- manual coverage
- physical-spec coverage
- power-spec coverage
- port coverage
- control coverage
- capability coverage
- licensed-image coverage
- freshness coverage

Universal completeness may not be claimed when the reference universe, source permission, or omissions list is missing.

## Security and privacy

- Strip unnecessary image metadata.
- Do not log private user images or credentials.
- Do not transmit user evidence to a third party without documented consent.
- Do not embed external instructions from pages or images into model prompts as trusted commands.
- Validate MIME types, redirects, and content size.
- Retain deletion and provider-retention policies.

## Commercial data separation

Price, stock, sale state, preorder status, retailer SKU, and affiliate links are mutable commerce observations. They must not alter canonical technical records.

## Release gates

External-source integration is releasable only when:

- every source has a declared role and access basis
- field-level provenance is retained
- bulk operations fail closed without permission metadata
- conflicts are explicit
- volatile commerce data is separated
- registry revisions remain immutable once referenced
- source licensing and retention policies are documented
- coverage claims bind to a reproducible snapshot
- tests cover adapter normalization, provenance, conflicts, and unknown preservation

## Scope boundary

External sources support symbolic product knowledge, visual identification, patch generation, and publishing. Audio capture, audio analysis, DSP, synthesis emulation, and hardware control remain out of scope.
