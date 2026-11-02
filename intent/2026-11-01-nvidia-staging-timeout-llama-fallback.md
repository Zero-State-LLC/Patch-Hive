# Intent

## Problem

The NVIDIA vision provider (spec 005 T086) used a 20 s timeout everywhere, and a cold first call to the default model has exceeded it. It also had no fallback model if the default is unavailable. The owner approved both changes on 2026-11-01.

## Proposed outcome

- Staging sets `NVIDIA_TIMEOUT_SECONDS=60` in `edge/api/wrangler.jsonc`, and the edge Worker forwards it outside production (`FLAG_VARS`). The backend default stays 20 s. `ENABLE_NVIDIA_PROVIDER` stays unset, and production still refuses the flag.
- `meta/llama-3.2-90b-vision-instruct` is pinned in `NVIDIA_MODELS` and the settings validator as a fallback chosen only through `NVIDIA_MODEL`. The default stays `nvidia/nemotron-3.5-super-vl-120b-a12b`. No automatic retry on another model; a non-default model logs a warning naming it, and `provider_version` names it in every packet and receipt.

Out of scope: enabling the provider, deploying, a 007 evaluation, and pinning the model in the 007 receipt.

## Affected users / systems

`intelligence/nvidia_provider.py`, `core/config.py`, `edge/api/src/index.ts`, `edge/api/wrangler.jsonc` (staging vars), spec 006 `DEPLOY_NOTES.md`, tests.

## Constraints / non-goals

Fail closed. Do not describe the Meta model as an NVIDIA model. No key in the tree.

## Open questions

- The 007 enablement receipt names the provider, not the model, so a receipt earned with one pinned model also admits the others. Should the receipt pin `NVIDIA_MODEL` (owner)?
- The Llama 3.2 Community License terms for this use need owner review before production.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `meta/llama-3.2-90b-vision-instruct` answers the provider's request shape (JSON schema, thinking off) with an in-schema answer | `OBSERVED` | `RUN_NVIDIA_LIVE=1 pytest tests/integration/test_nvidia_live.py`, 2026-11-01, one synthetic image |
| Its calls take several seconds and have taken 48 s | `OBSERVED` | Same run and earlier direct calls (7-12 s) |
| 60 s is enough for a cold call on staging | `INFERRED` | Longest observed call was 48 s |

## Author / date

- Author: Grok Bot (for the owner)
- Date: 2026-11-01
