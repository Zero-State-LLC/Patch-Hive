# Changelog

All notable changes to PatchHive are documented here.

This project follows [Semantic Versioning](docs/VERSIONING.md) beginning with the adoption of the formal release policy. From 0.3.0-alpha.3 on, release-please writes new entries from Conventional Commit PR titles; do not add an Unreleased section by hand. Historical entries are reconstructed from repository evidence and are labeled as retroactive classifications rather than invented release tags.

## [0.3.0-alpha.6](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.5...v0.3.0-alpha.6) (2026-10-31)


### Data

* **catalog:** apply the owner's T034 and A-155 decisions ([#172](https://github.com/Zero-State-LLC/Patch-Hive/issues/172)) ([414d96a](https://github.com/Zero-State-LLC/Patch-Hive/commit/414d96a39f45c9fb4e2133365738b1972340d095))
* **catalog:** fill Cockpit (golden) HP from the maker's COCKPIT MK1 page ([#176](https://github.com/Zero-State-LLC/Patch-Hive/issues/176)) ([927a086](https://github.com/Zero-State-LLC/Patch-Hive/commit/927a086a772cc91f0fa9a90ef0d57828a64453d2))
* **catalog:** fill Cockpit power and depth from the maker's COCKPIT MK1 page ([#178](https://github.com/Zero-State-LLC/Patch-Hive/issues/178)) ([5b46781](https://github.com/Zero-State-LLC/Patch-Hive/commit/5b46781b62bd7bc3c3cf4657a1e2abe6cbf11020))
* **catalog:** label Otool's jumper settings from its manual (spec 003 T034) ([#170](https://github.com/Zero-State-LLC/Patch-Hive/issues/170)) ([eabc044](https://github.com/Zero-State-LLC/Patch-Hive/commit/eabc044b0744a418bdb05eb6cf6e38e49788c588))
* **catalog:** re-source 4 more legacy HP values, correct Dixie II to 6 HP (spec 003 T039) ([#174](https://github.com/Zero-State-LLC/Patch-Hive/issues/174)) ([4baf206](https://github.com/Zero-State-LLC/Patch-Hive/commit/4baf206f498cda93794656d3918332c8a1f54ebf))


### Documentation

* record [#166](https://github.com/Zero-State-LLC/Patch-Hive/issues/166), [#167](https://github.com/Zero-State-LLC/Patch-Hive/issues/167), [#159](https://github.com/Zero-State-LLC/Patch-Hive/issues/159), the power_configs migration and the 9dbb5ba redeploy ([#168](https://github.com/Zero-State-LLC/Patch-Hive/issues/168)) ([4943db1](https://github.com/Zero-State-LLC/Patch-Hive/commit/4943db17e4ec9c938a1f1405e616f01353e76dcc))
* record [#168](https://github.com/Zero-State-LLC/Patch-Hive/issues/168), [#170](https://github.com/Zero-State-LLC/Patch-Hive/issues/170) and the Otool power_configs load ([#171](https://github.com/Zero-State-LLC/Patch-Hive/issues/171)) ([5c69e5d](https://github.com/Zero-State-LLC/Patch-Hive/commit/5c69e5d91c8819702c95d5050d78d4039c4b86db))
* record [#171](https://github.com/Zero-State-LLC/Patch-Hive/issues/171), [#172](https://github.com/Zero-State-LLC/Patch-Hive/issues/172) and the owner-decision loads ([#173](https://github.com/Zero-State-LLC/Patch-Hive/issues/173)) ([fb0139a](https://github.com/Zero-State-LLC/Patch-Hive/commit/fb0139a658a309efdfbbb0cbf1a21a8f442371ca))
* record [#173](https://github.com/Zero-State-LLC/Patch-Hive/issues/173), [#174](https://github.com/Zero-State-LLC/Patch-Hive/issues/174) and the HP v5 load ([#175](https://github.com/Zero-State-LLC/Patch-Hive/issues/175)) ([486e72f](https://github.com/Zero-State-LLC/Patch-Hive/commit/486e72f17691ef333c6b8c1fd76f70dc74f6c97c))
* record [#175](https://github.com/Zero-State-LLC/Patch-Hive/issues/175), [#176](https://github.com/Zero-State-LLC/Patch-Hive/issues/176) and the Cockpit (golden) load ([#177](https://github.com/Zero-State-LLC/Patch-Hive/issues/177)) ([81904b6](https://github.com/Zero-State-LLC/Patch-Hive/commit/81904b6b9c4db876a5d4ec4c923a1325c90cbbd0))

## [0.3.0-alpha.5](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.4...v0.3.0-alpha.5) (2026-10-30)


### Added

* **catalog:** jumper-dependent power as power_configs (spec 003 T034) ([#166](https://github.com/Zero-State-LLC/Patch-Hive/issues/166)) ([fd9fc44](https://github.com/Zero-State-LLC/Patch-Hive/commit/fd9fc4402bafd3e9744b86c3791bbd429d7f0353))
* define routing_flex_score and performance_density_index (spec 001 OQ-11 option 2) ([#161](https://github.com/Zero-State-LLC/Patch-Hive/issues/161)) ([873acb9](https://github.com/Zero-State-LLC/Patch-Hive/commit/873acb957d1fb8bdaaa2677e77519b99f1533cd3))


### Fixed

* report real package version in /health and add evidence-expiry CLI ([#162](https://github.com/Zero-State-LLC/Patch-Hive/issues/162)) ([af60a86](https://github.com/Zero-State-LLC/Patch-Hive/commit/af60a86e1b67d787e73f7f174863e44b630f00f3))


### Data

* **catalog:** re-source 26 more legacy HP values from maker pages (spec 003 T039) ([#167](https://github.com/Zero-State-LLC/Patch-Hive/issues/167)) ([4bd5ca6](https://github.com/Zero-State-LLC/Patch-Hive/commit/4bd5ca627c7ef6442e4610828fdbe2eb687a4198))
* **catalog:** triage the unsourced v1 HP values (spec 003 T038/T039) ([#164](https://github.com/Zero-State-LLC/Patch-Hive/issues/164)) ([694a84f](https://github.com/Zero-State-LLC/Patch-Hive/commit/694a84f6ad3c34e04d9ca7684476ab0fc4910618))
* T035 jumper-power receipt (free re-fetch, 42 pages) ([#163](https://github.com/Zero-State-LLC/Patch-Hive/issues/163)) ([c02b177](https://github.com/Zero-State-LLC/Patch-Hive/commit/c02b1777be17e3f46beb21292ddc813c4ccce201))


### Operations

* run prod DB and edge-secret workflows in the production environment (006 T101a) ([#160](https://github.com/Zero-State-LLC/Patch-Hive/issues/160)) ([442bd47](https://github.com/Zero-State-LLC/Patch-Hive/commit/442bd47e8e72203abb1827ba3e9493ab5664e377))


### Documentation

* record [#160](https://github.com/Zero-State-LLC/Patch-Hive/issues/160)-[#164](https://github.com/Zero-State-LLC/Patch-Hive/issues/164), the hp_source migration and the 2026-10-30 API redeploy ([#165](https://github.com/Zero-State-LLC/Patch-Hive/issues/165)) ([2e3c90d](https://github.com/Zero-State-LLC/Patch-Hive/commit/2e3c90dcbc4cf66cdfdfd2b6328b19a815965734))
* record the 2026-10-30 staging and production deploys at 62203c9 ([#158](https://github.com/Zero-State-LLC/Patch-Hive/issues/158)) ([b5d683c](https://github.com/Zero-State-LLC/Patch-Hive/commit/b5d683cacd6e40b73947d5f094c90382feccd453))

## [0.3.0-alpha.4](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.3...v0.3.0-alpha.4) (2026-10-30)


### Added

* 001 canonical compiler on the generation path + RigMetricsPacket (T030, T031) ([#142](https://github.com/Zero-State-LLC/Patch-Hive/issues/142)) ([34f227a](https://github.com/Zero-State-LLC/Patch-Hive/commit/34f227a3ef236f818d93a47b41afc57995b34d9a))
* **catalog:** add the six crawled modules no overlay held (slice A3) ([#121](https://github.com/Zero-State-LLC/Patch-Hive/issues/121)) ([beea608](https://github.com/Zero-State-LLC/Patch-Hive/commit/beea608befb74eda3abe97f44a5d575df8831fbb))
* **catalog:** fill missing categories from maker crawl tags ([#115](https://github.com/Zero-State-LLC/Patch-Hive/issues/115)) ([c879b76](https://github.com/Zero-State-LLC/Patch-Hive/commit/c879b76010ba898fe73da496cbbe43f0de0bf312))
* **catalog:** retire the ten misattributed brands the crawl guard found ([#120](https://github.com/Zero-State-LLC/Patch-Hive/issues/120)) ([03c7da0](https://github.com/Zero-State-LLC/Patch-Hive/commit/03c7da023dccdabd8adf343a6daba131fb1d9ec3))
* **catalog:** reviewed corrections; fix Sovage CHICANE's HP (003 T033) ([#125](https://github.com/Zero-State-LLC/Patch-Hive/issues/125)) ([284d5a5](https://github.com/Zero-State-LLC/Patch-Hive/commit/284d5a507a50c67a5a52beaba522627b958611fe))
* **catalog:** tombstone misattributed rows and re-add what only they held ([#116](https://github.com/Zero-State-LLC/Patch-Hive/issues/116)) ([c59b2db](https://github.com/Zero-State-LLC/Patch-Hive/commit/c59b2db508af9fc587cd2c2facd9d55478aa55cf))
* **commerce:** webhook event processor and one canonical balance (004 T044, T045) ([#145](https://github.com/Zero-State-LLC/Patch-Hive/issues/145)) ([de734eb](https://github.com/Zero-State-LLC/Patch-Hive/commit/de734eb28e2db14285068d709427e33360f59362))
* **crawl:** refuse a homepage another brand holds before crawling (003 T030) ([#119](https://github.com/Zero-State-LLC/Patch-Hive/issues/119)) ([8cd8f8e](https://github.com/Zero-State-LLC/Patch-Hive/commit/8cd8f8e7ad9913def1037cddbf823af6b8bcca45))
* **decision:** idempotency before provider call and a routing target (005 T083, T085) ([#146](https://github.com/Zero-State-LLC/Patch-Hive/issues/146)) ([4d5bfe9](https://github.com/Zero-State-LLC/Patch-Hive/commit/4d5bfe9cc8aae662758404f08b40dc94f23da057))
* **eval:** verify 007 receipts by replay, sign them with Ed25519, gate 006 gates_pass on them ([#144](https://github.com/Zero-State-LLC/Patch-Hive/issues/144)) ([fd42710](https://github.com/Zero-State-LLC/Patch-Hive/commit/fd4271063cc086f44cd7942f536a08ed262e1ffe))
* **frontend:** enforce the CSP and open sign-in ([#113](https://github.com/Zero-State-LLC/Patch-Hive/issues/113)) ([1d2d21e](https://github.com/Zero-State-LLC/Patch-Hive/commit/1d2d21ee6614dfd187b98948436878ced074d400))
* **patchbook:** validate_book stage, warning receipt, and FR-048 publish guard ([#143](https://github.com/Zero-State-LLC/Patch-Hive/issues/143)) ([80a9c1e](https://github.com/Zero-State-LLC/Patch-Hive/commit/80a9c1ee50d7efd742c7402fe0b7b9dbae216c00))
* **racks:** warn when a rack holds a retired module (slice A4) ([#122](https://github.com/Zero-State-LLC/Patch-Hive/issues/122)) ([1e19430](https://github.com/Zero-State-LLC/Patch-Hive/commit/1e1943056c54cda01c9216b6a24d9e9df874671c))


### Fixed

* **api:** make container startup migrations opt-in ([#110](https://github.com/Zero-State-LLC/Patch-Hive/issues/110)) ([a02da37](https://github.com/Zero-State-LLC/Patch-Hive/commit/a02da3799a9879f90efd7a314c6ec31209ee5c2c))
* **book:** unlisted by default, bounded gallery filter, wrapped cover disclaimer, manifest warnings ([#138](https://github.com/Zero-State-LLC/Patch-Hive/issues/138)) ([bc16194](https://github.com/Zero-State-LLC/Patch-Hive/commit/bc1619436f084390c7fa12949905c3aee65232b2))
* **catalog:** maker-cited HP overlays take precedence over unsourced v1 (D3) ([#152](https://github.com/Zero-State-LLC/Patch-Hive/issues/152)) ([63c5f7d](https://github.com/Zero-State-LLC/Patch-Hive/commit/63c5f7d64ef7a6c3e74be94cfb0e7f09a3e92607))
* **catalog:** plan a reverify clear only when the database would apply it ([#154](https://github.com/Zero-State-LLC/Patch-Hive/issues/154)) ([4338fc4](https://github.com/Zero-State-LLC/Patch-Hive/commit/4338fc46b4c2944c4e677657d0789c689d0e6da8))
* **ci:** edge-secrets writes production secrets to the production Worker ([#107](https://github.com/Zero-State-LLC/Patch-Hive/issues/107)) ([69adf16](https://github.com/Zero-State-LLC/Patch-Hive/commit/69adf1677cc2c9fb2d87ea0fc343f969961ea33c))
* close the catalog and decision lifecycle gaps the specs already define ([#135](https://github.com/Zero-State-LLC/Patch-Hive/issues/135)) ([b253c0e](https://github.com/Zero-State-LLC/Patch-Hive/commit/b253c0e3f91da1d8e9fc5a581c8eec4b0acf46c9))
* **commerce:** append-only canonical ledger, live-mode gate, webhook rotation and race ([#139](https://github.com/Zero-State-LLC/Patch-Hive/issues/139)) ([064b2fe](https://github.com/Zero-State-LLC/Patch-Hive/commit/064b2fec94fb09dd482f1461e0dc0e707939e281))
* **commerce:** delete legacy purchase route; referrals get their own flag (004 T043) ([#150](https://github.com/Zero-State-LLC/Patch-Hive/issues/150)) ([0abb283](https://github.com/Zero-State-LLC/Patch-Hive/commit/0abb283f2837417d2c1d9898436488b868361458))
* **decision:** default decision_routing_target to empty until ESCALATE has a consumer ([#151](https://github.com/Zero-State-LLC/Patch-Hive/issues/151)) ([b341a0b](https://github.com/Zero-State-LLC/Patch-Hive/commit/b341a0b1b12f553b91193db9f6158088b400a44e))
* **decision:** evaluation runs the candidate check; the walkthrough accepts staging only ([#140](https://github.com/Zero-State-LLC/Patch-Hive/issues/140)) ([3faaa63](https://github.com/Zero-State-LLC/Patch-Hive/commit/3faaa63b5733b406a1c7a65a8312d70469efd3ed))
* **export:** wrap legacy PDF text; switch off the legacy patch book ([#133](https://github.com/Zero-State-LLC/Patch-Hive/issues/133)) ([95ca9ee](https://github.com/Zero-State-LLC/Patch-Hive/commit/95ca9ee374c1cbcd3df526515329406463438e64))
* **frontend:** skip the refresh call on a signed-out page load (slice A5) ([#123](https://github.com/Zero-State-LLC/Patch-Hive/issues/123)) ([ff73657](https://github.com/Zero-State-LLC/Patch-Hive/commit/ff7365761693a4f2cf3fbedd698315726e42568d))
* HP overlays must cite a maker page; production refuses decision providers ([#132](https://github.com/Zero-State-LLC/Patch-Hive/issues/132)) ([65f4e10](https://github.com/Zero-State-LLC/Patch-Hive/commit/65f4e103b6d73e212cb2d64d81437de71257228f))
* never debit an export nothing will fulfill; guard the demo seeder ([#129](https://github.com/Zero-State-LLC/Patch-Hive/issues/129)) ([76dce4a](https://github.com/Zero-State-LLC/Patch-Hive/commit/76dce4a05dc358b5e51456a24a69355388b37d33))
* **power:** count unknown module draws per rail instead of as 0 mA ([#118](https://github.com/Zero-State-LLC/Patch-Hive/issues/118)) ([31ded5b](https://github.com/Zero-State-LLC/Patch-Hive/commit/31ded5bc415fb6d7bdc44bb748d71497bd8b0062))
* **registry:** read a manufacturer's models from the module catalog ([#114](https://github.com/Zero-State-LLC/Patch-Hive/issues/114)) ([3c95f64](https://github.com/Zero-State-LLC/Patch-Hive/commit/3c95f64b764308030a85efb4d4c609f52749f8f6))
* **rig:** honor allow_feedback and prefer_simple, hash the full IR, show blocking findings ([#137](https://github.com/Zero-State-LLC/Patch-Hive/issues/137)) ([14c647f](https://github.com/Zero-State-LLC/Patch-Hive/commit/14c647f7a1da6e95eb72e3978d9841ef003265ba))
* **runs:** every run ends terminal, rerun is gated, referral rewards are spendable ([#131](https://github.com/Zero-State-LLC/Patch-Hive/issues/131)) ([b091ab5](https://github.com/Zero-State-LLC/Patch-Hive/commit/b091ab51f7ea19ff184686c857c2cb46ba9558e3))
* **security:** limit sign-up, send HSTS, own confirmations, close removed publications ([#130](https://github.com/Zero-State-LLC/Patch-Hive/issues/130)) ([750c63d](https://github.com/Zero-State-LLC/Patch-Hive/commit/750c63d80c3a1e05999dfa120ba85a6cf35dd973))


### Specifications

* **003:** decide Frap (D7) and jumper power (D8); close answerable questions ([#128](https://github.com/Zero-State-LLC/Patch-Hive/issues/128)) ([f0c4dc9](https://github.com/Zero-State-LLC/Patch-Hive/commit/f0c4dc942e983c81bed7efee5d6cc004ed24b3f2))
* **003:** record D3-D6, a row lifecycle and FR-036-038; delete the seed scripts ([#124](https://github.com/Zero-State-LLC/Patch-Hive/issues/124)) ([db61faa](https://github.com/Zero-State-LLC/Patch-Hive/commit/db61faaf292dc7dd8ae5c8255b34414be53eb2df))
* research open decisions and reconcile specs 001–008 with the code ([#134](https://github.com/Zero-State-LLC/Patch-Hive/issues/134)) ([3725590](https://github.com/Zero-State-LLC/Patch-Hive/commit/3725590e5bc15c6a7869a451ba95b6ce4fb241db))
* tick 003 T036/T037 and 005 T081/T082 (shipped in [#135](https://github.com/Zero-State-LLC/Patch-Hive/issues/135)) ([#141](https://github.com/Zero-State-LLC/Patch-Hive/issues/141)) ([2c1ab42](https://github.com/Zero-State-LLC/Patch-Hive/commit/2c1ab42a051bbba6231b9824ab5d7ea878857c72))


### Data

* **catalog:** correct the HP values the v1 overlay filled before [#152](https://github.com/Zero-State-LLC/Patch-Hive/issues/152) (D4) ([#153](https://github.com/Zero-State-LLC/Patch-Hive/issues/153)) ([ba6f73c](https://github.com/Zero-State-LLC/Patch-Hive/commit/ba6f73c784d4a7e08772832756ae1b9c000956b6))


### Operations

* remove foreign pin-pr workflow, drop actions:write, revoke orphan R2 token ([#136](https://github.com/Zero-State-LLC/Patch-Hive/issues/136)) ([d636637](https://github.com/Zero-State-LLC/Patch-Hive/commit/d63663730ef7accb942bfc082e071570581878ba))


### Documentation

* **003:** mark T033 done after the staging and prod loads ([#127](https://github.com/Zero-State-LLC/Patch-Hive/issues/127)) ([23dd1b1](https://github.com/Zero-State-LLC/Patch-Hive/commit/23dd1b18747445744a68e2e67d6a2d6d169c8063))
* **003:** mark the prod catalog load (T027) done ([#112](https://github.com/Zero-State-LLC/Patch-Hive/issues/112)) ([2c98ada](https://github.com/Zero-State-LLC/Patch-Hive/commit/2c98ada3f09d89ff9ed3fa79d9b2757072f49c8a))
* **007:** describe the strict key revocation rule the verifier enforces ([#149](https://github.com/Zero-State-LLC/Patch-Hive/issues/149)) ([8e8f0b1](https://github.com/Zero-State-LLC/Patch-Hive/commit/8e8f0b1b3a6b2a3fe27259c831af324de9f775a2))
* A-101-3 stays flagged for +5V only, not power and depth ([#156](https://github.com/Zero-State-LLC/Patch-Hive/issues/156)) ([9b94d1e](https://github.com/Zero-State-LLC/Patch-Hive/commit/9b94d1e078e06cd413bb46e2bb9f6c027dcb1d01))
* follow-up research for the open decisions; record the staging deploy ([#157](https://github.com/Zero-State-LLC/Patch-Hive/issues/157)) ([eb212e8](https://github.com/Zero-State-LLC/Patch-Hive/commit/eb212e80a77c6219fa8846b8dbb1807c596606d8))
* refresh CURRENT_STATE for [#134](https://github.com/Zero-State-LLC/Patch-Hive/issues/134)-[#146](https://github.com/Zero-State-LLC/Patch-Hive/issues/146) and the 2026-10-30 migrations ([#147](https://github.com/Zero-State-LLC/Patch-Hive/issues/147)) ([9198aa2](https://github.com/Zero-State-LLC/Patch-Hive/commit/9198aa22cbbc5f52cb5e509a0242b69a3b5bbb7b))
* refresh CURRENT_STATE for [#147](https://github.com/Zero-State-LLC/Patch-Hive/issues/147)-[#154](https://github.com/Zero-State-LLC/Patch-Hive/issues/154) and the 2026-10-30 HP loads ([#155](https://github.com/Zero-State-LLC/Patch-Hive/issues/155)) ([555fa20](https://github.com/Zero-State-LLC/Patch-Hive/commit/555fa205b737ac25a77ff7532ce6411797df399b))
* refresh state, board mirror and decisions after [#116](https://github.com/Zero-State-LLC/Patch-Hive/issues/116); plan next slices ([#117](https://github.com/Zero-State-LLC/Patch-Hive/issues/117)) ([788e397](https://github.com/Zero-State-LLC/Patch-Hive/commit/788e397f8090f2d152b88f4b68adcf50fa2a326c))
* refresh state, slices, decisions and the board mirror for 2026-10-29 ([#126](https://github.com/Zero-State-LLC/Patch-Hive/issues/126)) ([66e34a3](https://github.com/Zero-State-LLC/Patch-Hive/commit/66e34a350234d9a08d2ba236ec662d1f2943d7d6))
* research brief for the open owner decisions (2026-10-30) ([#148](https://github.com/Zero-State-LLC/Patch-Hive/issues/148)) ([c1ad03a](https://github.com/Zero-State-LLC/Patch-Hive/commit/c1ad03a9f4c1c0037854457cd93fcf66e69f8c41))

## [0.3.0-alpha.3](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.2...v0.3.0-alpha.3) (2026-10-28)


### Added

* **001:** resolve generic jacks to declared ones, and fail runs on contradictions ([#97](https://github.com/Zero-State-LLC/Patch-Hive/issues/97)) ([4a303d5](https://github.com/Zero-State-LLC/Patch-Hive/commit/4a303d5e120d4af233a89125df7d60ea1741b32b))
* 003 T020–T022 source scope + Firecrawl proxy tier ([#65](https://github.com/Zero-State-LLC/Patch-Hive/issues/65)) ([a0a5d5d](https://github.com/Zero-State-LLC/Patch-Hive/commit/a0a5d5d4857df92a70252fdd0fe0e288f0fcca9e))
* 003 T023 manufacturer crawl v2 (shared router, curated homepages, adapters, dry run) ([#66](https://github.com/Zero-State-LLC/Patch-Hive/issues/66)) ([af00449](https://github.com/Zero-State-LLC/Patch-Hive/commit/af00449f4de5cdc95eb1a3527658a8f3a146168c))
* 003 T025 loader overlays from the v2 maker crawl (+2,721 catalog rows) ([#67](https://github.com/Zero-State-LLC/Patch-Hive/issues/67)) ([0ad98a6](https://github.com/Zero-State-LLC/Patch-Hive/commit/0ad98a67e1df23bc5d58f86bf899e2b609d3dae7))
* 003 T026 free adapter fixes for 4ms, Pittsburgh, Erica; Tiptop excluded ([#72](https://github.com/Zero-State-LLC/Patch-Hive/issues/72)) ([270140c](https://github.com/Zero-State-LLC/Patch-Hive/commit/270140c5d33a3803605c8e9d9f9907346cb995db))
* 003 T026 overlays: catalog-additions-v4 and module-power-depth-v12 ([#74](https://github.com/Zero-State-LLC/Patch-Hive/issues/74)) ([7db1f75](https://github.com/Zero-State-LLC/Patch-Hive/commit/7db1f75a645139318e11ed7bdd2cb3fef846763f))
* 003 T026 paid pass: 4ms, Pittsburgh and Erica merged into the v2 crawl ([#73](https://github.com/Zero-State-LLC/Patch-Hive/issues/73)) ([35b679c](https://github.com/Zero-State-LLC/Patch-Hive/commit/35b679cef469af3491d48cabbf1a0c9802757496))
* 006 implement Cloudflare Edge + Clef (state machines + ClefProvider adapter) ([#50](https://github.com/Zero-State-LLC/Patch-Hive/issues/50)) ([f64c9dc](https://github.com/Zero-State-LLC/Patch-Hive/commit/f64c9dc175b0e415d55806883448edf1c8e01b6f))
* 007 implement Evaluation Corpus Freeze + Controlled Staging Enablement ([#51](https://github.com/Zero-State-LLC/Patch-Hive/issues/51)) ([0b7b911](https://github.com/Zero-State-LLC/Patch-Hive/commit/0b7b911abccd2b51bd4cecdb3ef326fbcd41d94b))
* 008 implement Dual-Path F5 Cutover + Design Engine Staging Receipts ([#53](https://github.com/Zero-State-LLC/Patch-Hive/issues/53)) ([e0fb6a1](https://github.com/Zero-State-LLC/Patch-Hive/commit/e0fb6a1ddbcd4d2a86531eb4e6c695f3bfeba0e8))
* **api:** users own their racks ([#80](https://github.com/Zero-State-LLC/Patch-Hive/issues/80)) ([433bb76](https://github.com/Zero-State-LLC/Patch-Hive/commit/433bb76ec0c03bd6c7133ada82b550996fab9afd))
* **auth:** short in-memory access tokens, rotating refresh cookie, report-only CSP ([#99](https://github.com/Zero-State-LLC/Patch-Hive/issues/99)) ([789ec15](https://github.com/Zero-State-LLC/Patch-Hive/commit/789ec1507e4dd97c6efee52942e2fec2375e69b8))
* **engine:** six more patch rules, and a demo rig that shows real patches ([#96](https://github.com/Zero-State-LLC/Patch-Hive/issues/96)) ([1c4735d](https://github.com/Zero-State-LLC/Patch-Hive/commit/1c4735dbf89f9b7c44f7a64f6275807f2838f349))
* **storage:** mirror evidence, exports and design packs to R2 (006 T055a) ([#63](https://github.com/Zero-State-LLC/Patch-Hive/issues/63)) ([0741437](https://github.com/Zero-State-LLC/Patch-Hive/commit/07414374e2b3de8b99dda436f99c5eb3a60821a6))


### Fixed

* **001:** five canonical categories, and no invented study patches ([#94](https://github.com/Zero-State-LLC/Patch-Hive/issues/94)) ([9dd88cf](https://github.com/Zero-State-LLC/Patch-Hive/commit/9dd88cfaff6ee9df23c055c40f2793809274656e))
* **001:** gate readiness before writing, record the run lifecycle and real provenance ([#88](https://github.com/Zero-State-LLC/Patch-Hive/issues/88)) ([b7cd497](https://github.com/Zero-State-LLC/Patch-Hive/commit/b7cd497b1fe0da6b5353172c963f748074f62537))
* **001:** keep runs and generated patches append-only ([#92](https://github.com/Zero-State-LLC/Patch-Hive/issues/92)) ([33dbecb](https://github.com/Zero-State-LLC/Patch-Hive/commit/33dbecbec54a1c72d4c035fb69b713865f754d0d))
* **001:** soft-delete racks so deletion keeps run and patch history ([#93](https://github.com/Zero-State-LLC/Patch-Hive/issues/93)) ([08ae313](https://github.com/Zero-State-LLC/Patch-Hive/commit/08ae3130a0c931ce95a600828a70b32ec2a64890))
* **002:** draw body text, steps and cables at the profile's font floor ([#102](https://github.com/Zero-State-LLC/Patch-Hive/issues/102)) ([82435ed](https://github.com/Zero-State-LLC/Patch-Hive/commit/82435ed3335a6cf383ca330dcf92fdb86492c987))
* **002:** patch pages wrap instead of cutting, overflow fails with a code; guard publication lifecycle ([#101](https://github.com/Zero-State-LLC/Patch-Hive/issues/101)) ([5bd303b](https://github.com/Zero-State-LLC/Patch-Hive/commit/5bd303b18711034f0a8920231e2fb545ccbbf81f))
* 003 keep parsed draws the model left empty; fill feed rows from pages ([#76](https://github.com/Zero-State-LLC/Patch-Hive/issues/76)) ([d12791e](https://github.com/Zero-State-LLC/Patch-Hive/commit/d12791e482223b2c145bedef32bae7f75ad7d621))
* 003 loader false conflicts from integer columns and unverified sources ([#70](https://github.com/Zero-State-LLC/Patch-Hive/issues/70)) ([77080d6](https://github.com/Zero-State-LLC/Patch-Hive/commit/77080d6cd1b9de88a925585e8db9ad6b1b08cf8c))
* 003 rail parser misread -12V draws; correct the v2 overlays and staging ([#68](https://github.com/Zero-State-LLC/Patch-Hive/issues/68)) ([09d5645](https://github.com/Zero-State-LLC/Patch-Hive/commit/09d56456e61cbfcdb6246e3d97b7c7852e723474))
* 003 read Erica's unlabelled signed draws (+59mA, -30mA) ([#75](https://github.com/Zero-State-LLC/Patch-Hive/issues/75)) ([b235b97](https://github.com/Zero-State-LLC/Patch-Hive/commit/b235b979e540c50da75f5439162aaf221d43c184))
* 003 resolve the five staging conflicts by product identity ([#71](https://github.com/Zero-State-LLC/Patch-Hive/issues/71)) ([0fe76e7](https://github.com/Zero-State-LLC/Patch-Hive/commit/0fe76e78eddf1673a8cff6ae6b5f5be97f357e1a))
* **003:** bounded downloads, identified receipts, and apply bound to the reviewed plan ([#103](https://github.com/Zero-State-LLC/Patch-Hive/issues/103)) ([7e730e9](https://github.com/Zero-State-LLC/Patch-Hive/commit/7e730e98283977dd9ba885e608f20b32dee554dd))
* **api:** close the P0 security gaps from the 2026-10-27 gap analysis ([#82](https://github.com/Zero-State-LLC/Patch-Hive/issues/82)) ([9cd11aa](https://github.com/Zero-State-LLC/Patch-Hive/commit/9cd11aa852cd9418e600bf88ed8992e9e3b07076))
* **api:** require an admin for module and case writes, and audit them ([#79](https://github.com/Zero-State-LLC/Patch-Hive/issues/79)) ([f5c7ff6](https://github.com/Zero-State-LLC/Patch-Hive/commit/f5c7ff6691368a6316e48d8f1d8d7fe14f42c9ca))
* **cases:** reload fills nulls only, never overwrites; count real changes ([#35](https://github.com/Zero-State-LLC/Patch-Hive/issues/35)) ([6b65156](https://github.com/Zero-State-LLC/Patch-Hive/commit/6b65156344d25f9dc9ffe07155f5dff4c7c46014))
* **edge:** forward the https scheme to the API and restart on config changes ([#86](https://github.com/Zero-State-LLC/Patch-Hive/issues/86)) ([677a204](https://github.com/Zero-State-LLC/Patch-Hive/commit/677a20432632fa651626367618abdb862e1566a0))
* **edge:** keep the container label name under Cloudflare's 16-byte limit ([#87](https://github.com/Zero-State-LLC/Patch-Hive/issues/87)) ([25ce33f](https://github.com/Zero-State-LLC/Patch-Hive/commit/25ce33f7d487d0b4a7f980e1e88f953ccbc92d58))
* **frontend:** allow Cloudflare's analytics beacon in the report-only CSP ([#100](https://github.com/Zero-State-LLC/Patch-Hive/issues/100)) ([fd444e0](https://github.com/Zero-State-LLC/Patch-Hive/commit/fd444e09cb7117b441236a6302e77df1fca20e84))
* **frontend:** drop seed-v1 operator hint from production Cases error ([7a7791f](https://github.com/Zero-State-LLC/Patch-Hive/commit/7a7791f1806182973540e8892e31179c285c4ef4))
* **frontend:** keep demo credentials and seed hints out of production ([79d985b](https://github.com/Zero-State-LLC/Patch-Hive/commit/79d985be2002454aa0ca529e5ed7e583c232640e))
* **frontend:** remove phishing-scanner triggers from patch-hive.com ([#69](https://github.com/Zero-State-LLC/Patch-Hive/issues/69)) ([fbabe1b](https://github.com/Zero-State-LLC/Patch-Hive/commit/fbabe1bb2ac5e7c15472131f840d87249c14d52f))
* **github:** drop case-colliding PULL_REQUEST_TEMPLATE.md ([#59](https://github.com/Zero-State-LLC/Patch-Hive/issues/59)) ([bba9180](https://github.com/Zero-State-LLC/Patch-Hive/commit/bba9180e7485e5f2e179d3ae91c506cb9571c930))
* **intelligence:** a failed provider resolves UNRESOLVED or ESCALATE, never REJECT ([#105](https://github.com/Zero-State-LLC/Patch-Hive/issues/105)) ([278878e](https://github.com/Zero-State-LLC/Patch-Hive/commit/278878e562ff32630fb2e3f1728cf44c5abadb4e))
* **intelligence:** bound choice answers to the request's candidates (spec 005 FR-003) ([#104](https://github.com/Zero-State-LLC/Patch-Hive/issues/104)) ([16e5499](https://github.com/Zero-State-LLC/Patch-Hive/commit/16e5499626fb7c20b45998775d357b805e155b0c))
* **population:** flag, don't verify, when verified overlay disagrees with stored values ([#38](https://github.com/Zero-State-LLC/Patch-Hive/issues/38)) ([1b2bc6e](https://github.com/Zero-State-LLC/Patch-Hive/commit/1b2bc6e07c2b90b9fc2d38aea7465323d43ee751))
* **population:** flagged rows stay flagged without a spurious conflict ([#39](https://github.com/Zero-State-LLC/Patch-Hive/issues/39)) ([8b0bc33](https://github.com/Zero-State-LLC/Patch-Hive/commit/8b0bc33f126771cd9504408ba0fddb62b1718b4d))
* **security:** P1 hardening from the gap analysis ([#98](https://github.com/Zero-State-LLC/Patch-Hive/issues/98)) ([43241be](https://github.com/Zero-State-LLC/Patch-Hive/commit/43241bec1ddca71aca142155807e656e12795ac5))


### Specifications

* **003:** record owner decisions on ModularGrid leads and source scope ([#64](https://github.com/Zero-State-LLC/Patch-Hive/issues/64)) ([0125c0a](https://github.com/Zero-State-LLC/Patch-Hive/commit/0125c0a96f49730793f2df72eb46bd042b370b9c))
* add 006 Cloudflare Edge + Clef (DAG + state machines) ([#48](https://github.com/Zero-State-LLC/Patch-Hive/issues/48)) ([0b4ca02](https://github.com/Zero-State-LLC/Patch-Hive/commit/0b4ca02e6f13ab8e395ddca30d0db62c725e9c0c))
* add 007 evaluation/staging enablement + 008 dual-path F5 cutover (tasks + state machines) ([#49](https://github.com/Zero-State-LLC/Patch-Hive/issues/49)) ([3f6d19c](https://github.com/Zero-State-LLC/Patch-Hive/commit/3f6d19c5358fc0cde1c9937c8a0ef65c5a2f492c))
* add missing depends_on edges and a --ready view to the spec DAG checker ([#61](https://github.com/Zero-State-LLC/Patch-Hive/issues/61)) ([a66baf0](https://github.com/Zero-State-LLC/Patch-Hive/commit/a66baf0df31621c59bf0b76fc27e3062866ef4e1))
* audit 001-008 for Spec Kit + DAG compliance; add spec DAG checker ([#57](https://github.com/Zero-State-LLC/Patch-Hive/issues/57)) ([230c0a5](https://github.com/Zero-State-LLC/Patch-Hive/commit/230c0a5d03a89588c846f46a5957024a0e2be825))


### Data

* batch 8 paid run, power/depth overlay v7, fake-IP opt-in for sandbox egress ([#34](https://github.com/Zero-State-LLC/Patch-Hive/issues/34)) ([6d13ceb](https://github.com/Zero-State-LLC/Patch-Hive/commit/6d13ceb7b1971786b65d3faa3cc90b005b6e100f))
* catalog batch 7 via shared scrape-router (overlay v5, 179 new-brand candidates, dry-run receipt, architecture audit) ([#30](https://github.com/Zero-State-LLC/Patch-Hive/issues/30)) ([fdfbe93](https://github.com/Zero-State-LLC/Patch-Hive/commit/fdfbe93c6a446b82bcd9b311c8e409f683922fbf))
* in-repo scrape router + importer + batch 8 prep ([#33](https://github.com/Zero-State-LLC/Patch-Hive/issues/33)) ([6a2035b](https://github.com/Zero-State-LLC/Patch-Hive/commit/6a2035b2f96891e7a079f7ce5c5cd0ec065a70fc))
* maker re-verify v1 of ModularGrid-derived values (power/depth v10, catalog hp v2; maker pages only, fill-null) ([#42](https://github.com/Zero-State-LLC/Patch-Hive/issues/42)) ([2376481](https://github.com/Zero-State-LLC/Patch-Hive/commit/2376481bdd00380f8efbcbb5d3cd43f1d56f48cc))
* manufacturer-crawl catalog additions v2 + power/depth v9 (maker pages only) ([#40](https://github.com/Zero-State-LLC/Patch-Hive/issues/40)) ([3a8310c](https://github.com/Zero-State-LLC/Patch-Hive/commit/3a8310c7468dcb7800dc98b01fab4b9afa82a73b))
* manufacturer-verified catalog additions v1 + power/depth v8 for unmatched rows ([#37](https://github.com/Zero-State-LLC/Patch-Hive/issues/37)) ([9e22422](https://github.com/Zero-State-LLC/Patch-Hive/commit/9e2242244b8cfd854bad94bc61f5a6298c7f7257))
* ModularGrid provenance archive, null unconfirmed MG values, remove MG extracts from HEAD ([#41](https://github.com/Zero-State-LLC/Patch-Hive/issues/41)) ([c7b4777](https://github.com/Zero-State-LLC/Patch-Hive/commit/c7b4777cee5ba2ada778ab6135e6334464fa50fe))
* verified power/depth overlay v7, loader reads v1-v7 ([#36](https://github.com/Zero-State-LLC/Patch-Hive/issues/36)) ([3f1ab6e](https://github.com/Zero-State-LLC/Patch-Hive/commit/3f1ab6eb442a3b40c870e737d831d5d6dbc832a1))


### Operations

* add a workflow that writes edge API secrets without exposing them ([#85](https://github.com/Zero-State-LLC/Patch-Hive/issues/85)) ([d30711e](https://github.com/Zero-State-LLC/Patch-Hive/commit/d30711e4d28329f4cc30c0ddec802f9bb4894dd1))
* **api:** serve FastAPI on Cloudflare Containers at api.patch-hive.com (006 T040a, T050a) ([#62](https://github.com/Zero-State-LLC/Patch-Hive/issues/62)) ([46c23c6](https://github.com/Zero-State-LLC/Patch-Hive/commit/46c23c67808a00d69a81a1f80db04e23e382a154))
* **db-load:** stop uploading raw pre-apply dumps and row-level SQL as public artifacts ([#43](https://github.com/Zero-State-LLC/Patch-Hive/issues/43)) ([84a1b32](https://github.com/Zero-State-LLC/Patch-Hive/commit/84a1b3254d58a4f5eff19c9cf3a6b7a5718f9ecd))
* **edge:** run the API container under the durable_object scheduling policy ([#84](https://github.com/Zero-State-LLC/Patch-Hive/issues/84)) ([34b0a58](https://github.com/Zero-State-LLC/Patch-Hive/commit/34b0a589b209c62290bf3fb92754a7ad4d7d3920))
* **frontend:** deploy SPA to Cloudflare Workers static assets ([9a2e499](https://github.com/Zero-State-LLC/Patch-Hive/commit/9a2e499d20ab617889417ac9de6a20950e67b07c))
* **frontend:** redirect www.patch-hive.com to the apex ([f190a43](https://github.com/Zero-State-LLC/Patch-Hive/commit/f190a43b1a771169f6a3dbed87ec8b77f93ecb10))
* **frontend:** serve from patch-hive.com, disable shared workers.dev ([b511285](https://github.com/Zero-State-LLC/Patch-Hive/commit/b51128593d8f3064ab3dd50d2712fb58e9dbce5b))
* make the public pair production and add a separate staging pair ([#83](https://github.com/Zero-State-LLC/Patch-Hive/issues/83)) ([cc1b21a](https://github.com/Zero-State-LLC/Patch-Hive/commit/cc1b21a4a4e9e4e27fedcc7e4195a770546234ef))
* record Neon patchhive DB (staging/prod, quota) and add manual db-migrate workflow ([#32](https://github.com/Zero-State-LLC/Patch-Hive/issues/32)) ([6e557eb](https://github.com/Zero-State-LLC/Patch-Hive/commit/6e557ebd374f507342ae4a558ac92639089f3ff8))
* release-please + Conventional Commit PR titles; board Status Backlog ([#58](https://github.com/Zero-State-LLC/Patch-Hive/issues/58)) ([c4f83ba](https://github.com/Zero-State-LLC/Patch-Hive/commit/c4f83ba314ad874c29a3b6deae82d9d9078e7e56))
* **release:** pass RELEASE_PLEASE_TOKEN to release-please ([#60](https://github.com/Zero-State-LLC/Patch-Hive/issues/60)) ([a2014f5](https://github.com/Zero-State-LLC/Patch-Hive/commit/a2014f50c34c62659e29a0319ac023cfd5296799))


### Documentation

* refresh state, board mirror and open decisions after [#80](https://github.com/Zero-State-LLC/Patch-Hive/issues/80) ([#81](https://github.com/Zero-State-LLC/Patch-Hive/issues/81)) ([bbc68ad](https://github.com/Zero-State-LLC/Patch-Hive/commit/bbc68ad2054d523e069f109849e84393c60f42d4))
* **spec-006:** record T030 frontend edge deploy receipt ([f66077e](https://github.com/Zero-State-LLC/Patch-Hive/commit/f66077e38158eacd8978d9d12f2bb63f1756771d))

## 0.3.0-alpha.2 — 2026-10-16

### Changed

- Synced the personal repository main (964ce18) into the org repository: `.specify/memory/constitution.md`, `specs/005-decision-intelligence`, and the T050, T061, and T070 work.
- Aligned `backend/pyproject.toml` (`0.3.0a2`) and `frontend/package.json` (`0.3.0-alpha.2`) with the tag scheme. Both were `0.1.0`.

### Added

- `scripts/check_version_consistency.py` and `.github/workflows/release.yml`. The workflow checks versions on PRs, verifies tag/version match on tag push, and creates the GitHub release.

### Added (before the release policy; not split by tag)

- Cases C1–C3: `format_family` / `capacity_unit` / `powered` columns + migration; list filters on columns; power validation (POWER_UNSPECIFIED advisory, hard fail when rails known or unpowered+draw); non-Eurorack placement blocked; staging bootstrap doc; rack `validation_warnings` on create/update.
- Cases C0 product loop: list filters (`format_family`, `powered`, `q`, `min_hp`); Cases page filters + “Use on new rig”; RackBuilder Step 0 Eurorack case picker + create empty rig; rack validation errors JSON-serializable.
- Case catalog research ingest: 50 cases from `fixtures/Cases4PatchHive.md` → `fixtures/cases_research_2026.json` (Case schema); `scripts/parse_cases_research.py` + `scripts/import_cases_research.py`; fail-closed null rails; non-Eurorack `meta.capacity_unit`.
- Production readiness assessment (2026-07-21): gate scorecard, blockers, continuity plan under `docs/evidence/PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md`; refreshed SHA-pinned readiness matrix.
- README hero banner, product stills, Zero State lockup, and linked CI / readiness badges.
- Roadmap updated for late-alpha Design Engine + VSI delivery and beta/RC path.
- Zero State × PatchHive design system: brand hierarchy, guidelines, 340 SVG icons, CSS tokens, footer credit, design-system preview, lockups, app icon, Zero State monogram.
- Cyber Hive visual identity kit: brand assets under `brand/`, design system in `docs/brand/`, SVG icons + tokens.
- Local Docker staging receipt + domain cutover checklist; `just staging-up` / `staging-down`.
- F3 generate dual-write audit: native `rig-rev-*`/`gen-run-*` only, inventory row persistence, empty-rack NOT_COMPUTABLE still dual-writes; forbid legacy-* bridge ids on ready bridges.
- RigDetail inventory → generate → patches loop: step list, readiness-aware generate CTA, generation receipt, Playwright coverage.
- Staging host plan + `docker-compose.staging.yml`; dual-path retirement design F0 (`DUAL_PATH_RETIREMENT_DESIGN.md`).
- Release notes draft for `v0.3.0-alpha.1` (alpha hardening; not production).
- Canon-native replacements for residual legacy unit suites: `function_registry`, `query_surface`, `pipeline`, `export_pack` (no default-test imports of historical `patchhive`).
- `canon.gallery_revisions` append-only file store; `patchhive.gallery.revisions` is a compatibility shim; gallery revision tests no longer mark `legacy_pipeline`.
- Migrated schema roundtrip off historical `patchhive` onto `canon.contracts.RigMetricsPacket` (one fewer `legacy_pipeline` importer).
- Canon compiler edge-case tests: signal mismatch, direction, feedback declare/undeclared, attenuation, normals, empty graph.
- `patchhive` import telemetry quarantine: markers, package-test norecursedirs, CI import guard, `just telemetry-patchhive` / `test-historical`.
- Module gallery search, brand/type filters, sort, and place-on-rig entry links; Racks list loading/empty/retry parity.
- `GET /api/racks/{id}/evidence/inventory` latest sealed inventory receipt; RigDetail overview surfaces it.
- Fusion panel applied-status feedback; Playwright covers multi-photo fusion confirm + RigDetail receipt.
- Continuation plan post-#75 (`docs/evidence/CONTINUATION_PLAN_POST_75.md`).
- Fusion panel confirm/reject/defer actions and batch “confirm all non-conflict fused” (user-initiated only; conflicts blocked).
- Staging Compose drill receipt (`docs/evidence/STAGING_COMPOSE_RECEIPT.md`): local db+backend healthy at Alembic head `20240930_patch_user_overlays`.
- RackBuilder multi-photo upload and fusion review panel (reconcile API; never auto-confirms).
- Rig revision picker API/UI and mutable patch overlays (notes/favorite/tried) without mutating canonical patches.
- AI-native engineering foundation: `justfile`, `scripts/ai/rebuild_indexes.sh`, `docs/engineering/*`, `AI_CONTEXT.md`, `SYSTEM_CONTEXT.md`, engineering-quality CI, MCP template (see `ENGINEERING_SETUP_REPORT.md`).
- Cases and Patches list pages with loading / empty / error / retry parity.
- `evidenceApi` client; RackBuilder live upload → candidates → confirmation when a rack is selected.
- Vision evaluation harness + synthetic `fixtures/vision_eval` dataset (production accuracy remains `NOT_COMPUTABLE`).
- Consent-gated `CloudVisionProvider` and `select_vision_provider` (live calls fail-closed; CI uses mock).
- Canonical one-page Patch Book publishing invariant.
- Comprehensive Patch Book Generator specification.
- Versioning and release-candidate policy.
- Evidence-based production-readiness framework.
- Versioned product roadmap.
- Visual System Intelligence P0 contracts: provider-neutral `VisionEvidenceProvider`, `SystemInventoryRevision`, `SystemCapabilityGraph`, confirmed-inventory patch constraint gate.
- Local image quality assessment after secure re-encode.
- Audit receipts under `docs/evidence/` (baseline, audio-drift classification, capability matrix, readiness matrix, work packages).

### Changed

- Root README rebuilt as the canonical repository entrypoint.
- Canon and operations documentation aligned to page-fit, deterministic export, and manifest requirements.
- `docs/PATCH_ENGINE.md`: audio simulation and hardware CV/MIDI activation marked **OUT OF SCOPE** (symbolic waveform SVGs retained as non-audio visualization).
- Visual System Intelligence documents preserved and cross-linked to implementation paths.

### Tests

- Unit coverage for vision provider determinism, candidate self-confirm rejection, inventory immutability, and `NOT_COMPUTABLE` generation without confirmed modules.
- Inventory gate tests for rack-backed generation and generate-bridge API fields.
- Inventory persistence, multi-image evidence upload, retention expiry, native bridge IDs.
- Ranked candidate list + confirmation batch API; multi-candidate RackBuilder review UX.
- Acceptance (testcontainers): 11 passed on campaign branch.

### Database

- Alembic `20240929_visual_inventory_evidence`: `system_inventory_revisions`, `image_assets`, `classification_evidence_records`.

## 0.3.0 — Planned line

One-page Patch Book Generator implementation.

Planned scope includes versioned page contracts, deterministic semantic assembly, SVG-first technical diagrams, page-fit validation, accessible PDF/SVG/JSON/ZIP export, and manifest-bound release evidence.

No `v0.3.0` release tag exists at the time of this entry.

## 0.2.x — Retroactive canon-aligned MVP line

### Added

- Immutable user → rig → rig revision → run → patch library → patch hierarchy.
- Deterministic compiler contracts, canonical JSON, stable hashes, stage receipts, and artifact manifests.
- Canonical PatchGraph, five-phase PatchPlan, deterministic variations, and validation reporting.
- Canonical credits and exports API under `/api/canon/*`.
- Test-mode Stripe-style webhook and transactional ledger behavior.
- Instrument-bench workspace, graph/table accessibility pair, and light/dark themes.
- Security, operations, accessibility, canon-alignment, and continuation documentation.

### Changed

- Canonical UI export and credit clients migrated away from legacy frontend debit behavior.
- Historical social, publishing, leaderboard, and referral surfaces disabled by default.

### Known gaps

- Legacy acceptance and inventory paths remain partially present.
- Production deployment and live payments have not been authorized.
- Staging backup/restore, full operational, and production-readiness evidence remain incomplete.

This line includes work merged through PRs #47, #49, and subsequent documentation alignment. It is a descriptive lineage, not a claim that every `0.2.x` tag was issued.

## 0.1.x — Retroactive historical prototype line

Early PatchHive work explored rig ingestion, patch generation, exports, publishing, community, deployment packaging, and Abraxas bridge concepts. These surfaces vary in authority and maturity. Current ship authority comes from the canon-aligned documentation and active runtime classification, not historical root notes or disabled legacy modules.

No complete historical release sequence is asserted.
