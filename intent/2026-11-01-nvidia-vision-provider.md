# Intent

## Problem

The owner wants NVIDIA models wherever a vision model is needed (the project is in NVIDIA Inception) while keeping Clef for image classification. The only vision path was Clef on Cloudflare Workers AI.

## Proposed outcome

`NvidiaVisionProvider`, a second spec 005 DecisionProvider beside Clef. It calls an NVIDIA vision-language model on the NVIDIA API catalog (OpenAI-compatible chat completions) with the evidence images and a JSON schema that admits only the request's candidates. It reuses the Clef adapter machine and answer mapping. `DECISION_PROVIDER=nvidia` selects it; `ENABLE_NVIDIA_PROVIDER` defaults off, production refuses it, and outside development it needs the signed 007 receipt (005 T080). Clef is unchanged.

Out of scope: enabling it anywhere (needs `NVIDIA_API_KEY`, a 007 evaluation with `nvidia` as the assisted provider, and the approver key), and any self-hosted NIM.

## Affected users / systems

`intelligence/clef_provider.py` (provider name and error prefix overridable; behaviour unchanged), new `intelligence/nvidia_provider.py`, settings, the decision route, startup and enablement gates, 007 enableable providers, `edge/api` forwarding.

## Constraints / non-goals

Fail closed on timeout, transport error, malformed or out-of-candidate output, unfinished generation and loader failure. No network call or image load while the flag is off. Model self-reported probabilities are not trusted until the 007 evaluation calibrates them. Key from env only; never logged.

## Open questions

- The hosted API catalog is under NVIDIA's API trial terms; production use needs the Inception or paid entitlement confirmed (owner).

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| `nvidia/nemotron-3.5-super-vl-120b-a12b` and `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` are served by `integrate.api.nvidia.com` | `OBSERVED` | `GET /v1/models`, 2026-11-01 |
| The 3.5 Super VL card lists structured output and function calling as supported, commercial use allowed | `OBSERVED` | build.nvidia.com model card, 2026-11-01 |
| The hosted endpoint honours `response_format` json_schema for this model | `INFERRED` | NIM VLM docs; not yet called with a key (no key on this machine) |

## Author / date

- Author: Claude (for the owner)
- Date: 2026-11-01
