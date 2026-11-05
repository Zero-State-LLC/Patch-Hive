# Evaluation corpus: shot list for 007 T010b

The evaluation chain (specs 005, 006, 007 and 008) can't start without real module photos. `fixtures/vision_eval/pilot-manifest.json` has 0 cases. An earlier open-web search over 300 modules found only 6 rights-cleared images (`~/patchhive-corpus/review-queue.json`), far short of the minimum. This list covers what the owner has to supply.

## What the validator requires

`scripts/validate_vision_pilot.py` admits the corpus only when all of this holds:

- **50 to 100 different modules** across all cases.
- **At least one case in each of the 8 cohorts** below.
- **At least one case in each of** `validation`, `locked_test` and `unknown_open_set`.
- For every case: confirmed rights, a verified identity, a named reviewer, a candidate set that allows `none_of_above`, and an image hash.
- The same image never appears in two partitions.
- `unknown_open_set` cases expect `none_of_above`.

**If you own fewer than 50 modules,** this is the real blocker. Photos from a friend or a shop count only with their written permission, recorded in `consent_record`.

## What to shoot

Only the cohorts themselves are required. The counts are a suggestion that reaches 50 modules with about 70 photos.

| Cohort | Photos | How |
|---|---|---|
| `clear_front_panel` | 30 | One module, straight on, whole panel sharp and even light. A different module each time. |
| `installed_rack` | 12 | Modules in the case with neighbours in view, at normal viewing distance. |
| `partial_occlusion` | 6 | A hand, a case edge or another object covering part of the panel. |
| `cable_obscured` | 6 | Patched, with cables across the panel and labels. |
| `low_light_or_glare` | 6 | Dim room, or a light reflecting off the panel. |
| `revision_or_panel_variant` | 4 | Modules that exist in more than one revision or panel colour. Note which one. |
| `hard_negative` | 3 | Lookalikes: clones, or different modules with similar panels. |
| `unknown_open_set` | 3 | Modules that aren't in the catalog, such as DIY builds. These expect `none_of_above`. |

Use your phone's normal camera, save as JPEG, and don't filter or crop.

**Turn off location tagging first.** The live evaluation sends these images to a third-party provider.

## How to hand them over

1. Put the photos in `~/patchhive-corpus/own/`. They never go in the repo; it stores hashes only.
2. Name each one `<brand>-<model>-<cohort>-<n>.jpg`, for example `make-noise-maths-installed_rack-1.jpg`.
3. For any module with a revision or variant, add a line to `~/patchhive-corpus/own/notes.txt` saying which one, as printed on the panel.

Your file names are what mark the identity as verified, so name what you can actually see. You'll be the named reviewer on these cases.

## What happens next

An agent can then hash each photo, build the candidate sets from the registry, write the manifest entries, split the partitions before anything is measured, and run the validator until the corpus reads `ADMITTED_FOR_BASELINE`. The chain continues from there, and only the threshold approval and the signature stay with the owner.
