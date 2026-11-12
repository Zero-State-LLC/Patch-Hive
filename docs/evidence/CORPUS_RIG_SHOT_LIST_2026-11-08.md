# Evaluation corpus: whole-Rig shot list, 2026-11-08

For spec 009's T060b (the staging walkthrough) and T070b (the evaluation corpus), when you're photographing a Rig you've borrowed: a friend's, a shop's or one at a meetup.

One Rig, about ten minutes and five photos can cover what's still missing:

| Still needed | Why |
|---|---|
| One clean photo | T060b's walkthrough starts from it, and it's the reference for labelling the others |
| `low_light_or_glare` | No case in the corpus yet |
| `partial_occlusion` | No case in the corpus yet |
| `revision_or_panel_variant` | No case in the corpus yet |

## Before you start

1. **Get the Rig owner's OK in writing.** Use the permission note. In a shop, ask whoever can speak for the Rig.
2. **Set your phone to JPEG.** PatchHive reads JPEG, PNG or WebP, and not HEIC. On an iPhone: Settings, Camera, Formats, Most Compatible.
3. **Use the normal photo mode, at 40 MP or less.** Each file can be at most 12 MB, so avoid 48, 50, 108 or 200 MP modes. Leave out Portrait, Live and filters.
4. **Turn off location tagging.** These photos can go to an outside provider during testing.
5. **Keep people and private things out of frame:** faces, customers, receipts, price tags, screens.

## Every shot

- Get the whole Rig in frame, with a little margin and the top and bottom rails visible.
- Stand square-on to the panels, or as close to it as the Rig allows.
- Don't move the Rig or swap any Module between shots, so one set of labels fits all five.
- After each shot, zoom in and read a small panel label. If you can't read it, take it again.
- Don't crop, edit or screenshot afterwards. Each case pins the file's exact hash.

## The five shots

| File | Shot | How |
|---|---|---|
| `reference` | Clean | Even light, no flash, no hands. Unpatched if the owner is happy to pull the cables; otherwise as few cables as possible. |
| `low-light` | Dim | Room lights down, no flash. You should still just be able to read the panels by eye. |
| `glare` | Reflection | A lamp or window reflecting across part of the panels. Take this or `low-light` if you only have time for one. |
| `occluded` | Partly hidden | A hand, a sheet of paper or headphones covering about a fifth of the panels, somewhere in the middle of a row. |
| `variant` | Panel variant | Only if the Rig holds a Module whose panel exists in another version, such as a Doepfer vintage panel, a black edition, or a Mk1 where a Mk2 exists. Frame the whole Rig as usual and note which Module it is. |

If the Rig has no panel variant, skip that shot. That cohort will need another Rig or a Commons photo.

## Write down, for each Rig

- Each row from the top, left to right: maker and name as printed on the panel, plus any blank panels and gaps.
- The case's width in HP, if you know it.
- For `variant`: the Module, and the version printed on its panel.
- Who owns the Rig, and the date.

The owner's own list is the best check on the labels, so ask them for it if they have one.

## Limits worth knowing

- **The corpus allows at most 100 different catalog Modules, and it holds 63.** A Rig that adds more than 37 new ones would put it over. If it's that big, a Commons case may have to come out first.
- **Keep shots of one Rig in one partition.** They aren't independent of each other.
- **Modules the catalog doesn't have are fine.** They get labelled as off-catalog.

## Handing them over

Put them outside the repo, in `~/patchhive-corpus/own/`, named `<rig>-<shot>.jpg`, for example `rig-a-reference.jpg`. Put the written list and the signed note beside them.

**The one exception is the walkthrough photo.** T060b's workflow reads `fixtures/photo-walkthrough/rig.jpg`, which is in the public repo, so that photo needs the "show it publicly" box ticked on its permission note.

## What happens next

An agent hashes the photos and drafts the labels from the `reference` shot and your list, and you check them the way you checked the Commons ones. Each case records `source_url: operator://local` and a `consent_record` naming the note. T060b's recording is built from the checked labels. T060b says "their own Rig", so that wording needs a small change if this isn't yours.
