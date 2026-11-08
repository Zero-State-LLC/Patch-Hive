# Vision evaluation fixtures

**License:** synthetic internal fixtures only — not a production dataset.  
**Version:** `vision-eval.v1`

## Purpose

Provide a **deterministic** evaluation harness for CI:

- module detection precision/recall when labels exist
- explicit `NOT_COMPUTABLE` for production accuracy metrics

Do **not** publish fixture scores as product accuracy.

## Layout

```text
manifest.json
<sample_id>/
  image.bin          # bytes fed to VisionProviderContext
  labels.json        # ground truth modules/manufacturers
  recorded_packet.json  # optional fixture provider packet
```

## Run

```bash
cd backend
env -u PYTHONPATH python -m pytest tests/unit/test_vision_evaluation.py -q
```

## Decision Intelligence extension

Decision Intelligence reuses this corpus rather than creating a parallel dataset.

- `corpus-contract.json` records the admission contract for representative real-world cases.
- Existing samples remain synthetic CI fixtures only.
- Real-world development, validation, locked-test, adversarial/degraded, and unknown/open-set partitions are not yet admitted.
- Device Registry records may define candidate IDs, but operator-reviewed case labels remain the evaluation ground truth.
- Exact identity candidate sets must preserve an explicit `none_of_above` path.
- Production thresholds remain `NOT_COMPUTABLE` until a representative licensed corpus and SHA-pinned evaluation receipt exist.


## Real-world pilot intake

`pilot-manifest.json` is the governed intake shell for the first representative real-world corpus. It starts empty and **does not** change production metrics from `NOT_COMPUTABLE`.

Each admitted case must satisfy `pilot-case.schema.json` and the corpus contract. Run:

```bash
python scripts/validate_vision_pilot.py fixtures/vision_eval/pilot-manifest.json
```

The validator fails closed on unconfirmed rights, unreviewed/unverified ground truth, missing candidate hashes, missing `none_of_above`, locked-test contamination, insufficient identity/cohort coverage, or missing validation/locked/open-set partitions.

Research-derived Device Registry evidence may seed the candidate universe. It may not self-label pilot images.

## Whole-rig photos (spec 009)

A manifest with `"unit": "whole_rig"` is a corpus of whole-Rig photos. Each case is one photo, with:

- `rows`: how many Rig rows the photo covers.
- `labels`: every Module and Blank Panel on it. Each has a `kind` (`module` or `blank_panel`), `row_index`, `start_hp` and `hp`. A Module names its `maker` and `name`; one the catalog doesn't have is `"open_set": true` instead.

The rights, review, partition, cohort and contamination rules are the same as for photos of one Module. A whole-rig case has no `expected_choice`, `candidate_set_hash`, `none_of_above_allowed` or `ground_truth_inventory`. An `unknown_open_set` case shows at least one off-catalog Module. Its frozen record keeps a digest of its rows and labels.

`backend/evidence/rig_evaluation.py` scores each photo's provider answer against its labels. It reports identity accuracy per Sighting, detection recall and precision, position error in HP, and false canonicalization, which must stay zero.

`whole_rig/` is a two-photo synthetic corpus with recorded answers, for the harness tests. It is far below admission size.
