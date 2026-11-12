# Visual system intelligence — capability matrix

**Baseline SHA:** `2b72d5b10fef1ab70c74d3c40379eb1593cf8293`  
**Head (this campaign):** see PR / CURRENT_STATE after merge  
**Date:** 2026-07-21

**Changed 2026-11-08 ([decision 63](OWNER_DECISIONS_2026-11-04.md#photo-first-product-2026-11-07)):** the rig builder's per-Module photo step is gone. The evidence, confirmation and reconciliation APIs stay, with no screen of their own, and their mock detector never runs in production. Photos come in through spec 009's whole-Rig Reading.

| capability | status | source_files | tests | documentation | blocking_gaps |
|---|---|---|---|---|---|
| secure image upload validation | IMPLEMENTED | `backend/evidence/images.py` | `test_image_evidence.py` | SECURITY, VSI | production AV scanner still adapter-only |
| image re-encode + EXIF strip | IMPLEMENTED | `evidence/images.py` | unit | SECURITY | retention policy product copy |
| local image quality gates | PARTIAL | `assess_local_image_quality` | `test_vision_provider_and_quality.py` | VSI roadmap WS1 | provider blur/glare scores not calibrated |
| photo evidence UI review | REMOVED (decision 63) | — | — | VSI | the whole-Rig Reading screen (spec 009) replaces it |
| provider-neutral vision adapter | IMPLEMENTED | `evidence/vision_provider.py` | unit | VSI, ARCHITECTURE | live model needs ops secret |
| mock/fixture vision providers | IMPLEMENTED | mock + recorded fixture | unit | VSI roadmap | eval dataset NOT_COMPUTABLE |
| module candidate detection | PARTIAL / STUB | mock devices; `canon/runes.detect_modules`; historical Gemini stubs | unit | VSI | real detection + registry retrieval |
| manufacturer/model resolution | PARTIAL | `runes.resolve_modules` gallery match | existing unit/compiler | VSI | confidence calibration missing |
| confirmation workflow | PARTIAL | confirmations API (its rig builder screen left, decision 63) | unit + api | VSI | RigDetail receipt surface |
| immutable inventory revision | IMPLEMENTED | `canon/inventory.py` + Alembic `system_inventory_revisions` | unit + api | DATA_MODEL | list/latest UI on RigDetail |
| system capability graph | IMPLEMENTED (in-process) | `build_system_capability_graph` | unit | DATA_MODEL | port-level registry completeness |
| confirmed-hardware patch generation gate | IMPLEMENTED | `enforce_confirmed_inventory_constraints` + generate path | unit + api | PATCH_ENGINE, VSI | none for P0 |
| cable endpoint inference | STUB | mock returns empty; ConnectionCandidate contract | unit (occlusion rule) | VSI §7 | P1 model + UX |
| patch validation | IMPLEMENTED | `canon/compiler.validate_patch_graph` | unit | PATCH_ENGINE | inventory gate wiring |
| Patch Book one-page compiler | SPEC_ONLY / PARTIAL | export/pdf, patchbook packages | patchbook tests | PATCH_BOOK_GENERATOR | full page-fit 0.3.x |
| deterministic SVG/PDF/JSON/ZIP | PARTIAL | export routes | unit/api | EXPORT docs | manifest completeness |
| provenance retention | PARTIAL | EvidenceRecord, ProviderReceipt, Provenance | unit | CANON | image retention product policy |
| multi-photo reconciliation | PARTIAL | `evidence/reconciliation.py`, GET .../evidence/reconcile (its rig builder screen left, decision 63) | unit+api | VSI WS6 | accuracy metrics still NOT_COMPUTABLE |
| evaluation metrics dataset | NOT_COMPUTABLE | — | — | VSI §12 | licensed dataset required |

## Gap priority (execution)

### P0 remaining after this campaign

1. ~~Wire inventory constraint gate into generate~~ **DONE**
2. ~~Persist `SystemInventoryRevision` via Alembic~~ **DONE**
3. Authenticated upload endpoint with retention/consent flags (policy-backed) — partial (upload exists; full auth product policy residual).
4. ~~End-to-end confirmation API~~ **DONE** (confirmations → inventory revision); RigDetail latest-inventory surface residual.

### P1

Multi-photo, layout, ports/controls, cables, photo-derived Patch Books, calibration.

### P2

Live camera, marketplace, community system matching — do not promote ahead of P0.
