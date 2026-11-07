# Changelog

All notable changes to PatchHive are documented here.

This project follows [Semantic Versioning](docs/VERSIONING.md) beginning with the adoption of the formal release policy. From 0.3.0-alpha.3 on, release-please writes new entries from Conventional Commit PR titles; do not add an Unreleased section by hand. Historical entries are reconstructed from repository evidence and are labeled as retroactive classifications rather than invented release tags.

## [0.3.0-alpha.17](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.16...v0.3.0-alpha.17) (2026-11-07)


### Added

* **account:** buy credits, hold a plan and cancel it, behind the checkout flags (spec 004 T090) ([#347](https://github.com/Zero-State-LLC/Patch-Hive/issues/347)) ([69f14c8](https://github.com/Zero-State-LLC/Patch-Hive/commit/69f14c8db33a4e766015438aeb413b528cea77b2))


### Fixed

* **account:** one balance route, and a referral summary from the real rows (spec 004 T090) ([#345](https://github.com/Zero-State-LLC/Patch-Hive/issues/345)) ([8045b4d](https://github.com/Zero-State-LLC/Patch-Hive/commit/8045b4da9d91155f81853391973fa474f564d88a))
* **commerce:** an operator's rejection closes the checkout (spec 004 T090) ([#344](https://github.com/Zero-State-LLC/Patch-Hive/issues/344)) ([690a9bf](https://github.com/Zero-State-LLC/Patch-Hive/commit/690a9bfdaa73117e5cfc870e8c0c6ccae43b8d3f))
* **commerce:** guard the other ledgers and referral codes in the database (spec 004 T090) ([#346](https://github.com/Zero-State-LLC/Patch-Hive/issues/346)) ([59f4001](https://github.com/Zero-State-LLC/Patch-Hive/commit/59f4001d680d07f7b2ae188c9b3963cd21836036))


### Documentation

* record the 0.3.0-alpha.16 deploy ([#341](https://github.com/Zero-State-LLC/Patch-Hive/issues/341)) ([cade89c](https://github.com/Zero-State-LLC/Patch-Hive/commit/cade89c83849c217ce4de60ed95030cf5beb3924))
* **specs:** converge spec 004 with the code and tick T090 ([#348](https://github.com/Zero-State-LLC/Patch-Hive/issues/348)) ([422e61c](https://github.com/Zero-State-LLC/Patch-Hive/commit/422e61c8e283d19afc50dfaf2765e025478d43de))

## [0.3.0-alpha.16](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.15...v0.3.0-alpha.16) (2026-11-07)


### Added

* **catalog:** roll a load back by run ID, and keep each load's record (spec 003 T090) ([#340](https://github.com/Zero-State-LLC/Patch-Hive/issues/340)) ([f4b80cc](https://github.com/Zero-State-LLC/Patch-Hive/commit/f4b80cc7cf2ff9deffe9e2571ae2e2d1387e935c))


### Fixed

* **catalog:** keep a fetch refusal apart from not found, and add the filter (spec 003 T090) ([#335](https://github.com/Zero-State-LLC/Patch-Hive/issues/335)) ([e507303](https://github.com/Zero-State-LLC/Patch-Hive/commit/e50730311337266d57f64a8320cc4e8ea4b2cc4c))
* **catalog:** make the loader the only writer of catalog rows (spec 003 T090) ([#338](https://github.com/Zero-State-LLC/Patch-Hive/issues/338)) ([1349bcb](https://github.com/Zero-State-LLC/Patch-Hive/commit/1349bcb9176a418824a9abf36de0262d1f464148))


### Documentation

* record the 0.3.0-alpha.15 deploy ([#332](https://github.com/Zero-State-LLC/Patch-Hive/issues/332)) ([34e90c4](https://github.com/Zero-State-LLC/Patch-Hive/commit/34e90c484d1327821a8405c874c0decf549d9212))
* **spec-003:** converge the spec with the code and tick T090 ([#339](https://github.com/Zero-State-LLC/Patch-Hive/issues/339)) ([b783f19](https://github.com/Zero-State-LLC/Patch-Hive/commit/b783f197025b412d05b55a23442be461313ffe3d))

## [0.3.0-alpha.15](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.14...v0.3.0-alpha.15) (2026-11-06)


### Added

* **export:** write each page's operation steps for its own patch (spec 002 T091) ([#329](https://github.com/Zero-State-LLC/Patch-Hive/issues/329)) ([ea88bea](https://github.com/Zero-State-LLC/Patch-Hive/commit/ea88bea4f3b992a61efdc65bbf1a1d219e3ed72c))


### Fixed

* **engine:** read patch titles and intents from their cables ([#331](https://github.com/Zero-State-LLC/Patch-Hive/issues/331)) ([88f29a4](https://github.com/Zero-State-LLC/Patch-Hive/commit/88f29a4fb9fff09a7dce91f8c14b958deafaab3a))


### Documentation

* record the 0.3.0-alpha.14 deploy and reopen spec 002's FR-008 ([#328](https://github.com/Zero-State-LLC/Patch-Hive/issues/328)) ([cd4e47f](https://github.com/Zero-State-LLC/Patch-Hive/commit/cd4e47f7cd5adaf74d3f7f0a472dd4dd8b113696))

## [0.3.0-alpha.14](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.13...v0.3.0-alpha.14) (2026-11-06)


### Added

* **export:** draw each book page's diagram and name its modules (spec 002 T090) ([#326](https://github.com/Zero-State-LLC/Patch-Hive/issues/326)) ([f00903d](https://github.com/Zero-State-LLC/Patch-Hive/commit/f00903db1ad738c59f6bf4207b35b8bd98a0a03d))


### Documentation

* tick spec 001 T090 and record the 0.3.0-alpha.13 deploy ([#323](https://github.com/Zero-State-LLC/Patch-Hive/issues/323)) ([3522004](https://github.com/Zero-State-LLC/Patch-Hive/commit/3522004b21c5c607bc936d8c9d04f8631fd807fc))

## [0.3.0-alpha.13](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.12...v0.3.0-alpha.13) (2026-11-06)


### Added

* **001:** keep what a run and an evidence decision leave behind (T090) ([#321](https://github.com/Zero-State-LLC/Patch-Hive/issues/321)) ([1f3a357](https://github.com/Zero-State-LLC/Patch-Hive/commit/1f3a35757442ecc73c46d33c2c395504af9e0b7b))
* **001:** one role per module, and catch loops through other modules (T090) ([#322](https://github.com/Zero-State-LLC/Patch-Hive/issues/322)) ([5f446c0](https://github.com/Zero-State-LLC/Patch-Hive/commit/5f446c01652ee5ef4eebb22550a768931b08d056))
* **catalog:** add a NOISE category and move 17 noise-first rows ([#312](https://github.com/Zero-State-LLC/Patch-Hive/issues/312)) ([e0a1443](https://github.com/Zero-State-LLC/Patch-Hive/commit/e0a14434373947b462788a70fa9a8fc6541839b4))
* **catalog:** promote 46 more leads a search of makers' sites confirms (FR-034) ([#314](https://github.com/Zero-State-LLC/Patch-Hive/issues/314)) ([9787f50](https://github.com/Zero-State-LLC/Patch-Hive/commit/9787f501f2a6836c325f99ab1deb5ff2a5b4b575))
* **catalog:** retire 38 public rows that repeat another row's maker page ([#316](https://github.com/Zero-State-LLC/Patch-Hive/issues/316)) ([1433e62](https://github.com/Zero-State-LLC/Patch-Hive/commit/1433e62128e74a9c0187b6a26827e17235a2e8ff))


### Fixed

* **catalog:** give each maker one brand, and retire what the splits left ([#318](https://github.com/Zero-State-LLC/Patch-Hive/issues/318)) ([923375d](https://github.com/Zero-State-LLC/Patch-Hive/commit/923375d1cad90bcd486de5b077adcf2b99825f83))


### Documentation

* record the 0.3.0-alpha.12 deploy to staging and production ([#311](https://github.com/Zero-State-LLC/Patch-Hive/issues/311)) ([45e3780](https://github.com/Zero-State-LLC/Patch-Hive/commit/45e3780cb4b4a851650c4aefad26aea6597b453a))
* record the access-basis retry and FR-034 load on production ([#307](https://github.com/Zero-State-LLC/Patch-Hive/issues/307)) ([e2c703d](https://github.com/Zero-State-LLC/Patch-Hive/commit/e2c703dc23cf3a81e663e41fb9c2bf748de425b9))
* record the brand fix on production ([#319](https://github.com/Zero-State-LLC/Patch-Hive/issues/319)) ([9bfa8c7](https://github.com/Zero-State-LLC/Patch-Hive/commit/9bfa8c784c44516dd60e95e622093e82175e9055))
* record the lead search load on production ([#315](https://github.com/Zero-State-LLC/Patch-Hive/issues/315)) ([e314a99](https://github.com/Zero-State-LLC/Patch-Hive/commit/e314a99f0f9d1c5b7ec2ab9c92ee4c249802144f))
* record the NOISE load on staging and production ([#313](https://github.com/Zero-State-LLC/Patch-Hive/issues/313)) ([dd35349](https://github.com/Zero-State-LLC/Patch-Hive/commit/dd35349c3852f90f591c809a58152438848107dd))
* record the second-name retirements on production ([#317](https://github.com/Zero-State-LLC/Patch-Hive/issues/317)) ([4f8825d](https://github.com/Zero-State-LLC/Patch-Hive/commit/4f8825d7c5a1de85fdfb9f8e649b4f68ed6968b6))

## [0.3.0-alpha.12](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.11...v0.3.0-alpha.12) (2026-11-06)


### Added

* **catalog:** fill categories, widths and supply draws from free maker reads ([#304](https://github.com/Zero-State-LLC/Patch-Hive/issues/304)) ([9c610b0](https://github.com/Zero-State-LLC/Patch-Hive/commit/9c610b0ee163fb3f44fc97be0feec85fcb8f372c))
* **catalog:** promote 220 leads their makers' pages confirm (FR-034) ([#308](https://github.com/Zero-State-LLC/Patch-Hive/issues/308)) ([6826c36](https://github.com/Zero-State-LLC/Patch-Hive/commit/6826c361e7eeeaadd98338c33de1f044b5f50393))
* **catalog:** tag 5 more maker rows after retrying the access check ([#306](https://github.com/Zero-State-LLC/Patch-Hive/issues/306)) ([90d87d3](https://github.com/Zero-State-LLC/Patch-Hive/commit/90d87d31f537842aba2cb3aeebd2c53d8a14ab49))


### Fixed

* **api:** give paged module, catalog and rack lists a fixed order ([#309](https://github.com/Zero-State-LLC/Patch-Hive/issues/309)) ([29509af](https://github.com/Zero-State-LLC/Patch-Hive/commit/29509af8723284c0e22719cff1a8fbd47ce79b5f))


### Documentation

* record the 0.3.0-alpha.11 deploy to staging and production ([#303](https://github.com/Zero-State-LLC/Patch-Hive/issues/303)) ([9f2458f](https://github.com/Zero-State-LLC/Patch-Hive/commit/9f2458fde2e93cfbba7681b8ac09b13cf5daef97))
* record the catalog load on production ([#301](https://github.com/Zero-State-LLC/Patch-Hive/issues/301)) ([80be54c](https://github.com/Zero-State-LLC/Patch-Hive/commit/80be54c50c90987e07d85d54863d3c6656ca46e5))
* record the free-reads load on production ([#305](https://github.com/Zero-State-LLC/Patch-Hive/issues/305)) ([54b7608](https://github.com/Zero-State-LLC/Patch-Hive/commit/54b7608a5dd8fbfbb19f7e398ea1e47a967f6d54))

## [0.3.0-alpha.11](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.10...v0.3.0-alpha.11) (2026-11-05)


### Added

* **catalog:** set the access basis and clear ModularGrid URLs in the load ([#299](https://github.com/Zero-State-LLC/Patch-Hive/issues/299)) ([5efa122](https://github.com/Zero-State-LLC/Patch-Hive/commit/5efa12251c8c108e9871fc929ff6093341dcdaec))


### Fixed

* **ops:** give each design walkthrough run its own credit grant ([#298](https://github.com/Zero-State-LLC/Patch-Hive/issues/298)) ([ca210e7](https://github.com/Zero-State-LLC/Patch-Hive/commit/ca210e7562bc6545d66e73a41ca68bfa0518ce29))


### Documentation

* record the 0.3.0-alpha.10 deploy to staging and production ([#297](https://github.com/Zero-State-LLC/Patch-Hive/issues/297)) ([ed52509](https://github.com/Zero-State-LLC/Patch-Hive/commit/ed52509bde9937aee661744d66687da8a682d426))

## [0.3.0-alpha.10](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.9...v0.3.0-alpha.10) (2026-11-05)


### Added

* **catalog:** basic proxy tier by default, no paid route around a bot check ([#254](https://github.com/Zero-State-LLC/Patch-Hive/issues/254)) ([537ac0a](https://github.com/Zero-State-LLC/Patch-Hive/commit/537ac0a79d4823904718e3d770097370c862ce60))
* **frontend:** add a delete-account control ([#290](https://github.com/Zero-State-LLC/Patch-Hive/issues/290)) ([bab6520](https://github.com/Zero-State-LLC/Patch-Hive/commit/bab6520a0dce895cffdd753250c0e7b6faad1184))
* **frontend:** add a factual privacy notice ([#285](https://github.com/Zero-State-LLC/Patch-Hive/issues/285)) ([06c91de](https://github.com/Zero-State-LLC/Patch-Hive/commit/06c91deab5893f4e8e06e2a50b81eb9cd2cb7687))
* **racks:** warn about in-rack power supplies without counting them ([#291](https://github.com/Zero-State-LLC/Patch-Hive/issues/291)) ([8657171](https://github.com/Zero-State-LLC/Patch-Hive/commit/8657171966322f25f4d37dc9ae9b7f09212d76bf))


### Fixed

* **catalog:** leave rows with an unknown access basis out of anonymous reads ([#293](https://github.com/Zero-State-LLC/Patch-Hive/issues/293)) ([fe9be6e](https://github.com/Zero-State-LLC/Patch-Hive/commit/fe9be6ec5cd4a4193a810a9187bb2ba590ab7587))
* **catalog:** stop returning ModularGrid fields from the API ([#294](https://github.com/Zero-State-LLC/Patch-Hive/issues/294)) ([491fccd](https://github.com/Zero-State-LLC/Patch-Hive/commit/491fccda70210ba3d492971c528c25f9ca936729))
* **commerce:** let any live subscription cancel, and pay no reward to a deleted referrer ([#292](https://github.com/Zero-State-LLC/Patch-Hive/issues/292)) ([08694be](https://github.com/Zero-State-LLC/Patch-Hive/commit/08694be4f8243c9858543af5bc1f82eeb34792b5))
* **evidence:** drop JPEG comments when re-encoding photos ([#287](https://github.com/Zero-State-LLC/Patch-Hive/issues/287)) ([1b98867](https://github.com/Zero-State-LLC/Patch-Hive/commit/1b988676bee59d4f708ae448ef1605abfd3d2b11))
* **evidence:** only report ready for generation when generation would accept the rig ([#289](https://github.com/Zero-State-LLC/Patch-Hive/issues/289)) ([229be7d](https://github.com/Zero-State-LLC/Patch-Hive/commit/229be7d7e5eadb5271072e4c463fddc970f4af9e)), closes [#283](https://github.com/Zero-State-LLC/Patch-Hive/issues/283)


### Data

* **catalog:** add VIDEO and SYSTEM categories and apply the owner's taxonomy calls ([#286](https://github.com/Zero-State-LLC/Patch-Hive/issues/286)) ([3d9e072](https://github.com/Zero-State-LLC/Patch-Hive/commit/3d9e072b8cf0efdd3504673f56cfad70f89d6742))


### Operations

* run the case-catalog seed dry runs and report coverage again ([#276](https://github.com/Zero-State-LLC/Patch-Hive/issues/276)) ([1521499](https://github.com/Zero-State-LLC/Patch-Hive/commit/1521499fbafe5e4871ac2821ed0ceebc0ca80af6)), closes [#264](https://github.com/Zero-State-LLC/Patch-Hive/issues/264)


### Documentation

* record alpha.8 staging receipts, VirusTotal results and a corpus shot list ([#277](https://github.com/Zero-State-LLC/Patch-Hive/issues/277)) ([66a9516](https://github.com/Zero-State-LLC/Patch-Hive/commit/66a9516d0b46017665ea8cde88c4b18a43ff2fc1))
* record the 0.3.0-alpha.9 deploy to staging and production ([#288](https://github.com/Zero-State-LLC/Patch-Hive/issues/288)) ([a5611d3](https://github.com/Zero-State-LLC/Patch-Hive/commit/a5611d34f2aca8cca74600b5070787844b49884a))
* record the owner's 56 decisions, a glossary and the maker permission ADR ([#278](https://github.com/Zero-State-LLC/Patch-Hive/issues/278)) ([19eeace](https://github.com/Zero-State-LLC/Patch-Hive/commit/19eeaceb82311fb842e21c0c5d9fb9b8c9d45cef))
* **specs:** confirm spec 001 (T001) and finish its plan (T002) ([#282](https://github.com/Zero-State-LLC/Patch-Hive/issues/282)) ([65fd705](https://github.com/Zero-State-LLC/Patch-Hive/commit/65fd7053af92348609fa0a36a561162fb4238f40))
* **specs:** confirm spec 002 (T001) and finish its plan (T002) ([#279](https://github.com/Zero-State-LLC/Patch-Hive/issues/279)) ([45c9bed](https://github.com/Zero-State-LLC/Patch-Hive/commit/45c9bedab6cb191ad60ee5d489744ff8d1963329))
* **specs:** confirm spec 003 (T001) and finish its plan (T002) ([#284](https://github.com/Zero-State-LLC/Patch-Hive/issues/284)) ([9f1aae4](https://github.com/Zero-State-LLC/Patch-Hive/commit/9f1aae43516aa863c3d220310fac7bf58608cfb3))
* **specs:** confirm spec 004 (T001) and finish its plan (T002) ([#281](https://github.com/Zero-State-LLC/Patch-Hive/issues/281)) ([8571f0e](https://github.com/Zero-State-LLC/Patch-Hive/commit/8571f0e55fcb147a14b645f4b3b537e0f83072ab))

## [0.3.0-alpha.9](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.8...v0.3.0-alpha.9) (2026-11-05)


### Fixed

* **export:** escape names in SVG output ([#280](https://github.com/Zero-State-LLC/Patch-Hive/issues/280)) ([bbccfc1](https://github.com/Zero-State-LLC/Patch-Hive/commit/bbccfc1c136f73b3325284e034f7fd20cfdc142d))


### Documentation

* record the 0.3.0-alpha.8 deploy to staging and production ([#274](https://github.com/Zero-State-LLC/Patch-Hive/issues/274)) ([007b437](https://github.com/Zero-State-LLC/Patch-Hive/commit/007b437bcb18f725f067a6e0f933f430c6302ebb))

## [0.3.0-alpha.8](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.7...v0.3.0-alpha.8) (2026-11-05)


### Fixed

* **api:** keep exception text out of catalog and compatibility responses ([#267](https://github.com/Zero-State-LLC/Patch-Hive/issues/267)) ([29196c8](https://github.com/Zero-State-LLC/Patch-Hive/commit/29196c88741aa97e854daebc2b28a1bdd45ae486))
* **ci:** name the database secrets instead of looking them up by expression ([#273](https://github.com/Zero-State-LLC/Patch-Hive/issues/273)) ([40117bc](https://github.com/Zero-State-LLC/Patch-Hive/commit/40117bc4a2ebde2a95f5bda6b9be5c4faa7ebb13))
* **deps:** override minimatch to 11 for GHSA-g3hv-75wg-m249 ([#263](https://github.com/Zero-State-LLC/Patch-Hive/issues/263)) ([dd67257](https://github.com/Zero-State-LLC/Patch-Hive/commit/dd672572bd55be495dd432927f7bcee76c04f98f))
* **ops:** find the acceptance JUnit report when the receipt path is relative ([#259](https://github.com/Zero-State-LLC/Patch-Hive/issues/259)) ([2bf82c1](https://github.com/Zero-State-LLC/Patch-Hive/commit/2bf82c18f5bd0e0952874dee70e752cd9b5d7cfa))
* **runs:** return a run's patches in generation order ([#261](https://github.com/Zero-State-LLC/Patch-Hive/issues/261)) ([6a31173](https://github.com/Zero-State-LLC/Patch-Hive/commit/6a31173df0a07c93432bb48edb88c9c9faf81d62))
* **security:** remove the undeployed legacy HTTP API ([#269](https://github.com/Zero-State-LLC/Patch-Hive/issues/269)) ([219a822](https://github.com/Zero-State-LLC/Patch-Hive/commit/219a8224b71c2eea644bb0f0612fb6cd6f737a63))
* **seed:** stop printing the demo password ([#268](https://github.com/Zero-State-LLC/Patch-Hive/issues/268)) ([1330a9a](https://github.com/Zero-State-LLC/Patch-Hive/commit/1330a9a1780606297326409d7b2f692378f4a9f8))


### Operations

* **codeql:** scan the workflows again ([#270](https://github.com/Zero-State-LLC/Patch-Hive/issues/270)) ([c24ce86](https://github.com/Zero-State-LLC/Patch-Hive/commit/c24ce8669f004818c7ee8268a58ee7d7b83b9075))
* restore the security and backend lint gates removed in 5b85f58 ([#266](https://github.com/Zero-State-LLC/Patch-Hive/issues/266)) ([43459fd](https://github.com/Zero-State-LLC/Patch-Hive/commit/43459fd10444e10ce82fab88a80ebe5c5728e107))
* test on the Python production runs, and round-trip migrations ([#271](https://github.com/Zero-State-LLC/Patch-Hive/issues/271)) ([b98c243](https://github.com/Zero-State-LLC/Patch-Hive/commit/b98c243f1fa6a24210afad7c427033e998bc6ac1))


### Documentation

* acceptance receipt from main, beta drills done, board mirror for 2026-11-04 ([#262](https://github.com/Zero-State-LLC/Patch-Hive/issues/262)) ([be6b728](https://github.com/Zero-State-LLC/Patch-Hive/commit/be6b7283e13a1747b461ccf38eef5fc0272bfb89))
* **evidence:** alpha.7 staging receipts (walkthrough, restore drill, acceptance) ([#260](https://github.com/Zero-State-LLC/Patch-Hive/issues/260)) ([5d0b6e5](https://github.com/Zero-State-LLC/Patch-Hive/commit/5d0b6e57a7d8a53dd0700c5a82d55620c0dc3838))
* record the 0.3.0-alpha.7 deploy to staging and production ([#257](https://github.com/Zero-State-LLC/Patch-Hive/issues/257)) ([c36fcdf](https://github.com/Zero-State-LLC/Patch-Hive/commit/c36fcdf761d667d5f9b41366c812e8f53a0e7688))
* record the restored CI gates and what's left to decide ([#272](https://github.com/Zero-State-LLC/Patch-Hive/issues/272)) ([ac9d2f5](https://github.com/Zero-State-LLC/Patch-Hive/commit/ac9d2f57594994079e4cc6bb4bd2635219fe9909))
* review the unlanded branches and tie T101c to T101b ([#265](https://github.com/Zero-State-LLC/Patch-Hive/issues/265)) ([86a0a29](https://github.com/Zero-State-LLC/Patch-Hive/commit/86a0a2984241cd583d80bb8ce2566b33a7573d3e))

## [0.3.0-alpha.7](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.6...v0.3.0-alpha.7) (2026-11-04)


### Added

* **008:** operator driver for the readiness pin and the five-event replay ([#248](https://github.com/Zero-State-LLC/Patch-Hive/issues/248)) ([7a769b0](https://github.com/Zero-State-LLC/Patch-Hive/commit/7a769b0e3bb40befb466930571b2ef0461973683))


### Fixed

* **f5:** the rig builder reads rigs through the canon alias; the scanner sees split calls ([#243](https://github.com/Zero-State-LLC/Patch-Hive/issues/243)) ([bbdd871](https://github.com/Zero-State-LLC/Patch-Hive/commit/bbdd871a5ea9ceedb19b9444189fe225011a5b3f))
* **home:** keep the brand inside a 320px screen before the display font loads ([#256](https://github.com/Zero-State-LLC/Patch-Hive/issues/256)) ([eb6062d](https://github.com/Zero-State-LLC/Patch-Hive/commit/eb6062de58eff79aebb62bcfbfea7a227a97c546))


### Specifications

* prep specs 001-005 for owner confirmation (status, plan drafts, 005 gaps) ([#251](https://github.com/Zero-State-LLC/Patch-Hive/issues/251)) ([9437177](https://github.com/Zero-State-LLC/Patch-Hive/commit/94371770030d002f0c7d0fd77f1aaf27c3e658b2))


### Data

* **catalog:** 003 T031 offline pass: whole-tag rules (74 rows), store taxonomy kept by feed adapters ([#253](https://github.com/Zero-State-LLC/Patch-Hive/issues/253)) ([1a636af](https://github.com/Zero-State-LLC/Patch-Hive/commit/1a636af88f6b0db096f5b0d0a68a7010a7da5678))
* **catalog:** settle 9 two-category rows from committed data (category v2) ([#250](https://github.com/Zero-State-LLC/Patch-Hive/issues/250)) ([b45ddfc](https://github.com/Zero-State-LLC/Patch-Hive/commit/b45ddfc84da013ecc98917ed3f912613616b0c23))


### Operations

* acceptance in CI and on Neon staging, ledger reconcile CLI, restore drill ([#252](https://github.com/Zero-State-LLC/Patch-Hive/issues/252)) ([fd50806](https://github.com/Zero-State-LLC/Patch-Hive/commit/fd508061e769bd837903caf5cc9a53a3fc998a42))
* **release:** skip creating a release that already exists ([#245](https://github.com/Zero-State-LLC/Patch-Hive/issues/245)) ([a0e5d25](https://github.com/Zero-State-LLC/Patch-Hive/commit/a0e5d2525ad0435c2f1f577be3fde0f011b73700))


### Documentation

* **evidence:** branch triage of 2026-11-03 and the 24 branches deleted ([#247](https://github.com/Zero-State-LLC/Patch-Hive/issues/247)) ([22d150b](https://github.com/Zero-State-LLC/Patch-Hive/commit/22d150b3326beba40d72155d96f007069b5f556a))
* **evidence:** owner packet after the Project [#8](https://github.com/Zero-State-LLC/Patch-Hive/issues/8) Backlog remediation ([#249](https://github.com/Zero-State-LLC/Patch-Hive/issues/249)) ([a29a86f](https://github.com/Zero-State-LLC/Patch-Hive/commit/a29a86f1b6f34b7d5f8e75edc61994ff6e8cb4e7))
* record the rig builder's canon reads and refresh the board mirror ([#255](https://github.com/Zero-State-LLC/Patch-Hive/issues/255)) ([7e07fd9](https://github.com/Zero-State-LLC/Patch-Hive/commit/7e07fd911267360ac79947b56cc563b2a44c490c))
* record what the alpha.6 deploy settled across the roadmap, state and specs ([#242](https://github.com/Zero-State-LLC/Patch-Hive/issues/242)) ([ded89a4](https://github.com/Zero-State-LLC/Patch-Hive/commit/ded89a41af64a1536ca00681eb846500030acd29))
* refresh the board mirror and the release priority after the alpha.6 deploy ([#241](https://github.com/Zero-State-LLC/Patch-Hive/issues/241)) ([b864a0a](https://github.com/Zero-State-LLC/Patch-Hive/commit/b864a0aeb1de362aeeda6eeec436443fcaa52607))
* **state:** main at 9c42bd6 (0.3.0-alpha.6) deployed to staging and production ([#239](https://github.com/Zero-State-LLC/Patch-Hive/issues/239)) ([3688037](https://github.com/Zero-State-LLC/Patch-Hive/commit/368803746d8b5e219cc47a608bdda74034f89e06))

## [0.3.0-alpha.6](https://github.com/Zero-State-LLC/Patch-Hive/compare/v0.3.0-alpha.5...v0.3.0-alpha.6) (2026-11-03)


### Added

* **002:** lock publication rows on transitions; rate-limit and dedupe reports ([#197](https://github.com/Zero-State-LLC/Patch-Hive/issues/197)) ([1209396](https://github.com/Zero-State-LLC/Patch-Hive/commit/12093968b5dc849ce44d4c21ff369a1d1de5bf46))
* **003:** apply checks the reviewed inputs_hash; retirements need evidence ([#198](https://github.com/Zero-State-LLC/Patch-Hive/issues/198)) ([ba8e3d2](https://github.com/Zero-State-LLC/Patch-Hive/commit/ba8e3d222708a0e03cc7b3d64250494d3502748a))
* **003:** require a committed approval for paid catalog fetches ([#196](https://github.com/Zero-State-LLC/Patch-Hive/issues/196)) ([825defe](https://github.com/Zero-State-LLC/Patch-Hive/commit/825defeb8fae6288a2e165d773f19aac3c68a0b4))
* **004:** account deletion anonymizes the user and keeps the ledger (OQ-12) ([#194](https://github.com/Zero-State-LLC/Patch-Hive/issues/194)) ([653911f](https://github.com/Zero-State-LLC/Patch-Hive/commit/653911f556ee9767f097e7f1e9ebb70e45f21ca9))
* **004:** Machine B credit checkout behind the payments flag (T046) ([#209](https://github.com/Zero-State-LLC/Patch-Hive/issues/209)) ([5ac3209](https://github.com/Zero-State-LLC/Patch-Hive/commit/5ac320907ff2dac62c5309390634d84b7fa8e982))
* **004:** Machine B refunds and disputes (OQ-2, T053) ([#214](https://github.com/Zero-State-LLC/Patch-Hive/issues/214)) ([b6cc917](https://github.com/Zero-State-LLC/Patch-Hive/commit/b6cc917ae1bfe8050480592700e70d288fc358ab))
* **004:** Machine C subscriptions (T049) ([#219](https://github.com/Zero-State-LLC/Patch-Hive/issues/219)) ([6d33e80](https://github.com/Zero-State-LLC/Patch-Hive/commit/6d33e8018681c4e0f155622ab34e14af28815ed2))
* **004:** operator resolve for unresolved checkout events (T048b) ([#211](https://github.com/Zero-State-LLC/Patch-Hive/issues/211)) ([cf8fd3f](https://github.com/Zero-State-LLC/Patch-Hive/commit/cf8fd3f5a9e9e6e433ff363829e0ac036d2047ed))
* **004:** tier from subscription, STUDIO fair-use spending (T050) ([#224](https://github.com/Zero-State-LLC/Patch-Hive/issues/224)) ([571ba23](https://github.com/Zero-State-LLC/Patch-Hive/commit/571ba23cd4a7b82fedf5778ab1a59f3b204efadb))
* **005:** gate the decision runtime on a signed 007 receipt (T080) ([#185](https://github.com/Zero-State-LLC/Patch-Hive/issues/185)) ([d6b791c](https://github.com/Zero-State-LLC/Patch-Hive/commit/d6b791cd01116016c838c3557deb013d45bf6128))
* **005:** NVIDIA vision provider beside Clef (T086) ([#189](https://github.com/Zero-State-LLC/Patch-Hive/issues/189)) ([176779e](https://github.com/Zero-State-LLC/Patch-Hive/commit/176779e3ba55b185e06bfd8d5f8f785ca43cf4cf))
* **005:** staging NVIDIA timeout 60 s and a pinned Meta Llama fallback model (T086) ([#192](https://github.com/Zero-State-LLC/Patch-Hive/issues/192)) ([7dbdb57](https://github.com/Zero-State-LLC/Patch-Hive/commit/7dbdb578a09efeae419a0873eef080a80dead585))
* **007:** add operator driver for the evaluation and enablement chain ([#203](https://github.com/Zero-State-LLC/Patch-Hive/issues/203)) ([ee5326e](https://github.com/Zero-State-LLC/Patch-Hive/commit/ee5326e21796d1dec44c5bd6a22f6dfedb9ea2a7))
* **007:** find openly licensed corpus photos via context.dev (T010b) ([#206](https://github.com/Zero-State-LLC/Patch-Hive/issues/206)) ([7493472](https://github.com/Zero-State-LLC/Patch-Hive/commit/74934729f6cac4c51920cb3e30b5b0b85dc46da5))
* **008:** pin only against a signed 007 receipt and sign the pin (T071) ([#186](https://github.com/Zero-State-LLC/Patch-Hive/issues/186)) ([e59d9a9](https://github.com/Zero-State-LLC/Patch-Hive/commit/e59d9a961c9ae01661248cdb624671bcfeb4ac30))
* **commerce:** admin reject for unresolved provider events (004 T048) ([#184](https://github.com/Zero-State-LLC/Patch-Hive/issues/184)) ([41bef96](https://github.com/Zero-State-LLC/Patch-Hive/commit/41bef96f525c6528ab3058ec31d76e3ad30eae6f))
* **evidence:** cap retention at 90 days and purge bytes on owner image delete ([#193](https://github.com/Zero-State-LLC/Patch-Hive/issues/193)) ([0eb1acd](https://github.com/Zero-State-LLC/Patch-Hive/commit/0eb1acd1b9854172500a6caa56b6a424499ac745))
* **frontend:** a page for each patch, on its rig's rail ([#232](https://github.com/Zero-State-LLC/Patch-Hive/issues/232)) ([dccc88f](https://github.com/Zero-State-LLC/Patch-Hive/commit/dccc88f73fa4f57e2725fa3bcdbceb25f685b782))
* **frontend:** app shell that recovers, names screens and loads less ([#227](https://github.com/Zero-State-LLC/Patch-Hive/issues/227)) ([2d17957](https://github.com/Zero-State-LLC/Patch-Hive/commit/2d17957886ab4b3cf49e2437ad44f34a2b50b01a))
* **frontend:** finish the light theme, remember it, and guard the design ([#225](https://github.com/Zero-State-LLC/Patch-Hive/issues/225)) ([5879e5b](https://github.com/Zero-State-LLC/Patch-Hive/commit/5879e5b6c05c07a598c78b559494f8fcc0184c27))
* **frontend:** keyboard tabs, a nav that shows it scrolls, one heading outline ([#235](https://github.com/Zero-State-LLC/Patch-Hive/issues/235)) ([f496362](https://github.com/Zero-State-LLC/Patch-Hive/commit/f4963623b0d28974f66e2d4323cac635ea97a156))
* **frontend:** motion by transform and opacity only, unused code gone ([#238](https://github.com/Zero-State-LLC/Patch-Hive/issues/238)) ([5135762](https://github.com/Zero-State-LLC/Patch-Hive/commit/51357624748598e34b297ae4af362446722bc798))
* **frontend:** move modules on the rail by drag, tap or keyboard, with Undo ([#237](https://github.com/Zero-State-LLC/Patch-Hive/issues/237)) ([fa8d09d](https://github.com/Zero-State-LLC/Patch-Hive/commit/fa8d09dd67d7ab67d4ba8db23514f3de3c9120aa))
* **frontend:** patch on the rail, and loading skeletons ([#222](https://github.com/Zero-State-LLC/Patch-Hive/issues/222)) ([55917bb](https://github.com/Zero-State-LLC/Patch-Hive/commit/55917bb98c753da78923a05d79c0ce366c4adffd))
* **frontend:** put the rig in the URL and link Racks with Rig detail ([#228](https://github.com/Zero-State-LLC/Patch-Hive/issues/228)) ([91414d2](https://github.com/Zero-State-LLC/Patch-Hive/commit/91414d2e90dabdb96afb2bc84f57af064837bbaa))
* **frontend:** rail redesign of the workbench UI under the Cyber Hive system ([#215](https://github.com/Zero-State-LLC/Patch-Hive/issues/215)) ([4fb2474](https://github.com/Zero-State-LLC/Patch-Hive/commit/4fb24745417a1758d55b65ae2a627a9891a4acdf))
* **frontend:** recompose Rig detail around the patch path ([#218](https://github.com/Zero-State-LLC/Patch-Hive/issues/218)) ([4a88069](https://github.com/Zero-State-LLC/Patch-Hive/commit/4a880699785f3cc977ee1256154b8785026c175d))
* **frontend:** recompose the remaining screens under the rail system ([#220](https://github.com/Zero-State-LLC/Patch-Hive/issues/220)) ([0d24cf2](https://github.com/Zero-State-LLC/Patch-Hive/commit/0d24cf295cbf52210e77b7ab356b6a4f3dd58c50))
* **frontend:** recompose the rig builder into steps on the rail ([#231](https://github.com/Zero-State-LLC/Patch-Hive/issues/231)) ([3e40b77](https://github.com/Zero-State-LLC/Patch-Hive/commit/3e40b770efe6998d4fe7e854f844d52761e1a790))
* **frontend:** say it plainly: dates, short ids, and words for codes ([#234](https://github.com/Zero-State-LLC/Patch-Hive/issues/234)) ([d6a2f1d](https://github.com/Zero-State-LLC/Patch-Hive/commit/d6a2f1df76e6f80f73b75313eacdd7593c2fc825))
* **frontend:** searches that wait for a pause, failures that say so ([#236](https://github.com/Zero-State-LLC/Patch-Hive/issues/236)) ([7f5abbe](https://github.com/Zero-State-LLC/Patch-Hive/commit/7f5abbe493482c9a15f64750656907519a5d38ea))
* **frontend:** show the product on Home, the demo rig on its rail ([#229](https://github.com/Zero-State-LLC/Patch-Hive/issues/229)) ([726be3a](https://github.com/Zero-State-LLC/Patch-Hive/commit/726be3a431182f2c75c65f65ab0b344a69f08fb5))


### Fixed

* **007:** keep only corpus photos that name their module; record the 300-search run (T010b) ([#208](https://github.com/Zero-State-LLC/Patch-Hive/issues/208)) ([ecf2eb7](https://github.com/Zero-State-LLC/Patch-Hive/commit/ecf2eb7257d96429b756a1ac562ab6a24d0c65ab))
* **evidence:** bind uploaded candidates to the stored evidence record id ([#202](https://github.com/Zero-State-LLC/Patch-Hive/issues/202)) ([2911d54](https://github.com/Zero-State-LLC/Patch-Hive/commit/2911d54b263ea05a29baa8d1a1ef48d2815d813a))
* **frontend:** keep the gallery's preselected module in the builder filter ([#233](https://github.com/Zero-State-LLC/Patch-Hive/issues/233)) ([9a67eb8](https://github.com/Zero-State-LLC/Patch-Hive/commit/9a67eb856ab9144e3fcc5e7457a3d852197b3f9f))
* **frontend:** wait for the session restore before rendering routes ([#221](https://github.com/Zero-State-LLC/Patch-Hive/issues/221)) ([c872b31](https://github.com/Zero-State-LLC/Patch-Hive/commit/c872b316437aff01829ddaf4f75d13c808a6264b))
* **referrals:** refuse unverified purchases (spec 004 FR-033) ([#183](https://github.com/Zero-State-LLC/Patch-Hive/issues/183)) ([9f4d3a2](https://github.com/Zero-State-LLC/Patch-Hive/commit/9f4d3a2e5048188f473b1eb7088fd45bc066da2e))


### Data

* **catalog:** apply the owner's T034 and A-155 decisions ([#172](https://github.com/Zero-State-LLC/Patch-Hive/issues/172)) ([414d96a](https://github.com/Zero-State-LLC/Patch-Hive/commit/414d96a39f45c9fb4e2133365738b1972340d095))
* **catalog:** fill Cockpit (golden) HP from the maker's COCKPIT MK1 page ([#176](https://github.com/Zero-State-LLC/Patch-Hive/issues/176)) ([927a086](https://github.com/Zero-State-LLC/Patch-Hive/commit/927a086a772cc91f0fa9a90ef0d57828a64453d2))
* **catalog:** fill Cockpit power and depth from the maker's COCKPIT MK1 page ([#178](https://github.com/Zero-State-LLC/Patch-Hive/issues/178)) ([5b46781](https://github.com/Zero-State-LLC/Patch-Hive/commit/5b46781b62bd7bc3c3cf4657a1e2abe6cbf11020))
* **catalog:** label Otool's jumper settings from its manual (spec 003 T034) ([#170](https://github.com/Zero-State-LLC/Patch-Hive/issues/170)) ([eabc044](https://github.com/Zero-State-LLC/Patch-Hive/commit/eabc044b0744a418bdb05eb6cf6e38e49788c588))
* **catalog:** quote the maker for eight hand-checked HP values (003 OQ-2) ([#200](https://github.com/Zero-State-LLC/Patch-Hive/issues/200)) ([9dba804](https://github.com/Zero-State-LLC/Patch-Hive/commit/9dba804ec18e21283427e5d51ca932b1222c7833))
* **catalog:** re-source 4 more legacy HP values, correct Dixie II to 6 HP (spec 003 T039) ([#174](https://github.com/Zero-State-LLC/Patch-Hive/issues/174)) ([4baf206](https://github.com/Zero-State-LLC/Patch-Hive/commit/4baf206f498cda93794656d3918332c8a1f54ebf))
* **catalog:** retailer evidence for the 57 unsourced HP values (FR-039) ([#180](https://github.com/Zero-State-LLC/Patch-Hive/issues/180)) ([ada8949](https://github.com/Zero-State-LLC/Patch-Hive/commit/ada8949ab88aa84b05f66787acf4f286fe708180))


### Operations

* **008,006:** staging walkthrough workflow and Design Engine flags for staging ([#213](https://github.com/Zero-State-LLC/Patch-Hive/issues/213)) ([820a136](https://github.com/Zero-State-LLC/Patch-Hive/commit/820a136bc86a794c7fe81c81dfd16b10f4ddaa1f))


### Documentation

* 006 OQ-3 operator receipts for 2026-11-02 (no closures) ([#207](https://github.com/Zero-State-LLC/Patch-Hive/issues/207)) ([74b7a93](https://github.com/Zero-State-LLC/Patch-Hive/commit/74b7a938cc2733225ded058022fae32f872ee87c))
* **006:** record operator task receipts, close T030 and T050b ([#190](https://github.com/Zero-State-LLC/Patch-Hive/issues/190)) ([f7b79ec](https://github.com/Zero-State-LLC/Patch-Hive/commit/f7b79ec7e7f90a242fb6bc8edb83364199f36bfc))
* **008,006:** staging walkthrough receipts; close T030b and T040b ([#216](https://github.com/Zero-State-LLC/Patch-Hive/issues/216)) ([7899458](https://github.com/Zero-State-LLC/Patch-Hive/commit/7899458eabd3ee9811cc767f6353d3d368d75501))
* owner action guide (2026-11-02) ([#201](https://github.com/Zero-State-LLC/Patch-Hive/issues/201)) ([9730109](https://github.com/Zero-State-LLC/Patch-Hive/commit/9730109ba5aeaa69f81c01cffed6deb99af4af91))
* record [#166](https://github.com/Zero-State-LLC/Patch-Hive/issues/166), [#167](https://github.com/Zero-State-LLC/Patch-Hive/issues/167), [#159](https://github.com/Zero-State-LLC/Patch-Hive/issues/159), the power_configs migration and the 9dbb5ba redeploy ([#168](https://github.com/Zero-State-LLC/Patch-Hive/issues/168)) ([4943db1](https://github.com/Zero-State-LLC/Patch-Hive/commit/4943db17e4ec9c938a1f1405e616f01353e76dcc))
* record [#168](https://github.com/Zero-State-LLC/Patch-Hive/issues/168), [#170](https://github.com/Zero-State-LLC/Patch-Hive/issues/170) and the Otool power_configs load ([#171](https://github.com/Zero-State-LLC/Patch-Hive/issues/171)) ([5c69e5d](https://github.com/Zero-State-LLC/Patch-Hive/commit/5c69e5d91c8819702c95d5050d78d4039c4b86db))
* record [#171](https://github.com/Zero-State-LLC/Patch-Hive/issues/171), [#172](https://github.com/Zero-State-LLC/Patch-Hive/issues/172) and the owner-decision loads ([#173](https://github.com/Zero-State-LLC/Patch-Hive/issues/173)) ([fb0139a](https://github.com/Zero-State-LLC/Patch-Hive/commit/fb0139a658a309efdfbbb0cbf1a21a8f442371ca))
* record [#173](https://github.com/Zero-State-LLC/Patch-Hive/issues/173), [#174](https://github.com/Zero-State-LLC/Patch-Hive/issues/174) and the HP v5 load ([#175](https://github.com/Zero-State-LLC/Patch-Hive/issues/175)) ([486e72f](https://github.com/Zero-State-LLC/Patch-Hive/commit/486e72f17691ef333c6b8c1fd76f70dc74f6c97c))
* record [#175](https://github.com/Zero-State-LLC/Patch-Hive/issues/175), [#176](https://github.com/Zero-State-LLC/Patch-Hive/issues/176) and the Cockpit (golden) load ([#177](https://github.com/Zero-State-LLC/Patch-Hive/issues/177)) ([81904b6](https://github.com/Zero-State-LLC/Patch-Hive/commit/81904b6b9c4db876a5d4ec4c923a1325c90cbbd0))
* record Jev's decisions on every open question (2026-11-01) ([#188](https://github.com/Zero-State-LLC/Patch-Hive/issues/188)) ([ad8c0f9](https://github.com/Zero-State-LLC/Patch-Hive/commit/ad8c0f9b7b50686344ecd57ee2664ba8f84a4f18))
* **spec:** threat models for the provider boundary and publishing surfaces ([#195](https://github.com/Zero-State-LLC/Patch-Hive/issues/195)) ([4b8fbb6](https://github.com/Zero-State-LLC/Patch-Hive/commit/4b8fbb6d9838648576fcc334009b6fd452de7ed1))
* **state:** record [#178](https://github.com/Zero-State-LLC/Patch-Hive/issues/178) and its Cockpit power/depth loads ([#179](https://github.com/Zero-State-LLC/Patch-Hive/issues/179)) ([867026b](https://github.com/Zero-State-LLC/Patch-Hive/commit/867026b1528e8ab9d85b519e90913de96f7789e4))
* **state:** record [#180](https://github.com/Zero-State-LLC/Patch-Hive/issues/180) and its retailer marker loads ([#181](https://github.com/Zero-State-LLC/Patch-Hive/issues/181)) ([93f55ed](https://github.com/Zero-State-LLC/Patch-Hive/commit/93f55ed3588810651e0f5eedaa25cfa93fecdfcc))
* **state:** record [#181](https://github.com/Zero-State-LLC/Patch-Hive/issues/181)-[#186](https://github.com/Zero-State-LLC/Patch-Hive/issues/186) ([#187](https://github.com/Zero-State-LLC/Patch-Hive/issues/187)) ([2c67a4e](https://github.com/Zero-State-LLC/Patch-Hive/commit/2c67a4e78ed9f6fd3a3a3d0c68a46c2c70965a8d))
* **state:** record [#204](https://github.com/Zero-State-LLC/Patch-Hive/issues/204)-[#211](https://github.com/Zero-State-LLC/Patch-Hive/issues/211) and the 20261102_credit_checkout migrations ([#212](https://github.com/Zero-State-LLC/Patch-Hive/issues/212)) ([a12260a](https://github.com/Zero-State-LLC/Patch-Hive/commit/a12260a397962e1b257a52948c209fed74fe6af5))
* **state:** record the 2026-11-02 migrations and deploys ([#187](https://github.com/Zero-State-LLC/Patch-Hive/issues/187)-[#203](https://github.com/Zero-State-LLC/Patch-Hive/issues/203)) ([#205](https://github.com/Zero-State-LLC/Patch-Hive/issues/205)) ([f2c6ada](https://github.com/Zero-State-LLC/Patch-Hive/commit/f2c6ada9b08b44dd541717fef89f7a58a2b4373c))

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
