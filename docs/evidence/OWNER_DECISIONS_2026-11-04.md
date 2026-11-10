# Owner decisions, 2026-11-04

The agent put 56 decisions to the owner over several rounds, each with a recommendation, and the owner answered "Yes to all" each time. Where this conflicts with [OWNER_ACTIONS_2026-11-03.md](OWNER_ACTIONS_2026-11-03.md) or an older guide, this record wins. Vocabulary is in [GLOSSARY.md](../../GLOSSARY.md).


## Catalog and makers

| # | Decision |
|---|---|
| 1 | Changed by 65 on 2026-11-08. Maker permission basis is option C: official spec pages count as publication for facts, with an opt-out; anything beyond facts, or a maker whose terms forbid automated access, needs permission. [ADR 0002](../adr/0002-maker-permission-basis.md). Counsel reads the policy before any sale or bulk export of the catalog. |
| 2 | Proxy tier is `basic` by default, with `stealth` or `auto` only under a recorded approval naming the tier. Land #254. |
| 3 | Changed by 66 on 2026-11-09. 401, 403 and 451 on a page, and 401 or 403 on robots.txt, are refusals and never reach a paid backend. |
| 4 | A Module is a unit that occupies HP in a Case, whether or not a Patch can use it. This overrides the brief's recommendation to retire the 11 power rows. |
| 5 | The 24 held video rows get a new VIDEO Module Category. |
| 6 | The 4 rows tagged both noise and random follow naming rules (option A in the brief) for now. |
| 7 | Retire `jolin-getrekt-touch-waveshaper`; keep `jolin-getrekt`. |
| 13 | Blank Panels aren't Modules, so the definition is "a *working* unit that occupies HP". |
| 14 | A new SYSTEM Module Category covers rack infrastructure: the 11 power rows, plus any fans and USB power panels among the 9 "probably not modules" rows. Check those 9 on maker pages, and retire whatever never occupies HP, such as connectors and bare PCBs. |
| 15 | An in-rack power supply's output is never added to a Rig's power budget. The builder warns that it isn't counted. |
| 16 | Add a NOISE Module Category, in its own PR after spec 003 lands. New runs on affected Rigs may differ; old runs are immutable. Loaded 2026-11-06 with #312: the owner chose not to wait for spec 003's T010, T031, T039 and T090 ([record](CATALOG_NOISE_CATEGORY_2026-11-05.md)). |
| 17 | Rectifiers (5) go to UTIL and crossfaders (3) to MIX. Firmware platforms (10) stay empty. Mutable-derived modules (12) get a reviewed name-to-category table, and the catalog's own Mutable rows are checked against the maker's docs (Ripples and Yarns look wrong as VCO). |
| 18 | Changed by 67 on 2026-11-09, for one render. Free reads come first: the 281 feed rows and the 59 or more maker pages, by plain GET. Paid fetches are only for T035, under a 50 context.dev credit cap. A site that blocks stays blocked. |
| 19 | The opt-out address is `catalog@patch-hive.com`, published on the site's About page and in the source policy once the owner has created it. |
| 20 | The agent applies catalog loads to staging once the dry run looks right. Each production load needs the owner's yes, with the plan and inputs hashes. Staging always goes first. |
| 30 | For the 17 unsourced HP values: retry maker pages by plain GET, then the owner sends drafted emails for the rest. With no reply in about 4 weeks, those rows stay `legacy_unsourced` and T039 closes. |

## Privacy, money and legal

| # | Decision |
|---|---|
| 24 | Publish a factual privacy notice before the owner's real sign-up test, marked as not yet reviewed by counsel. Sign-ups stay open. It must say that expired photos are refused when read but their files stay until the expiry job runs. |
| 25 | The notice names Zero-State LLC as operator, with the jurisdiction left off until the owner gives it. |
| 26 | Rig photos keep the 30-day default and 90-day maximum, with counsel still to confirm. Re-check that no older long-retention images exist before closing this. |
| 27 | The Patch Book licence stays undecided while publishing is off (`no_public_sharing`). This replaces Jev's provisional pick. |
| 28 | Report limits stand as built. How long to keep reports goes to counsel. |
| 29 | Fix the SVG escaping in `backend/export/visualization.py` now, not when publishing returns. |
| 32 | Prices (004 OQ-1) are **not ratified**, and there are no sales during beta. This replaces the record that says provisionally ratified. T046 to T053 stay open. |
| 33 | Counsel's answers are required before real sales, publishing, or sending anyone's photos to NVIDIA outside staging. On staging, the provider only sees the owner's own photos. Changed by 64 on 2026-11-08: on staging it may also see the corpus's openly licensed Commons photos. |
| 34 | Publishing stays off through beta, and T033 waits until after it. |

## Process and platform

| # | Decision |
|---|---|
| 8 | Vocabulary: Rig is canonical and Rack is legacy; Case is the enclosure; Module Category and Patch Category are separate terms. |
| 9 | Changed by 64 on 2026-11-08. Corpus photos come from the owner's own modules, and the validator's minimum of 50 stays. |
| 10 | 006 T060b verifies only the wired provider (NVIDIA through the Clef adapter), with no separate Clef evaluation. |
| 11 | `frontend-e2e`, `backend-lint`, `secrets`, `audit` and `migrations` become required checks once #276 lands, so every future migration needs a working downgrade on an empty database. The owner applies this. |
| 12 | The repo stays public. |
| 21 | Evidence expiry gets its own environment, `production-expiry`, with no reviewers, a main-only rule, and only the production database and storage secrets. The owner sets it up with T101b, and the agent writes the job. It should run before the first real image uploads. |
| 22 | VoiceOver with Safari plus the PDF reading-order check are enough to exit beta. NVDA with Firefox moves to the release candidate. |
| 23 | Merging a spec PR counts as the owner's T001 confirmation. |
| 31 | The owner is the only required reviewer on `production`, with a main-only rule, admin bypass off and "Prevent self-review" off. The owner applies this. |

Decision 4's "occupies HP" reads with decision 13's "working". Decisions 19 and 24 depend on steps only the owner can take, so neither goes live until those are done.

## From the spec reviews

Spec 001, 002, 003 and 004's T001 reviews (#282, #279, #284, #281) left these open. Decisions 39 and 49 to 51 refine the catalog decisions above.

| # | Decision |
|---|---|
| 35 | Superseded by 59 on 2026-11-07. A photo-confirmed Module is listed as still to place, with placement through the existing rack route. The API doesn't say `ready_for_generation: true` until it's placed. No auto-placement (#283). |
| 36 | A Module doesn't fill two roles in one Patch unless the catalog declares separate sections. |
| 37 | The spec 002 page and book compile machines aren't built. If a patch doesn't fit, the whole export fails and the customer's credits come back. |
| 38 | Book thresholds stay `NOT_COMPUTABLE` until approved, the publication profile flag stays off, and the spec wins over the truncated source extracts. |
| 39 | Anonymous reads of `GET /api/modules/catalog` leave out rows whose `access_basis` is `unknown`, after checking how many rows that removes from the Modules page; if it guts browsing, it comes back to the owner. The full question goes to counsel. |
| 40 | FR-031 per-run rollback stays required, and T090 builds it. |
| 41 | Try the maker's page for Akemie's Castle (18 HP versus 38) under the free reads. If it's blocked, mark HP as unknown rather than pick one. |
| 42 | A paid invoice on a canceled subscription keeps granting credits. |
| 43 | Any live subscription (`active`, `trialing`, `past_due`) can schedule a cancel. |
| 44 | A referral reward no longer pays out to a referrer who has deleted their account. |
| 45 | A user who never subscribed and one whose subscription lapsed both get FREE before sales open. Today's default stays during beta. |
| 46 | Parked: the STUDIO usage cap and operator resolve for subscription events wait for sales; disclosing provider data to customers and retention after account deletion go in the counsel brief. Operators keep rejecting subscription events. |
| 47 | Add a delete-account control with a clear confirmation step to the Account page, before the owner's real sign-up test. |
| 48 | The privacy contact is `privacy@patch-hive.com`, separate from `catalog@`. The owner creates it, and the notice's gap stays until then. |
| 49 | The 35 further video rows filed under other categories move to VIDEO. |
| 50 | Mutable-derived rows that rest only on a reviewer's knowledge come out of the overlay until a maker page confirms each. |
| 51 | Confirm and fix filled catalog rows keeping `modules.module_type` as UNKNOWN on a loaded database, before the catalog load. |
| 52 | The API stops returning `modulargrid_url` and `modulargrid_id`, and the leftover ModularGrid text on the Modules page goes. The next load clears those URLs from the 179 `CatalogCandidate` rows on production and tags them `unknown` (FR-033). Clearing production data needs the owner's yes at that load. |
| 53 | For the other 730 rows with no `access_basis`, the basis follows the source: the 721 maker-sourced rows become `official_publication` under decision 1, once each is checked to come from a maker's own site, and the 9 `SynthCatalogResearch` rows become `unknown`. |
| 54 | LZX DC Distro 3A and 5A become SYSTEM. The other 9 rows that link to video only through their brand stay as they are until a maker page says otherwise. |
| 55 | The 3 Rings-derived rows come out of the overlay until a maker page settles their category, under decision 50. |
| 56 | For this load, accept that the same rig revision and seed can give different patches, because the revision hash omits `module_type`. Old runs don't change. The hash gap is filed as its own bug, because changing the hash would invalidate every existing revision. |

## Photo-first product (2026-11-07)

The owner chose each recommendation, after an agent showed how far the product had drifted from its central job: a photo of the Rig in, a Patch Book out. [Spec 009](../../specs/009-photo-to-patchbook/spec.md) and [ADR-007](../adr/ADR-007-photo-first-product.md) carry them.

| # | Decision |
|---|---|
| 57 | A Rig owner gives PatchHive a photo of the whole Rig, or one per row for a big Case. PatchHive reads every Module and its Position, and asks for a closer photo only when it can't tell a Module apart. |
| 58 | Modules, Products and Cases leave the navigation and the public routes. The catalog stays as what a Reading matches against, and searching it is how a misread Module gets fixed. The placement editor becomes "correct the layout". |
| 59 | Positions read from a photo count as placement once the owner confirms the Reading, so generation doesn't wait for manual placement. A Position can still be corrected. This supersedes decision 35. |
| 60 | The journey is tested at two seams: the API journey from photo to exported book with a recorded provider answer, in CI, and the staging walkthrough starting from a fixture photo. |
| 61 | A provider that sends a photo away, such as NVIDIA, reads only a photo whose owner agreed to that when they uploaded it, and the Photo screen asks. Without that agreement the Reading fails `CONSENT_NOT_GRANTED` and nothing is sent. This sits beside the host gate: counsel still answers decision 33 before anyone's photo is read outside staging. Chosen 2026-11-07, on T022. |
| 62 | The staging walkthrough from a photo (spec 009 T060a) runs beside spec 008's walkthrough, with a receipt of its own. Spec 008's walkthrough still starts from the seeded Rig, and its receipt still gates `BETA_ELIGIBLE`. Spec 009's Seam 2 is tested at the photo walkthrough and its receipt, not through spec 008's receipt as T010 first set it. Chosen 2026-11-08, on T090 (D1). |
| 63 | The rig builder's per-Module photo step (spec 005) is removed: the whole-Rig photo is the product's one way in for photos (ADR-007). Its mock detector derives candidates from each photo's hash, so in production it would offer someone Modules no one saw; it never runs in production. Staging keeps it for its evidence check on a test card (006 T060b). The evidence, confirmation and reconciliation APIs stay. Chosen 2026-11-08, on T090 (D14). |
| 64 | The evaluation corpus starts from the owner's own Rig. Openly licensed Wikimedia Commons photos may fill the Modules and cohorts it doesn't cover, each with its licence, author and source page recorded. Only Commons qualifies for now: the other sources a search turned up (Reddit, Facebook, shops and blogs) carry no open licence. The photos stay on Commons, pinned by hash, and aren't committed. An agent may draft a photo's labels, but a case counts only once the owner has checked them. On staging, the provider may read these Commons photos as well as the owner's own, and no one else's. This changes decisions 9 and 33. Chosen 2026-11-08, on T070b. |
| 65 | Official maker sites now cover more than facts: descriptions, manuals and pictures on a maker's own site may be crawled and used, along with name, HP, power, depth and category. The owner reports that most of the makers they contacted say this material is Creative Commons; those replies aren't in this repository. Where a maker's own licence sets conditions, such as credit, they apply. The other conditions stay: maker-owned domains only, robots.txt honoured, a per-host delay, no route around a block, the opt-out, and permission first from a maker whose terms forbid automated access. This changes decision 1. It doesn't change decision 64, so only Commons photos join the evaluation corpus. Chosen 2026-11-08. |
| 66 | A 403 on robots.txt whose body is a file-storage service's own error reply (an S3-style `AccessDenied` or `MissingKey` error, or `Missing Authentication Token`) means the host has no robots.txt, and it's treated like a 404. Such services commonly answer 403 for a file that doesn't exist. Every other 401 or 403 on robots.txt stays a refusal under decision 3, as do a bot check and a 401, 403 or 451 on a page, including a file that itself answers 403. None of those reach a paid backend. In the 2026-11-09 maker crawl this covered 777 files, including Make Noise's manuals. |
| 67 | One paid render of 21 makers' sites that looked script-built, on context.dev, for at most 500 credits (approval `maker-render-2026-11`, now closed). It used 254. Eight of the sites were serving a bot check the router didn't recognise, so 226 pages went past it, against decision 3: see [the record](CATALOG_RENDER_BOT_CHECK_2026-11-09.md). Decision 18's limit stands for everything else. |

