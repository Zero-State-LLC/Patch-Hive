# Intent

## Problem

Two gap-closure items from the 2026-10-29 research are still open in code.

- 005 R4: offline evaluation calls `policy.evaluate(packet)` with no request, so the candidate-set check never runs. `false_canonicalization_count` is hardcoded to `0` in `evaluation.py`, so the base harness reports zero by construction.
- 008 R2: the Design Engine walkthrough denies only `production`/`prod`. `development`, `test`, a typo or an empty string pass, and `expected_environment=None` skips the check.

## Proposed outcome

- 005 T084: `EvaluationCase` and `LabeledCorpusCase` gain optional `candidate_ids`. When present, evaluation builds a `ChoiceRequest` and passes it to `policy.evaluate`, so an out-of-set answer escalates. `false_canonicalization_count` is the resolution-machine replay count (a case whose disposition alone would permit a canon write), computed in `evaluation.py`; the enablement harness no longer adds a second count.
- 008 T070: `expected_environment` is a required `Literal["staging"]`. `flags_test_mode_failures` fails with `SERVER_ENVIRONMENT_NOT_STAGING` unless the server reports exactly `staging`. The walkthrough CLI drops `--environment`.
- Out of scope: 005 T081/T082/T083/T085, `evidence/routes.py`, `policy.py`, `resolution_machine.py`, `clef_resolution.py` (PR #135), and any receipt re-pinning.

## Affected users / systems

Offline evaluation (`intelligence/evaluation.py`, `evaluation_enablement.py`, `clef_evaluation.py`), the 008 staging walkthrough (`core/ops/design_walkthrough.py`, `core/ops/f5_cutover.py`, `scripts/staging/design_engine_walkthrough.py`) and their tests. No runtime request path changes.

## Constraints / non-goals

- Fail closed. No test or fixture is edited to force green.
- A case with no `candidate_ids` still skips the candidate check, because the existing corpora do not record the candidate set. This is a gap to close when fixtures gain candidates; it is not silently treated as checked.
- An absent `candidate_ids` is omitted from the corpus digest, so existing frozen corpora keep their hashes.
- No deploy, no network write.

## Open questions

- Should corpora with no `candidate_ids` be refused at freeze time? The research does not say; the owner decides.
- Definition used: R4 says "replace the hardcoded 0 with the structural count", so a false canonicalization is a case where the resolution machine permits a canon write from the policy disposition alone.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Evaluation did not pass a request into `policy.evaluate` | `OBSERVED` | research R4, `evaluation.py` before this change |
| Existing corpus digests are unchanged | `INFERRED` | `candidate_ids=None` is excluded from the digest payload; the existing corpus tests pass unmodified |
| `harness_source_sha256` changes because harness source changed | `OBSERVED` | it hashes source files; no committed receipt pins a value |

## Author / date

- Author: Claude (medium lane), for Daniel Meyer
- Date: 2026-10-29
