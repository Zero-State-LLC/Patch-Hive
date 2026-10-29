# Research: 002-patch-book-publishing

Decision research for the open 002 gaps (2026-10-29). Each item gives the evidence, the options, a recommendation and the effort (S, M or L). Labels follow the spec: `[OBSERVED: <source>]` or `[INFERRED]`. The fixes already merged (#101, #102, #130, #133) are listed in the spec's implementation status, not here.

## R1. No book validation stage and no per-page manifest (FR-016, FR-017; P2)

**Evidence**

- `compose_design_export_pack` writes `manifest/patch-book.json` with `page_count = len(layout_irs)`, the hashes and a `paths` block. It has no per-page entries (page number, patch id, page hash, SVG hash, validation status) [OBSERVED: backend/export/patchbook/design/engine.py].
- `manifest/checksums.json` holds only `composition_hash` and `pack_manifest_hash`. No file in the bundle has its own hash [OBSERVED: same file].
- The post-pack preflight checks that files exist (`PACK_FILE_MISSING`). It does not count PDF pages or check hashes [OBSERVED: backend/export/patchbook/design/preflight.py].
- `PATCH_BOOK_PAGE_COUNT_MISMATCH` and `PATCH_BOOK_ASSET_HASH_MISMATCH` appear nowhere in the code. `PATCH_BOOK_REFERENCE_UNRESOLVED` is used only by the legacy export route, for patches from another rig (#133) [OBSERVED: repo grep 2026-10-29, backend/export/routes.py].
- Plate mode (publication profile, behind `ENABLE_PATCHBOOK_PUBLICATION_PROFILE`, default false) adds a plate and an appendix page per patch to `layout_irs`. `_render_execution_pdf` still draws one page per patch. For a one-patch library the manifest says 4 pages and `PatchBook.pdf` has 3 [OBSERVED: probe run 2026-10-29 on the fixture in `tests/unit/test_patchbook_publication_dual.py`]. In general that is 2N+2 against N+2 [INFERRED from the code].
- `pypdf` is not installed. The renderer can count its own pages: one `showPage` per page [OBSERVED: backend venv, engine.py].

**Options**

1. Add a `validate_book` stage after render. It counts pages drawn and compares them with the manifest. It writes one manifest entry per page (index, kind, patch artifact id, layout IR hash, SVG hash, status) and a SHA-256 per bundle file in `checksums.json`. It also recomputes `composition_hash`. Each check fails with its code: `PATCH_BOOK_PAGE_COUNT_MISMATCH`, `PATCH_BOOK_REFERENCE_UNRESOLVED` or `PATCH_BOOK_ASSET_HASH_MISMATCH`.
2. Fix only the plate-mode count, by setting `page_count` to the pages drawn.

**Recommendation:** option 1. `PatchBook.pdf` is the page-count authority. Plates are not drawn yet, so plate mode fails `PATCH_BOOK_PAGE_COUNT_MISMATCH` until they are. The flag is off by default, so no user sees that failure. Effort: M.

## R2. Publishing does not check for a validated book (FR-048, OQ-6)

**Evidence**

- Publication exports are made by `_create_export_from_patch` and `_create_export_from_rack`. They use the legacy PDF and hash `{export_type, id, run_id, generated_at, artifact_urls}`. A publication export has no link to a Design Engine pack or a `PatchBookManifest` [OBSERVED: backend/publishing/routes.py].
- `update_publication` allows `draft` → `published` if the pair is in `OWNER_TRANSITIONS`. It checks nothing about the export [OBSERVED: same file].
- The whole router is mounted only when `ENABLE_LEGACY_PUBLISHING=true`, and that flag defaults to false [OBSERVED: backend/main.py, backend/core/config.py].

**Options**

1. Bind each publication export to a canon export whose pack passed book validation (a new reference, checked on publish). This needs R1 first.
2. Exempt legacy publishing from FR-048 while it stays behind the flag.
3. Refuse `draft` → `published` with 409 `PUBLICATION_BOOK_NOT_VALIDATED` for any export with no validated book. Today that is every export.

**Recommendation:** option 3 now. It fails closed, it's small, and it changes nothing while the flag is off. Take option 1 only if the owner wants publishing back as a product. Whether a publication export must bind a validated manifest at all is still the owner's call (OQ-6). Effort: S for option 3, L for option 1.

## R3. Visibility default and gallery filters (FR-036, FR-042)

**Evidence**

- `PublicationCreate.visibility` is a required `Literal["unlisted", "public"]` with no default. Only the database column defaults to `unlisted` [OBSERVED: backend/publishing/schemas.py, backend/publishing/models.py].
- The gallery's `export_type` is `Optional[str]`. An unknown value returns an empty list instead of an error [OBSERVED: backend/publishing/routes.py `list_gallery`]. `limit`, `recent_days` and `cursor` are already checked: a bad cursor returns 400 [OBSERVED].

**Recommendation:** give `visibility` the default `"unlisted"`, and type `export_type` as `Optional[Literal["patch", "rack"]]` so a bad value gets 422. Add a test for each. Effort: S.

## R4. Cover disclaimer and metadata (FR-004)

**Evidence**

- The cover draws `PATENT_FUTURE_DISCLAIMER` at 8 pt Helvetica with 10 pt line spacing, from 1.55 in below the top. The metadata block starts at a fixed 1.9 in, 25.2 pt lower [OBSERVED: backend/export/patchbook/design/engine.py].
- Only the Patent Future family sets `patent_disclaimer=True`, and the PDF is always US Letter [OBSERVED: backend/export/patchbook/design/families/registry.py, engine.py].
- The text measures 366 pt at 8 pt against a 468 pt line, so it takes one line today and does not overlap [OBSERVED: reportlab `stringWidth`, 2026-10-29]. A third line would put its baseline 20 pt below the first. The metadata text (9.5 pt or more) reaches up to about 18 pt below, so the two would overlap [INFERRED].
- 8 pt is under the 9.5 pt print floor. FR-004's note counts cover text as body text [OBSERVED: spec FR-004].

**Options**

1. Draw the disclaimer with `_draw_wrapped` at `body_size_pt()`, and start the metadata block at the y value it returns.
2. Keep 8 pt as a caption, exempt from the floor, but place the metadata block after the last disclaimer line.

**Recommendation:** option 1. The notice says what the document is not, so readers need to be able to read it. Both options remove the fixed offset. Effort: S.

## R5. Preflight warnings are dropped (OQ-7, FR-019)

**Evidence:** `run_preflight` blocks only on `severity == "error"`. Warnings such as `BODY_SIZE_RAISED_TO_FLOOR` and `INK_COVERAGE_HIGH` let the pack pass, and they are written nowhere in the pack [OBSERVED: backend/export/patchbook/design/preflight.py, engine.py]. So as built, a warning allows acceptance and leaves no record, against "warnings must never silently become passes".

**Recommendation:** list every preflight warning in the book manifest from R1, and in the stage receipt. Whether a warning may still allow acceptance stays the owner's call (OQ-7). Recording it is required either way. Effort: S, after R1.

## R6. Publication questions the code answers

- OQ-1: create makes a `draft`; the owner publishes it (#101) [OBSERVED: backend/publishing/routes.py `create_publication`].
- OQ-2: no. A publication an admin hid carries `moderation_audit_id`, and an owner status change gets 409 `PUBLICATION_UNDER_MODERATION` [OBSERVED: `update_publication`].
- OQ-3: no. Admin remove accepts only `published` or `hidden`; a draft gets 409 `INVALID_TRANSITION` [OBSERVED: `remove_publication`].
- OQ-4: the owner may edit the allowed fields in `draft`, `published` and `hidden`; a removed publication refuses any PATCH (#130) [OBSERVED: `update_publication`].
- OQ-5: 404. With the flag off the router is not mounted, so no handler runs and nothing changes [OBSERVED: backend/main.py].
- OQ-8: no. An export with no patches fails `EXPORT_NO_PATCHES` in the Design Engine, and the legacy route returns 404 [OBSERVED: backend/export/patchbook/design/content_spine.py, backend/export/routes.py].
- OQ-13, in part: reports may be anonymous (`reporter_user_id` is nullable and the route takes an optional user), and the report route has no rate limit [OBSERVED: `report_publication`]. Retention is still the owner's to set.

## R7. Questions only the owner can answer

- OQ-6 (R2), OQ-7 (R5), OQ-9 (thresholds), OQ-12 (license), OQ-14 (missing source text) and OQ-15 (threat model) stay open.
- OQ-10: owner and admin writes take no row lock and check no version, so the last commit wins [OBSERVED: backend/publishing/routes.py]. To get "admin wins", add a version column checked on each write, or `SELECT … FOR UPDATE` [INFERRED]. Effort: S once decided.
- OQ-11: as built, the publication profile adds a non-executable plate per patch and keeps each patch's one-page execution page in the appendix (`technical/PatchBook-execution.pdf`) [OBSERVED: engine.py]. The owner must say whether that meets the one-page law.
