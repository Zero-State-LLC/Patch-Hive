# Security model

## Trust boundaries

- Uploaded images and detection-provider output are untrusted.
- Image ingestion checks byte limits, decoded signature/MIME agreement, dimensions and pixel count; runs a scanner adapter before and after decoding; applies EXIF orientation; resizes; re-encodes to JPEG; and strips metadata.
- Local structural quality gates (`assess_local_image_quality`) reject undersized post-normalize images before provider handoff.
- Provider records pass strict Pydantic validation and cannot claim confirmed status (`USER_CONFIRMED` / `EpistemicStatus.confirmed`).
- Vision adapters are provider-neutral (`VisionEvidenceProvider`); CI uses mock/fixture providers only — no live paid model calls in tests.
- OCR/image-embedded text and filenames are untrusted (prompt-injection surface); never execute or elevate them to inventory truth.
- JWT verification uses PyJWT; the vulnerable `python-jose`/`ecdsa` stack was removed.
- Canonical admin events, credit entries in every ledger, referral rows and subscription period grants are append-only, enforced by Postgres triggers. A referral code changes only while it's empty or as its account is deleted.
- Stripe-style webhooks use constant-time HMAC comparison, timestamp tolerance, unique event IDs, replay-conflict detection, and a livemode rejection gate.
- Errors at canonical boundaries use stable codes without stack traces or provider payloads.

## Image privacy

User photographs may reveal home interiors, equipment, serial numbers, people, location EXIF, screens, or documents.

- Prefer re-encoded JPEG without EXIF for stored evidence bytes.
- Bind derived evidence to content hashes; do not expose raw storage paths.
- Do not send images to third-party providers without an explicit retention policy and user consent model (product policy; not activated in this repository by default).
- Support deletion of source images while retaining legally required audit and derived-artifact lineage where applicable.
- Retention and deletion runbooks: see OPERATIONS + product privacy policy (staging-gated).

## Supply chain

Python and frontend direct dependencies are exact-version pinned. CI runs `pip-audit`, `npm audit`, Bandit at medium/high severity, a secret scan, and CycloneDX SBOM generation. Lockfile changes require review.

### Temporary React Router advisory exception

The frontend is pinned to `react-router-dom@7.18.1`, the newest version published to npm as of
2026-07-28. The advisory declares `8.3.0` as the first fixed version, but that version is not
available in the npm registry. `npm audit` reports GHSA-qwww-vcr4-c8h2 against experimental
React Server Components action handling. PatchHive uses the client-only `BrowserRouter` API,
does not enable RSC mode, and exposes no React Router server actions, so the vulnerable path is
not reachable. CI runs `npm run audit`, which permits only this exact advisory and fails for every
new or changed finding. Remove the exception as soon as a fixed upstream release is published.

## Deployment requirements

- Replace `SECRET_KEY` with a high-entropy secret supplied by the platform.
- Restrict CORS origins and database networking.
- Use a production malware-scanning implementation behind `ImageScanner`.
- Use scoped, expiring object-storage URLs; never expose raw storage paths.
- Keep `STRIPE_TEST_MODE=true` and `ALLOW_PRODUCTION_PAYMENTS=false` until a separate payment activation review.
