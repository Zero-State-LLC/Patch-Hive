# Intent

## Problem

Almost no catalog row has `io_ports` (2 of 3,379 public Modules on 2026-11-09), so Patch Books print role names such as "Audio Out" instead of a Module's real jacks. The 2026-11-09 maker crawl holds pages and manuals that name those jacks, but pattern matching can't read them.

## Proposed outcome

`scripts/read_module_jacks.py` reads each Module's maker page and user manual with a low-cost model and writes a proposal of complete jack lists, a review sample and the proposal's hash.

A Module is proposed only when two differently worded readings of one document both call the list complete, agree on every jack, and quote text found in that document.

`read` does the same reading through OpenRouter, which the owner chose on 2026-11-09. It uses the same Haiku 5.5 model the pilot checked by hand. OpenRouter's price is the batch price doubled, so `read` also holds each request's largest possible charge against the cap before sending it.

Out of scope: running the paid step, which needs the owner's API key and a spending cap, and loading any list. A load needs a reviewed PR and the owner's yes on its hashes.

## Affected users / systems

Catalog tooling only. No product, API or database change. Maker documents already in the private crawl bucket are sent to the Anthropic API for reading.

## Constraints / non-goals

- Fail closed. A partial list is worse than none, because the engine sends a cable to the first free jack of the right type (`patches/validation.py`). Partial lists are dropped, not stored.
- Facts come only from the maker's own page or manual (decision 65), never from a model's memory and never from ModularGrid.
- `submit` refuses without a dollar cap, refuses a second batch while one is uncollected, and doesn't pay twice for a good reading.
- The model is given no tools, and documents are marked as untrusted data, so a page can at worst distort its own list. The quote check, the second reading and the review sample are there for that.
- A document longer than the limit is skipped, not cut, so a cut manual can't read as complete.

## Open questions

- Whether to allow lists that both readings agree on when only one reading calls them complete. They would add coverage but are shakier. The readings are kept, so this can change without paying again.
- What a load should write, and whether a list needs a provenance column, belongs to the load PR.

## Verified / assumed claims

| Claim | Label | Basis |
|---|---|---|
| The reader got 279 of 292 jacks right across 50 pages and 14 manuals; 13 errors were on two Modules | `OBSERVED` | Hand comparison against a blind reading, 2026-11-09 pilot |
| Replaying those readings through the gate accepts 19 lists, all complete by the blind reading, and blocks both wrong lists | `OBSERVED` | `decide` on the pilot's readings |
| "Complete" means the document appears to cover every jack, not that it matches the physical panel | `NOT_COMPUTABLE` | No panels were checked |
| Two differently worded readings catch random slips but not a mistake both make | `INFERRED` | Same model, same document |
| `read` works against OpenRouter | `OBSERVED` | 6,356 readings on 2026-11-09, all usable, $3.87 in total |
| The run proposes 230 of 2,514 Modules read | `OBSERVED` | `decide` on those readings |
| 23 of 25 accepted lists checked by hand were right; the 2 others gave one channel of a dual Module and are now excluded | `OBSERVED` | Hand comparison with each document, reading only the jack-related lines of 15 of them |
| `submit` and `collect` work against the Message Batches API | `NOT_COMPUTABLE` | No batch has been sent; tested with the API faked |

## Author / date

- Author: Claude Opus 5.5, for the owner
- Date: 2026-11-09
