# Decision Intelligence provenance axes

Campaign 005 uses three independent axes. They MUST NOT be collapsed.

## 1. Evidence epistemics

Describes how a claim is known from an evidence source:

- OBSERVED — the value is directly stated or directly visible in the cited source.
- INFERRED — the value is derived from other retained evidence.
- SPECULATIVE — the value is a hypothesis or weakly supported interpretation.
- NOT_COMPUTABLE — available evidence is insufficient to produce the value safely.

OBSERVED does not imply physical truth for the user's module and does not imply human confirmation.

## 2. Source authority

Describes the class of source that supplied the claim:

- MANUFACTURER_PRIMARY
- AUTHORITATIVE_DATABASE
- RETAILER_DISTRIBUTOR
- COMMUNITY_CATALOG
- COMMUNITY_CONTENT
- UNKNOWN_SOURCE_AUTHORITY

Source authority is descriptive, not a truth score. Conflicts are retained rather than overwritten.

## 3. Resolution authority

Describes the confirmation state used by the visual/canonical workflow:

- USER_CONFIRMED
- REJECTED
- UNKNOWN
- NOT_COMPUTABLE
- OBSERVED / INFERRED where used by existing visual contracts remain non-canonical evidence states.

A probabilistic provider cannot emit USER_CONFIRMED.

## Canonical interpretation

A record can therefore be:

`OBSERVED × COMMUNITY_CATALOG × UNKNOWN`

This means the catalog explicitly stated the value, the source was community-maintained, and the user's physical module has not been confirmed.

Likewise:

`OBSERVED × MANUFACTURER_PRIMARY × USER_CONFIRMED`

means a manufacturer source explicitly stated the claim and a human independently confirmed the physical identity through the confirmation workflow.

No axis may be used as a shortcut for another.

## Evaluation consequence

Evaluation ground truth requires resolution authority plus corpus admission. Neither epistemic OBSERVED status nor high source authority alone establishes an image label.

Registry evidence may bound the candidate universe, but image ground truth must remain independently verified.
