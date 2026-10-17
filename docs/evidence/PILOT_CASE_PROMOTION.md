# Pilot evidence → evaluation-case promotion

Use this workflow for the GrokBot/Firecrawl pilot and future acquisition runs.

## Input state

Acquisition records are evidence candidates. They are not evaluation cases merely because an image is rights-cleared or a module identity appears in the registry.

## Promotion workflow

For each RIGHTS_CONFIRMED asset:

1. Bind the retained image hash to exactly one proposed case.
2. Record source URL and rights basis.
3. Identify the physical module/revision visible in the asset.
4. Establish ground truth independently:
   - OPERATOR_VERIFIED: an operator verifies the visible identity/revision; or
   - TWO_SOURCE_VERIFIED: two independent authoritative identity sources agree and the review is recorded.
5. Build a bounded candidate set from the registry.
6. Include `none_of_above` in every identity candidate set.
7. Hash the exact candidate set and retain that hash.
8. Assign one or more scene-condition descriptors and exactly one evaluation cohort.
9. Record contamination. If the asset or label influenced prompts, ranking, policy, thresholds, or provider selection, it cannot enter `locked_test`.
10. Obtain at least one named reviewer and set annotation_status=REVIEWED only after review.
11. Run `scripts/validate_vision_pilot.py`.
12. Leave failures unresolved. Do not repair validation by inventing metadata.

## Partition doctrine

Newly collected material defaults to `development`.

After collection stabilizes:
- select validation cases before threshold selection;
- freeze an uncontaminated locked-test partition before any locked-test measurement;
- preserve degraded/adversarial cases as their own partition;
- unknown/open-set cases MUST expect `none_of_above`.

Do not move a case into locked_test after it has been used for tuning.

## Pilot-specific starting point

The 2026-09-25 acquisition receipt reports 43 RIGHTS_CONFIRMED image assets. Treat these as the first promotion queue.

They are not 43 admitted cases yet.

Promotion counts MUST be reported separately:
- rights-cleared assets;
- ground-truth verified;
- reviewed;
- schema-valid;
- admitted;
- unresolved.

A lower admitted count is valid evidence. Fabricated completeness is not.

## Stop condition for T061c

T061c may be checked only when:
- the manifest validates with no errors;
- identity count is within the approved pilot range;
- required cohorts are represented;
- required partitions are represented;
- the corpus manifest SHA is frozen and retained.

Production thresholds remain NOT_COMPUTABLE at that point. T061d must still compare baseline and Jev-assisted conditions.


## Deterministic promotion workbench

When the retained acquisition bundle is available locally, build a review queue without promoting any unresolved field:

```bash
python scripts/build_vision_promotion_queue.py \
  --discovery deliverables/patchhive-corpus/pilot-2026-09-25/discovery-manifest.jsonl \
  --modules deliverables/patchhive-corpus/pilot-2026-09-25/module-records.jsonl \
  --output work/vision-pilot-promotion-queue.json
```

The queue imports only `RIGHTS_CONFIRMED` assets. It deliberately leaves ground truth, reviewer, cohort, contamination, candidate-set hash, and expected choice unresolved. An operator must resolve those fields from retained evidence before conversion into a pilot case.

For a clean locked-test partition, prefer newly collected operator-owned photographs using `fixtures/vision_eval/operator-shot-intake-template.json`. Public manufacturer/Commons imagery may remain useful for development and validation, but public-web pretraining exposure makes it a weak basis for a clean locked test.
