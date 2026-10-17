# Decision Intelligence Evaluation Corpus

Status: **HARNESS READY / REAL-WORLD CORPUS NOT YET APPROVED**

The evaluator in `backend/intelligence/evaluation.py` is offline and provider-neutral.
It does not call Jev or any live model.

## Required corpus fields

Each JSONL row must contain:

- `case_id` — stable pseudonymous identifier
- `cohort` — e.g. clear-panel, glare, partial-label, clone-family, unknown
- `expected_choice` — operator-verified catalog candidate or `none_of_above`
- `licensed_source` — provenance/licensing label; blank values are rejected
- `packet` — retained DecisionPacket from the system under evaluation

Do not commit user rack photos, OCR text containing personal data, API payloads containing
secrets, or unlicensed scraped images.

## Metrics

The first gate records:

- case count
- top-1 accuracy
- abstention rate
- human-review rate
- escalation rate
- multiclass Brier score
- false-canonicalization count (architectural invariant = 0)

Top-k and cohort confusion matrices remain required before staging enablement. They need
candidate rankings/retained distributions from a sufficiently large real-world corpus.

## Threshold policy

Do **not** invent release thresholds before baseline collection.

1. Freeze a corpus SHA.
2. Run the current vision-only/candidate baseline.
3. Run the same corpus through Jev-assisted ranking.
4. Compare accuracy, calibration, abstention/review, latency, and cost.
5. Select thresholds only after reviewing the distributions and failure cases.
6. Record operator approval and corpus SHA in a retained evaluation receipt.

Until that receipt exists, `enable_decision_intelligence` remains false.


## Existing corpus discovery — 2026-09-25

A repository audit found an existing deterministic vision corpus at `fixtures/vision_eval/`
(version `vision-eval.v1`). It is **synthetic internal fixtures only** and therefore valid
for CI and plumbing validation, but not representative enough for production threshold selection.

Notion's canonical **PatchHive — Computer Vision Evaluation Protocol** already defines the
real-world corpus contract: image assets, scene conditions, rights/consent, ground-truth
inventory/regions/ports/controls/connections, annotation status, reviewers, and partitions for
development, validation, locked test, adversarial/degraded, and unknown/open-set cases.

Therefore Decision Intelligence does not create a competing corpus. It extends the existing
vision-evaluation corpus and protocol.

### Admission mapping

- `fixtures/vision_eval/` → deterministic CI/synthetic baseline.
- representative licensed real-world cases → future retained evaluation corpus governed by the
  Computer Vision Evaluation Protocol.
- Device Registry / Product Database → candidate universe and canonical identity labels, not
  evaluation ground truth by themselves.
- Jev DecisionPackets → predictions retained against those labels.
- locked test cases → never used for prompt, model, policy-threshold, or candidate-ranking tuning.

### Current status

- Synthetic CI corpus: **OBSERVED / AVAILABLE**.
- Real-world representative corpus: **NOT_COMPUTABLE from current repo/Notion evidence**.
- Production thresholds: **NOT_COMPUTABLE** until the representative corpus is admitted.


## Research evidence versus evaluation ground truth

The Hermes/Firecrawl collection under `data/synth-catalog/hermes-research/` is a valuable registry-enrichment evidence source, but it is not automatically an evaluation corpus.

Research claims MUST preserve both epistemic status and source authority. In particular, a legacy record with `provenance: OBSERVED` sourced from a community catalog means only that the claim was observed at that source. It does not establish manufacturer verification.

See `specs/005-decision-intelligence/evidence-acquisition.md` for the normative acquisition → registry-admission boundary.

A registry-admitted module can supply candidate vocabulary for an evaluation case. The case still requires the corpus contract's independent image provenance/rights, scene conditions, ground-truth identity, annotation status, reviewers, and partition controls before it can contribute to T061/T062 calibration.
