# Patch Book Generator

**Status:** canonical publishing specification  
**Scope:** generated patch pages, book assembly, validation, export, and release gates  
**Primary invariant:** one published patch equals exactly one standalone page

The owner chose not to build the staged pipeline below (decision 37, [owner decisions](evidence/OWNER_DECISIONS_2026-11-04.md)). A book is composed in one pass, and a patch that doesn't fit fails the whole export. [Spec 002](../specs/002-patch-book-publishing/spec.md) describes what's built, and it wins over this document where they differ (decision 38).

## 1. Purpose

The Patch Book Generator converts immutable PatchHive artifacts into publication-quality technical manuals for a specific modular rig. It is not a generic PDF formatter. It is a deterministic compiler whose output must remain technically accurate, accessible, reproducible, printable, and independently usable at the rack.

A patch page must answer, without requiring another page:

- what the patch does
- which modules and ports it uses
- how to connect it in order
- which controls need starting positions
- what the performer should listen for
- which controls are intended for performance
- what can fail or become unsafe
- how the page is identified and reproduced

## 2. Binding invariants

1. Every published patch occupies exactly one page.
2. A patch may not continue onto another page.
3. Two patches may not share a page.
4. A patch may not rely on its facing page.
5. A QR code or online companion may extend the page but may not contain required execution information.
6. Required content may not be hidden, clipped, truncated, or replaced by an ellipsis.
7. Typography may not shrink below the active output profile's accessibility floor.
8. Decorative art may not reduce technical legibility.
9. Color may not be the sole signal or cable encoding.
10. Fixed normalized input, schema version, generator version, layout profile, and seed must produce canonical-equivalent output.

When a candidate patch cannot satisfy these constraints, the generator must simplify optional prose, choose another approved layout, decompose the concept into separately executable patches, or reject it from the selected book profile.

## 3. Compiler pipeline

```text
PatchGraph
  + PatchPlan
  + ValidationReport
  + module display metadata
  + book profile
  + theme tokens
    -> build PatchPageSpec
    -> score semantic and visual density
    -> select approved layout class
    -> route and label cables
    -> render canonical SVG assets
    -> run page-fit validation
    -> run accessibility validation
    -> bind page manifest
    -> assemble PatchBookManifest
    -> emit PDF / SVG / JSON / ZIP
```

Compilation must be stage-receipted. A terminal failure preserves all completed receipts and diagnostics.

## 4. Canonical contracts

### PatchPageSpec

```yaml
schema_version: patchhive.patch_page.v1
page_id: opaque-id
patch_id: opaque-id
patch_version: string
source_run_id: opaque-id
source_rig_revision_id: opaque-id
generator_version: string
layout_profile: diagram_first | instruction_first | performance_first
output_profile: us_letter | a4 | a5 | screen
identity:
  patch_number: integer
  title: string
  category: string
  difficulty: beginner | intermediate | advanced | expert | experimental
  estimated_build_time_minutes: integer
intent:
  purpose: string
  expected_result: string
  listening_cue: string
construction:
  required_modules: []
  optional_modules: []
  ordered_connections: []
  starting_settings: []
  diagram_asset_id: opaque-id
operation:
  performance_controls: []
  variations: []
  troubleshooting: []
  warnings: []
indexing:
  techniques: []
  tags: []
  qr_target: string | null
canonical_hash: sha256
```

### PageFitReport

```yaml
schema_version: patchhive.page_fit.v1
page_id: opaque-id
status: pass | warning | fail
selected_layout: string
text_density: number
diagram_density: number
minimum_font_size_pt: number
cable_crossing_score: number
unresolved_label_collisions: integer
overflow_blocks: []
clipped_elements: []
grayscale_check: pass | fail
non_color_encoding_check: pass | fail
required_content_check: pass | fail
remediation: []
```

### PatchBookManifest

```yaml
schema_version: patchhive.patch_book_manifest.v1
book_id: opaque-id
source_run_id: opaque-id
source_rig_revision_id: opaque-id
generator_version: string
output_profile: string
theme_version: string
page_count: integer
patch_page_count: integer
front_matter_pages: integer
back_matter_pages: integer
pages: []
assets: []
canonical_hash: sha256
created_at: timestamp
```

Every manifest page entry must bind page number, patch ID where applicable, page hash, SVG asset hash, and validation status.

## 5. Page information architecture

Each patch page contains these semantic regions:

1. **Identity header** — patch number, title, category, difficulty, build time, version.
2. **Patch diagram** — simplified module panels, labeled ports, numbered cable routes, direction where ambiguous.
3. **Intent** — purpose, expected result, listening cue.
4. **Construction** — ordered connection sequence and essential starting settings.
5. **Operation** — performance controls, bounded variations, troubleshooting, warnings.
6. **Footer identity** — required modules, tags, QR extension, page/patch checksum.

The layout may move regions but may not omit required semantics.

## 6. Approved layout classes

### Diagram-first

Use for beginners, visually dense topologies, and patches where cable interpretation is the dominant task.

```yaml
diagram_area_target: 55%
instruction_area_target: 25%
operation_area_target: 20%
```

### Instruction-first

Use when the route is visually simple but the ordered setup sequence has more steps or mode requirements.

```yaml
diagram_area_target: 38%
instruction_area_target: 42%
operation_area_target: 20%
```

### Performance-first

Use for live patches whose defining value is a set of playable controls and state transitions.

```yaml
diagram_area_target: 42%
instruction_area_target: 23%
operation_area_target: 35%
```

Layout selection must be deterministic and evidence-based. Themes cannot introduce unapproved semantic layouts.

## 7. Default content budgets

Budgets are profile inputs, not permission to truncate required information.

| Block | Default maximum |
|---|---:|
| Purpose | 45 words |
| Expected result | 30 words |
| Listening cue | 25 words |
| Primary ordered connections | 12 |
| Starting settings | 8 |
| Performance controls | 4 |
| Variations | 3 |
| Troubleshooting entries | 3 |
| Warnings | 2 |
| Tags | 8 |

A compiler stage may compress wording while preserving meaning. It may not delete a connection, safety condition, or required mode merely to achieve fit.

## 8. Diagram rules

The technical diagram is SVG-first and prioritizes routing clarity over photorealism.

Required characteristics:

- simplified but identifiable module panels
- explicit source and destination port labels
- numbered cable routes matching the ordered connection list
- arrowheads or direction labels where direction is not self-evident
- distinct encoding for audio, CV, gate, trigger, and clock
- line pattern or route identifier in addition to color
- highlighted performance controls with a text legend
- explicit feedback-cycle marking and startup warning
- controlled route lanes and bounded bends for dense graphs
- deterministic node placement and edge routing

Module photography and decorative renderings are optional secondary assets and may not replace the technical diagram.

## 9. Typography and physical profiles

Minimum default body size:

- print: 9.5 pt
- digital: 14 px equivalent

Identifiers, port names, voltage values, hashes, and route numbers may use a legible monospace face. Body instructions use a highly legible sans-serif face. Numeric settings use tabular numerals.

The initial physical target is US Letter portrait with support for A4. A5 and other compact formats require separate fit profiles and may reject patches that fit larger pages.

Lay-flat or spiral binding is recommended because users operate the book beside physical hardware. Binding preference must not affect standalone page semantics.

## 10. Accessibility

Target WCAG 2.2 AA for digital surfaces and equivalent print legibility.

Every page must:

- remain understandable in grayscale
- avoid color-only encoding
- preserve logical reading order
- include textual equivalents for the graph
- use explicit headings and labels
- expose route numbers consistently between diagram and instructions
- retain sufficient contrast
- avoid background art beneath technical text and cables
- provide tagged PDF structure where the export stack supports it
- include a text-first companion representation in JSON or HTML

Accessibility failure is a compilation failure for production output.

## 11. Validation

### Semantic validation

- patch, module, and port references resolve to the source rig revision
- ordered connections exactly represent the PatchGraph
- required modes and normal-break behavior are explicit
- warnings match the ValidationReport
- unsupported safety claims are absent
- every required content block exists

### Page-fit validation

- exactly one rendered page exists for the patch
- no block overflows its semantic region
- no element is clipped
- minimum font size is preserved
- labels do not collide
- cable routing stays within accepted crossing and ambiguity thresholds
- footer identity and checksum remain visible

### Book validation

- patch count equals patch-page count
- PDF page count equals manifest page count
- every table-of-contents and index reference resolves
- page order is stable
- all assets are present and hash-valid
- deterministic replay reproduces canonical JSON and stable SVG structure

## 12. Deterministic rune surface

```text
RUNE.PATCHHIVE.BUILD_PATCH_PAGE_SPEC(input)
RUNE.PATCHHIVE.SELECT_PAGE_LAYOUT(input)
RUNE.PATCHHIVE.RENDER_PATCH_PAGE_SVG(input)
RUNE.PATCHHIVE.VALIDATE_PAGE_FIT(input)
RUNE.PATCHHIVE.COMPILE_PATCH_PAGE(input)
RUNE.PATCHHIVE.ASSEMBLE_PATCH_BOOK(input)
RUNE.PATCHHIVE.VALIDATE_PATCH_BOOK(input)
```

Each rune declares input/output schemas, version, determinism class, permitted side effects, authority requirement, error taxonomy, and test vectors.

`RUNE.PATCHHIVE.COMPILE_PATCH_PAGE` succeeds only when signal validation, required-content validation, diagram legibility, page-fit validation, and standalone execution all pass.

## 13. Export bundle

A complete export may contain:

```text
PatchBook.pdf
manifest/patch-book.json
manifest/checksums.json
pages/svg/*.svg
pages/json/*.json
diagrams/svg/*.svg
source/patch-library.json
source/rig-revision.json
validation/page-fit/*.json
validation/patch/*.json
LICENSE.txt
README.txt
```

The PDF is a presentation artifact. Canonical JSON and hashes remain the reproducibility authority.

## 14. Book structure

Front matter may include cover, ownership and edition data, rack overview, table of contents, cable legend, module abbreviations, and instructions for reading a page.

The patch body contains exactly one patch per page.

Back matter may include technique index, module index, glossary, dependency map, credits, methodology, and license.

Front and back matter are exempt from the one-patch rule because they are not patch pages. They must never be inserted inside a patch's required content.

## 15. Error taxonomy

- `PATCH_PAGE_REQUIRED_CONTENT_MISSING`
- `PATCH_PAGE_GRAPH_MISMATCH`
- `PATCH_PAGE_LAYOUT_NOT_SUPPORTED`
- `PATCH_PAGE_TEXT_OVERFLOW`
- `PATCH_PAGE_DIAGRAM_OVERFLOW`
- `PATCH_PAGE_FONT_BELOW_MINIMUM`
- `PATCH_PAGE_LABEL_COLLISION`
- `PATCH_PAGE_NON_COLOR_ENCODING_FAILED`
- `PATCH_PAGE_GRAYSCALE_FAILED`
- `PATCH_PAGE_STANDALONE_EXECUTION_FAILED`
- `PATCH_BOOK_PAGE_COUNT_MISMATCH`
- `PATCH_BOOK_REFERENCE_UNRESOLVED`
- `PATCH_BOOK_ASSET_HASH_MISMATCH`

Errors are machine-readable and include remediation. Warnings never silently become passes.

## 16. Testing strategy

### Unit

Content-budget scoring, layout selection, route numbering, reading order, hash construction, error mapping.

### Property

One patch always yields zero or one accepted page; accepted pages always contain required semantics; deterministic inputs produce canonical-equivalent output; page assembly never mutates source artifacts.

### Golden and visual regression

Use representative beginner, dense, feedback, performance, missing-data, long-label, grayscale, and A4/Letter fixtures. Review structural SVG diffs and rendered-image diffs with explicit thresholds.

### Integration

Font embedding, SVG-to-PDF conversion, object storage, worker retry, manifest binding, export compensation, download token flow.

### End-to-end

Generate a verified rig, compile a patch library, preview one-page results, purchase a test-mode export, download it once under retries, validate manifest/page counts, and revisit the immutable run.

## 17. Implementation sequence

1. Define versioned PatchPageSpec, PageFitReport, and PatchBookManifest contracts.
2. Build deterministic semantic content assembly from canonical patch artifacts.
3. Implement route numbering and SVG technical diagrams.
4. Implement the three layout classes and page-fit engine.
5. Add property, golden, accessibility, and visual-regression fixtures.
6. Assemble PDF and export bundle with manifest verification.
7. Integrate asynchronous export orchestration and credit compensation.
8. Add print-profile QA and tagged-PDF support.

No implementation phase may claim completion without the prior phase's gates.

## 18. Definition of done

The generator is production-ready only when a fixed source run can be compiled repeatedly into a manifest-bound Patch Book in which every published patch occupies exactly one complete page, all technical content agrees with canonical artifacts, accessibility and fit gates pass, and retries cannot duplicate charges or create conflicting immutable artifacts.