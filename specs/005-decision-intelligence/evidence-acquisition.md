# Evidence acquisition and registry admission

**Status:** normative for Decision Intelligence campaign 005.

This boundary governs research-derived hardware facts collected by Firecrawl, GrokBot/Hermes, manual research, catalogs, retailers, and manufacturer documentation.

## Authority chain

```text
DISCOVERY
→ SOURCE CLAIM
→ PROVENANCE + RIGHTS RECORD
→ NORMALIZED EVIDENCE
→ REGISTRY ADMISSION REVIEW
→ CANDIDATE UNIVERSE
→ VISION / DECISION INTELLIGENCE
→ HUMAN CONFIRMATION
→ CANON
```

Research tooling MUST NOT write canonical inventory or silently promote a source claim into hardware truth.

## Two independent dimensions

Every acquired fact MUST preserve both its epistemic status and source authority.

### Epistemic status

- `OBSERVED`: the stated value was directly observed in the cited source.
- `INFERRED`: derived from one or more observations.
- `SPECULATIVE`: plausible but insufficiently supported.
- `NOT_COMPUTABLE`: available evidence does not support a value.

`OBSERVED` means "observed in this source." It does **not** mean manufacturer-verified or canonical.

### Source authority

- `MANUFACTURER_PRIMARY`: official manufacturer product page, manual, revision note, or technical document.
- `AUTHORITATIVE_DATABASE`: maintained structured database with explicit provenance/curation.
- `RETAILER_DISTRIBUTOR`: retailer or distributor product material.
- `COMMUNITY_CATALOG`: community-maintained catalog/database.
- `COMMUNITY_CONTENT`: forum, review, social, wiki, or other community content.
- `UNKNOWN_SOURCE_AUTHORITY`: authority cannot be established.

Source authority is descriptive, not a truth score. Conflicts are retained and resolved by deterministic admission policy or human review.

## Research claim record

Research outputs SHOULD normalize each fact to:

```json
{
  "subject_id": "stable module/revision candidate",
  "field": "hp",
  "value": 8,
  "unit": "HP",
  "epistemic_status": "OBSERVED",
  "source_authority": "COMMUNITY_CATALOG",
  "source_url": "https://example.invalid/product",
  "source_retrieved_at": "RFC3339 timestamp",
  "source_content_hash": "sha256:...",
  "rights_status": "RIGHTS_UNKNOWN",
  "admission_status": "EVIDENCE_ONLY"
}
```

Unknown values remain unknown. Conflicting claims remain separate records.

## Registry admission states

- `EVIDENCE_ONLY`: retained research evidence; not registry truth.
- `REVIEW_REQUIRED`: conflict, weak authority, identity ambiguity, or material missing provenance.
- `REGISTRY_ACCEPTED`: admitted by registry policy/operator as a registry fact.
- `REJECTED`: evidence was evaluated and rejected; retain reason/provenance.
- `SUPERSEDED`: replaced by a newer admitted revision without deleting historical evidence.

Registry admission does not confirm that a photographed physical module is that registry entry. Physical identity still requires the existing PatchHive confirmation boundary.

## Deterministic admission rules

1. A Firecrawl success is never sufficient by itself for `REGISTRY_ACCEPTED`.
2. `OBSERVED + COMMUNITY_CATALOG` remains evidence until registry admission.
3. Manufacturer-primary evidence MAY support automatic registry proposal, but conflicting manufacturer revisions or incompatible claims require review.
4. Retailer/community claims MAY fill candidate metadata but MUST NOT overwrite a conflicting higher-authority admitted claim.
5. Missing, inaccessible, or contradictory evidence resolves to `REVIEW_REQUIRED` or `NOT_COMPUTABLE`, never invention.
6. Research scripts MUST retain the exact source URL and SHOULD retain a content hash and retrieval time.
7. Rights status governs reuse of source assets. Factual metadata provenance and image-training rights are separate concerns.
8. Scraped images MUST NOT enter the representative vision corpus unless the corpus rights/consent contract admits them.
9. Device Registry entries define a bounded candidate vocabulary; they are not evaluation ground truth merely because they were admitted.
10. Locked-test corpus cases MUST NOT be used to tune acquisition rules, Jev prompts, candidate ranking, or policy thresholds.

## Existing Hermes/Firecrawl data

The current `data/synth-catalog/hermes-research/` outputs are admitted as **research evidence**.

Legacy `provenance: "OBSERVED"` means a value was observed at the recorded source. It MUST NOT be interpreted as manufacturer verification. Consumers SHOULD derive `source_authority` from explicit source metadata/domain until the legacy files are migrated.

No destructive rewrite of historical research artifacts is required. New acquisition output MUST emit the two-dimensional provenance model.

## Acceptance

- No acquisition script imports or mutates canonical inventory services.
- A community-catalog observation cannot masquerade as manufacturer-primary evidence.
- Conflicting claims remain inspectable.
- Rights status is retained independently from factual provenance.
- Unknown remains unknown.
- Registry admission and physical-module confirmation remain distinct state transitions.


## Provenance axis clarification

Campaign 005 uses three independent axes: evidence epistemics, source authority, and resolution authority. See `docs/evidence/PROVENANCE_AXES.md`. `OBSERVED` never means `USER_CONFIRMED`, and source authority never substitutes for either epistemic or resolution status.
