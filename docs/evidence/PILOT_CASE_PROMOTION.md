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

## Finding openly licensed candidate photos (context.dev)

The owner approved 300 context.dev searches for corpus photos on 2026-11-02 (approval
`corpus-photos-2026-11` in `data/synth-catalog/receipts/fetch-approvals.json`, expires
2026-11-30). `scripts/vision/find_corpus_photos.py` spends that allowance and writes candidates
for the promotion queue above. Run it from the repo root with the backend venv:

```bash
# 1. Pick modules: write a starter identities file from the committed catalog seeds and overlays.
python scripts/vision/find_corpus_photos.py starter \
  --slugs mutable-instruments-plaits,make-noise-maths --out ~/patchhive-corpus/identities.json

# 2. Search (one search per identity, at most 300 and never more than the approval has left).
#    CONTEXT_DEV_API_KEY must be set in the environment.
python scripts/vision/find_corpus_photos.py search \
  --identities ~/patchhive-corpus/identities.json --out-dir ~/patchhive-corpus/photos

# 3. Build the review queue from the run's output.
python scripts/build_vision_promotion_queue.py \
  --discovery ~/patchhive-corpus/photos/candidates.jsonl \
  --modules ~/patchhive-corpus/photos/modules.jsonl \
  --output ~/patchhive-corpus/photos/promotion-queue.json
```

What the search does:

- Searches go through `CatalogScraper` (free DuckDuckGo first, then context.dev), so the FR-003
  approval gate and the spend ledger apply. The run is context.dev-only: it removes
  `FIRECRAWL_API_KEY` from its own process environment and aborts if a Firecrawl call is made.
  Without a matching approval entry it refuses before any request.
- Only Wikimedia Commons `/wiki/File:` pages and Flickr photo pages are kept. Each page is a free
  GET with no paid fallback (robots.txt respected, 2 s per host). Commons' robots.txt disallows
  `/w/api.php`, so the File page HTML (`licensetpl_short` / `licensetpl_link`) is parsed instead.
  On Flickr only the photo's own `rel="license"` link counts.
- Originals (Commons original file, Flickr's largest public size) are downloaded with plain GETs:
  robots respected, 2 s per host, 20 MB cap, JPEG/PNG/WebP only. They go to `--out-dir/images/`.
  `--out-dir` must be outside this repo and any other git checkout. Image bytes never enter the
  repo.
- Output: `candidates.jsonl` (one row per photo page and identity), `modules.jsonl`,
  `receipts.jsonl` and `summary.json` (searched, results, allowed-host results, licenses accepted
  and excluded by reason, downloaded, failed).

Rights rule: only CC0, public domain, CC BY and CC BY-SA (any version) are accepted, and BY / BY-SA
need a recorded author. Those rows get `rights_status=RIGHTS_CONFIRMED` with `rights_basis` =
license, license URL, author and source page. NC, ND, all-rights-reserved, other licenses and
pages without a readable license are kept with an `exclusion_reason` and are never
`RIGHTS_CONFIRMED`. Only rights-confirmed rows whose bytes were retained have `kind=image_asset`,
so only they enter the queue.

The identity searched is a proposal, not ground truth. Rows stay `ground_truth_status=UNVERIFIED`
and `annotation_status=DISCOVERED`, with `identity_sources` listing the photo page text match and
the maker's page. Cohort and partition are left for the operator (`proposed_cohort` is a guess
from the page text, or null). An operator must still verify the visible identity and revision and
review each case (steps 3 to 12 above) before it is admitted. Commons and Flickr images are
public-web material: prefer them for development and validation, not `locked_test`.
