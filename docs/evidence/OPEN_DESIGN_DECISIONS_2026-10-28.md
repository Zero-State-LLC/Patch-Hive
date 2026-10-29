# Open design decisions (2026-10-28)

Research from a read-only pass over the code and specs, for decisions that need the owner. Each has a recommendation; the matching cards are on [Project #8](https://github.com/orgs/Zero-State-LLC/projects/8) under `[decision]`. Settled since the research: module and case writes are admin-only (#79), users own their racks (#80), catalog rows are retired by tombstone (#116, decision 2), and the Products page reads the module catalog (#114, the registry half of decision 4). Updated 2026-10-28 evening.

## 1. Unknown power draws count as 0 mA — fixed (#118)

**Fixed 2026-10-29 (#118).** Per-rail unknowns, a NULL +5V counts as unknown, one rounding rule. Jumper-dependent draws are still open: spec 003 research R5, task T034.


This is a bug, so it does not wait on a decision; it is a `[api]` card in Ready.

- `backend/racks/validation.py` adds a NULL draw as 0 with no warning, so it can pass an over-budget rack.
- `backend/cases/compatibility.py` warns about unknown draw only when all three rails are NULL. It treats a NULL +5V as "does not need +5V" and returns `verified`, which is wrong for a 4ms jumper module set to external 5V.
- `frontend/src/pages/RackBuilder.tsx` marks a module unknown when +12V is NULL and then also drops its known -12V.
- `scripts/apply_module_power_depth_overlay.py` truncates 3.5 mA to 3; the loader rounds it to 4.

Fix: per-rail unknowns (a rail with any unknown draw is `incomplete`, "≥ X mA + N unknown"), a NULL +5V counts as unknown, per-rail counts in the UI, and one rounding rule.

**Decision (later):** how to model jumper-dependent draws. Recommended: a `power_configs` JSON column with one +12V/+5V/-12V set per jumper setting, each with its source, so a budget can check that some setting fits the case. Storing the worst case per rail mixes two settings into a draw neither one has. Until then these rails stay unknown, as spec 003 FR-022 requires.

## 2. Retiring a bogus catalog row (TLM "ST MODULAR") — settled

**Settled 2026-10-28 (#116).** `module_catalog` gained `tombstoned_at` and `tombstone_reason`; `modules` uses `status = 'tombstoned'`. The loader tombstones rows named in `overlays/catalog-retirements-v*.json` (each with evidence), never deletes. Browse, search, counts and batch materialize skip them; a slug lookup still answers; materializing one is 409. First use: the TLM row and 262 rows the crawl filed under the wrong brand (seven brands were given another maker's homepage). Rack validation does not yet warn on existing placements of a tombstoned module (no prod racks use them).

The research below is kept for the record.


- `modules` already has `status` (active, deprecated, tombstoned) and a soft delete; `module_catalog` has only `is_available`.
- Catalog browse shows every row by default, materialize returns a tombstoned module, and rack validation ignores `Module.status`.
- The admin merge endpoint only relabels the old row; it does not move users' racks.
- Nothing references catalog rows by foreign key, and `rack_modules` cascades on hard delete, so retire softly.

**Recommendation:** a `retire` loader action that archives the old values and sets `status = tombstoned`, `is_available = retired`; browse hides retired rows by default, materialize skips them, validation warns on existing placements.

## 3. Correcting a wrong `modules.hp` (Sovage CHICANE: stored 14, true 4) — decided

**Decided 2026-10-29 (spec 003 D4, FR-038; #125).** A `correct` provenance action archives the old value and writes a new one cited to a maker page, only while the stored value is `only_if_value`. An HP correction lifts the FR-035 block. First use: CHICANE 14 → 4. The research below is kept for the record.


Nothing in the loader or admin tools can change `modules.hp` after insert. The FR-035 placement block lifts only when `needs_reverify` is false, and nothing sets it back.

**Recommendation:** a `correct` manifest action that archives the old value, updates it under `only_if_value`, and lets a later correction outrank the earlier HP flag (rather than clearing `needs_reverify`, which also covers CHICANE's depth). Manifests would start carrying values: a policy change. Existing racks re-validate at 4 HP, which leaves gaps but never overlaps.

## 4. `seed_catalog_from_synth.py` and Device Registry links

- Two drifted copies (`scripts/` and `backend/scripts/`); no automation runs either.
- The registry match is circular: device slugs derive from the same seed (376 of 376 match by slug).
- The update path overwrites HP, category and source unconditionally, and it fills a missing HP with 10 and a missing type with VCO, against spec 003.

**Recommendation:** delete both copies; have the loader fill `registry_manufacturer_slug` (empty only); leave the device slug empty until `device_models` is populated.

**Registry half settled 2026-10-28 (#114).** Confirmed: the snapshot was not in the API image, so search and every maker's models were empty in production. The registry now reads a maker's models from `module_catalog` (brand name or alias), so it no longer needs the snapshot or the slug fill. Seed scripts deleted 2026-10-29 (spec 003 D5, T032). Decision 3 (the HP correction) is spec 003 D4 / FR-038, implemented in T033.

## 5. Scraping policy

Settled: maker pages and manuals only, no ModularGrid fetching, robots.txt respected (spec 003 D1/D2). Open:

- **Maker permission.** `docs/EXTERNAL_SOURCE_POLICY.md` says bulk operations "fail closed without permission metadata". The paid maker crawl (3,429 modules) has no permission record. Decide whether official spec pages count as public publication (and record it), or contact makers.
- **Stealth proxy.** Firecrawl's stealth proxy is enabled by configuration with no recorded sign-off. Recommendation: basic proxy only.
- **Blocked sites.** One rule for Frap (drops connections) and Tiptop (CAPTCHA): never route around a block; ask the maker for data or access.

## 6. Budget approvals (spec 003 FR-003)

Two runs now wait on a cap: the Frap listing adapter (T026) and rebuilding the maker-crawl page cache, which was deleted on 2026-10-28 with a worktree (T031). The committed crawl results are intact; the cache is only needed to re-parse pages.

Paid runs need a recorded budget approval; caps so far are written into `data/synth-catalog/SCRAPING_ARCHITECTURE.md` by hand. Recommendation: an approvals receipt (who, cap, date) the crawler checks before any paid fetch.

## 7. Spec 003 housekeeping

The spec is still DRAFT with T001 (operator confirmation) open and `plan.md` and `research.md` as stubs. Two open questions are already settled by D2 (access basis for scraped rows; Thomann coverage) and can be closed. Still the owner's call: whether the catalog key becomes `(brand, slug)`, overlay file naming and schema, whether every admission needs three scrubbed runs, and coverage targets. Specs 001, 002 and 004 each list 13–14 open questions of their own.
