# GrokBot / Firecrawl execution prompt — PatchHive vision pilot

Work directly against issue #160 and the contracts on `main`.

## Goal
Acquire candidate **real-world image cases** for the PatchHive vision/Decision Intelligence pilot. Do not modify production thresholds, canon, or T061/T062 completion state.

## Read first
1. `fixtures/vision_eval/pilot-manifest.json`
2. `fixtures/vision_eval/pilot-case.schema.json`
3. `fixtures/vision_eval/pilot-case-template.json`
4. `fixtures/vision_eval/corpus-contract.json`
5. `specs/005-decision-intelligence/evidence-acquisition.md`
6. `docs/evidence/DECISION_INTELLIGENCE_EVALUATION.md`

## Firecrawl task
Use the existing enriched registry/research evidence to select a diverse 50–100 identity candidate universe. Then use Firecrawl for targeted discovery of image-bearing manufacturer/documentation pages and other sources whose reuse rights can be established.

Prefer manufacturer-primary material. Do not infer that public accessibility grants training/evaluation reuse rights.

For every discovered image candidate retain:
- exact source URL;
- image/asset URL;
- retrieval UTC;
- SHA-256 of retained asset if legally retained;
- stated license/rights basis;
- source authority;
- module/revision identity evidence;
- scene cohort;
- contamination status.

Only `RIGHTS_CONFIRMED` assets may be proposed for admission. Keep RIGHTS_UNKNOWN/AMBIGUOUS/RESTRICTED in a separate discovery/review artifact; do not insert them into admitted pilot cases.

## Cohort balance
Actively seek:
- clear_front_panel
- installed_rack
- partial_occlusion
- cable_obscured
- low_light_or_glare
- revision_or_panel_variant
- hard_negative
- unknown_open_set

Hard negatives should emphasize same-family/revision/clone/lookalike ambiguity. Unknown/open-set must preserve `none_of_above`; never force a nearest registry identity.

## Ground truth
Registry membership is not image ground truth.

A case remains `UNVERIFIED` / `DISCOVERED` until independent evidence establishes the depicted module/revision. Do not self-promote cases to OPERATOR_VERIFIED. If two genuinely independent authoritative sources establish identity, record the evidence needed for later TWO_SOURCE_VERIFIED review but do not fabricate reviewer identity.

## Partitioning
Default newly discovered material to `development` intake. Do not assign `locked_test` merely to fill quotas. A locked-test set must be frozen from uncontaminated material after collection and before tuning.

## Output
Create/update a branch, not main directly. Produce:
- a candidate intake JSONL or equivalent source manifest;
- rights-review artifact for non-admissible discoveries;
- proposed pilot cases conforming to the case schema;
- coverage report by identity, manufacturer, cohort, source authority, and rights state;
- hard-negative/confusion report;
- unresolved/open-set report.

Do not commit copyrighted image bytes unless the recorded rights basis explicitly permits repository storage. Hash/reference externally retained assets where appropriate.

Run:
`python scripts/validate_vision_pilot.py fixtures/vision_eval/pilot-manifest.json`

Expect `NOT_ADMITTED` until human/operator review is genuinely complete. That is a valid result.

Open a PR referencing #160. In the PR body report exact counts and distinguish DISCOVERED, RIGHTS_CONFIRMED, REVIEWED, and ADMITTED counts. Do not report model accuracy.

Stop and report rather than guess if rights, identity, provenance, or contamination cannot be established.
