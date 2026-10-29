# Research: 003-catalog-dataset-pipeline

Decision research for the open catalog decisions (2026-10-29). Each item gives the evidence, the options and the recommendation. Labels follow the spec: `[OBSERVED: <source>]` or `[INFERRED]`.

## R1. Correcting a wrong stored value (decision note §3; D4, FR-038)

**Evidence**

- `modules` row Sovage Engineering CHICANE holds `hp = 14`, `verification_status = verified`, `verification_source_url = …/product-page/chicane-1u`, `needs_reverify = true` [OBSERVED: prod query 2026-10-29].
- The Eurorack page `…/product-page/chicane` gives 4 HP, +12 V 24 mA, −12 V 28 mA, +5 V 0, 12 mm [OBSERVED: hermes-research/maker-crawl-v2.json]. The `module_catalog` row already holds 4 HP, and the module's power and depth already match that page.
- `maker-review-v1` archived the 14 and flagged the row, because `modules.hp` is NOT NULL and the loader can only fill nulls [OBSERVED: provenance/maker-review-v1.json, catalog_value_archive]. The FR-035 guard blocks placement while an `hp` archive row has action `flag` [OBSERVED: backend/racks/validation.py].

**Options**

1. A `correct` provenance action: archive the old value, then write the new one only while the stored value is still `only_if_value`, citing the maker page.
2. Admin edit in the UI. It leaves no manifest, so it is not reproducible on a fresh database (FR-028).
3. Clear `needs_reverify`. That doesn't fix the value, and the flag also covers other fields.

**Recommendation:** option 1. The guard lifts when a `correct` row for `hp` exists. Manifests start carrying values; each value must cite a maker page (D4). First use: CHICANE `hp` 14 → 4 and `verification_source_url` `…chicane-1u` → `…chicane`.

## R2. `seed_catalog_from_synth.py` (decision note §4; D5)

**Evidence**

- Two drifted copies: `scripts/` (4 KB) and `backend/scripts/` (8 KB). No workflow, Makefile or script calls either [OBSERVED: repo grep 2026-10-29].
- They overwrite HP, category and source unconditionally, and fill a missing HP with 10 and a missing type with VCO, against FR-022 and FR-024 [OBSERVED: decision note §4].
- Their only test, `tests/unit/test_seeder_catalog.py`, is permanently skipped and checks registry slugs on a pre-seeded database [OBSERVED].
- The registry no longer needs the slug fill: it reads makers' models from `module_catalog` by brand name or alias (#114) [OBSERVED: backend/registry/services.py].

**Recommendation:** delete both copies and the skipped test. The loader is the only writer (D5).

## R3. Paid Frap listing adapter (T026)

**Evidence**

- Frap Tools: `discovered = 0, pages = 0` [OBSERVED: maker-crawl-v2.json]. Squarespace's `?format=json` comes back rendered, and the site drops direct connections [OBSERVED: earlier runs].
- A rendered listing pass needs 1–2 renders to test, then about 20–60 for product pages [INFERRED from Frap's catalog size].

**Recommendation:** owner sets a cap (suggest 80 context.dev credits). Run a free dry run first. Never route around a block (decision note §5).

**Update 2026-10-29:** `frap.tools` resolves (46.252.150.74) but accepts no TCP connection on 80 or 443 from the crawl network [OBSERVED: curl and nc, 2026-10-29]. That is a refusal at the network level. A paid renderer would reach it from another network, which is routing around it. **Decided (D7):** no paid pass. Frap is excluded like Tiptop until the maker supplies data or access, and T026 closes.

## R4. Rebuilding the maker-crawl page cache (T031)

**Evidence**

- The cache was deleted on 2026-10-28 with a worktree. Committed crawl results are intact [OBSERVED].
- The full v2 crawl used 2,569 paid fetches: about 1,116 context.dev credits and 33 Firecrawl credits [OBSERVED: receipts/scrape-ledger.json]. A full rebuild would cost about the same.
- 644 catalog rows still lack a category because their pages had no tags [OBSERVED: #115].

**Recommendation:** don't rebuild on its own. Rebuild only for a change that must re-parse pages, scoped to the brands it needs.

**Update 2026-10-29:** R3 no longer needs a pass (D7). The one change that needs pages read again is D8 (jumper settings), so a scoped re-fetch is T035: the 4ms modules whose draws were left unknown, plus Dave Jones Design Otool and Velectronic A-Envelope. That's about 46 product pages, an estimated 20–50 context.dev credits at the v2 crawl's rate (about 0.44 credit per call). It waits on an owner cap.

## R5. Jumper-dependent power (decision note §1)

**Evidence:** 4ms and other makers publish draws per jumper setting; the loader keeps those rails unknown (FR-022) [OBSERVED: provenance/maker-crawl-v2-jumper-fix-v1.json]. Per-rail unknowns are now reported (#118).

**Options**

1. A `power_configs` JSON column: one +12/−12/+5 set per setting, each with its source.
2. Store the worst case per rail. That mixes two settings into a draw neither one has.

**Recommendation:** option 1, as its own spec slice. It needs a migration, a loader action and UI to pick a setting.

**Decided (D8, 2026-10-29):** option 1. Not built yet: the committed crawl keeps one value per page, so there's nothing to load until T035 reads the settings from the maker pages.

## R6. Spec confirmations (001–004 T001)

Each spec is still DRAFT with `[INFERRED]` claims the operator must confirm. These are operator sittings, not engineering. Recommendation: one sitting per spec, starting with 003, whose open questions are now mostly settled (D1–D6).
