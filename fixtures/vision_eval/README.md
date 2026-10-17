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
