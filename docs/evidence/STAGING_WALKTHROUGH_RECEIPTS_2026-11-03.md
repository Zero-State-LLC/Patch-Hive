# Staging walkthrough receipts, 2026-11-03

Owner-approved run of `.github/workflows/staging-walkthrough.yml` against `api-staging.patch-hive.com` (Worker version `4c315e91`, deployed from `b6cc917` after migrating staging to `20261102_purchase_refunds`, run [41557401152](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/41557401152)).

Run: [41557808902](https://github.com/Zero-State-LLC/Patch-Hive/actions/runs/41557808902), source `b6cc917ae1bfe8050480592700e70d288fc358ab`. Demo passwords were made for the run and masked; the receipts hold statuses and hashes only.

| Task | Result | Evidence |
|---|---|---|
| 008 T030b seeded auth | **Done.** `aligned=True`; both demo accounts exist with the expected role and password | `seed_auth` in [staging-design-walkthrough-2026-11-03.json](receipts/staging-design-walkthrough-2026-11-03.json), `seed_auth_sha256` `716598372842a92762c3ef251227db15cadda0c583accc02953e976b3778fffa` |
| 008 T040b Design Engine walkthrough | **Done.** `WALKTHROUGH PASS`: health_ready 200, login_user 200, login_admin 200, preview 200, grant_credits 201, export_debit 201, fulfillment, download_token 200, download_pack 200; flags read from the server; `production_payments_enabled: false` | `receipt_sha256` `27de665e287475ec5d9885ab54e7458708fe4e05bd1bd6c3c1ca85327f1cf736` |
| 006 T060b decision-resolution on staging | **Fail-closed path shown; stays open.** Upload 201 with one accepted asset; its evidence id found in candidates; two `decision-resolution` calls with one key both 409 `DECISION_INTELLIGENCE_DISABLED` | [staging-t060b-2026-11-03.json](receipts/staging-t060b-2026-11-03.json), `receipt_sha256` `112cb3bc13e47a7c5cccd4e7889475df3ac666feba1d098e114a2411a5d5f2b0` |

008 T050b (pin the readiness docs) now has its walkthrough receipt but still waits on 007 T060b. 006 T060b's provider path needs a decision provider enabled on staging, which needs the signed 007 evaluation receipt (T083).

Side effects on the staging branch only: demo users re-seeded (new passwords, not kept), the demo rack's runs recreated, a credit grant and export debit, one design pack in the staging R2 bucket, one generated test image and its evidence record (90-day retention).
