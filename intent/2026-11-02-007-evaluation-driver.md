# Intent

## Problem

The spec 007 chain (`freeze_corpus` through `pin_receipt`, plus signing and verification) exists only as library functions called by tests. The owner guide of 2026-11-02 (finding 1, gaps list item 1) says the operator has no command to run it.

## Proposed outcome

`scripts/staging/run_007_evaluation.py` with subcommands `freeze`, `candidate-hashes`, `run`, `propose`, `approve`, `enable-staging`, `pin`, `sign` and `verify`. Each reads the previous sealed JSON artifact from one directory and writes the next through the existing library calls. `run` calls the live Clef or NVIDIA provider (env credentials, refused unless the flag is on) or, with `--dry-run`, the fixture provider. `sign` reads the Ed25519 key from a file path. `verify` replays the chain, checks the signature against the committed allowlist and runs the staging startup gate.

Out of scope: building the corpus, any live run, generating or committing a key, committing a receipt, changing staging settings or deploying.

## Affected users / systems

The operator running 007 T010b to T083. New script and tests; spec 007 tasks/notes and the owner guide. No library, route, setting or deployed behaviour changes.

## Constraints / non-goals

Fail closed: every library refusal is surfaced with its code; no library check is weakened. Credentials and key material are never printed or taken from argv. Artifacts are never overwritten. A dry run must write outside `backend/` so it cannot ship.

## Open questions

- The baseline condition is not defined by spec 007. The driver uses a deterministic no-model abstainer through the fixture provider (uniform over candidates, selects `none_of_above`). The owner may prefer another baseline.
- The manifest's `candidate_set_hash` had no fixed formula. The driver requires it to equal the module-identity `ChoiceRequest.candidate_set_hash()` of the candidates it sends (`sha256:<hex>` or bare hex).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| Every subcommand runs offline on the synthetic chain and `verify` passes | `OBSERVED` | `backend/tests/integration/test_007_evaluation_driver.py` |
| Missing approval flag, unknown approver, tampered receipt and wrong key are refused | `OBSERVED` | same tests |
| The live path sends bound images through the real NVIDIA adapter | `OBSERVED` | same tests, mocked transport |
| A real NVIDIA or Clef run succeeds end to end | `NOT_COMPUTABLE` | no corpus and no live call in this work |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-02
