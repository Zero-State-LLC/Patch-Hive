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

**Update 2026-10-29:** R3 no longer needs a pass (D7). The one change that needs pages read again is D8 (jumper settings), so a scoped re-fetch is T035: about 45 product pages: the 42 live 4ms modules (41 with an unknown rail), the 2 Dave Jones Design modules and Velectronic A-Envelope. That's an estimated 20–50 context.dev credits at the v2 crawl's rate (about 0.44 credit per call). It waits on an owner cap.

## R5. Jumper-dependent power (decision note §1)

**Evidence:** 4ms and other makers publish draws per jumper setting; the loader keeps those rails unknown (FR-022) [OBSERVED: provenance/maker-crawl-v2-jumper-fix-v1.json]. Per-rail unknowns are now reported (#118).

**Options**

1. A `power_configs` JSON column: one +12/−12/+5 set per setting, each with its source.
2. Store the worst case per rail. That mixes two settings into a draw neither one has.

**Recommendation:** option 1, as its own spec slice. It needs a migration, a loader action and UI to pick a setting.

**Decided (D8, 2026-10-29):** option 1. Not built yet: the committed crawl keeps one value per page, so there's nothing to load until T035 reads the settings from the maker pages.

## R6. Spec confirmations (001–004 T001)

Each spec is still DRAFT with `[INFERRED]` claims the operator must confirm. These are operator sittings, not engineering. Recommendation: one sitting per spec, starting with 003, whose open questions are now mostly settled (D1–D6).

## R7. The 221 unsourced HP values in `module-catalog-hp-v1` (FR-004, D2)

**Evidence**

- `overlays/module-catalog-hp-v1.json` holds 221 fill-null HP entries. None has a `source_url`; 186 are `source_class = maker_or_retail` and 35 `unknown_non_modulargrid` [OBSERVED].
- The loader now accepts an HP overlay entry only with `source_class = maker` and an https `source_url`. v1 is let through by name (`UNSOURCED_HP_OVERLAYS`) [OBSERVED: data/synth-catalog/population.py:839].
- Matched by brand and name against the committed maker crawl (`hermes-research/maker-crawl-v2.json`, 2026-10-29): 45 agree with a maker page, 7 disagree, 169 have no maker HP [OBSERVED: local comparison]. The 169 are mostly Doepfer (50), Bastl (27), ADDAC (26), Befaco (12) and Intellijel (11).
- The 7 disagreements: Acid Rain Junction (6 vs 4), ALM Akemie's Castle (18 vs 38), Befaco Hexmix VCA (12 vs 14), Intellijel Quadrax (12 vs 14), Make Noise DPO (30 vs 28), Make Noise Morphagene (18 vs 20), Qu-Bit Data Bender (12 vs 14). The crawl is not always right: Akemie's Castle is widely listed at 18 HP, so 38 looks like an extraction error [INFERRED].
- Flagging an HP value blocks rack placement (FR-035), so flagging all 221 would block common modules [OBSERVED: backend/racks/validation.py].

**Options**

1. Keep all 221 grandfathered. Simple, but D2 says retailer values come only from one-off manual lookups, and these carry no lookup record.
2. Flag all 221. Honest, but blocks placement of 221 modules until each is re-checked.
3. Triage: re-source the 45 that agree (a v3 HP manifest citing the maker page, no value change); check the 7 by hand against the maker page and fix the wrong ones with `correct` entries (D4); keep the 169 grandfathered but mark them `hp_source = legacy_unsourced` so the catalog can show "HP not maker-checked"; then look up the 169 on maker pages (Doepfer and Bastl publish HP on free pages) and retire `UNSOURCED_HP_OVERLAYS` when the list is empty.

**Recommendation:** option 3. It fixes the known errors now, keeps placement working, and makes the remaining gap visible and finite. Effort: M (one manifest builder, one small API field, a free lookup pass). Awaits the owner (tasks T038, T039).

## R8. A correction leaves `needs_reverify` set (row lifecycle, FR-038)

**Evidence:** the lifecycle table says `FLAGGED --correct--> LIVE` [OBSERVED: spec.md, Row lifecycle]. `_correct_row` writes the new value and `updated_at` only; nothing in the loader ever sets `needs_reverify = FALSE` [OBSERVED: data/synth-catalog/population.py:585]. CHICANE's HP block lifts only because the FR-035 guard also looks for a `correct` archive row [OBSERVED: backend/racks/validation.py]; the flag itself stays set, so counts of flagged rows and the admin view still show it.

**Recommendation:** not a decision; the spec already says what should happen. Clear `needs_reverify` in the same UPDATE when every field this row was flagged for has a `correct` archive row. Keep it set if another flagged field is still open. Effort: S (task T036).

## R9. A tombstoned row can still be corrected or flagged (row lifecycle, D3)

**Evidence:** `TOMBSTONED` is final [OBSERVED: spec.md, Row lifecycle]. The retirement UPDATE checks `tombstoned_at IS NULL` [OBSERVED: population.py:931], but `_row_where`, used by archive, correct and reverify, matches on slug, brand and name only [OBSERVED: population.py:525]. A later manifest that names a retired row would archive and rewrite it.

**Recommendation:** not a decision. Add the tombstone check to the archive, correct and reverify statements, and count a skipped entry in the receipt as `refused: row_tombstoned`. Effort: S (task T037).
