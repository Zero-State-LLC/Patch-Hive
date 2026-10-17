# Journeys

## J1 — Photo-assisted exact module resolution

1. User uploads rack evidence.
2. Vision/OCR produces normalized observations.
3. Catalog retrieval creates a bounded candidate set.
4. DecisionProvider ranks candidates.
5. DecisionPolicy classifies disposition.
6. UI presents proposal and provenance.
7. User confirms/rejects/defers.
8. Confirmation creates or updates the immutable inventory revision through the existing canonical path.

## J2 — Unknown exact identity, useful capability resolution

1. Exact identity remains unresolved.
2. Available evidence is classified into function family and bounded capability hypotheses.
3. Low-confidence or safety-sensitive properties remain unknown.
4. Patch generation continues to exclude unconfirmed capabilities.

## J3 — Conflicting sources

1. Evidence sources disagree.
2. Decision layer flags a material conflict.
3. Policy routes to authoritative retrieval or user review.
4. All source claims remain retained.
5. Canon remains unchanged until resolution.

## J4 — Cheap-to-expensive routing

1. A decision is attempted with the configured low-cost provider.
2. Policy evaluates confidence, conflict, and evidence sufficiency.
3. If unresolved, route to one bounded next step.
4. Stop when confirmed, explicitly unresolved, or retry/escalation budget is exhausted.
