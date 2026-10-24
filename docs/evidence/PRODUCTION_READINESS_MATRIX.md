# Production readiness matrix (evidence-bound)

```yaml
assessment:
  source_sha: d0bbcd072a9026538ce7403bed73337d6a6a4676  # #148; re-pin after F2 merge
  branch: main
  environment: local developer host + CI + local Docker staging (named host NOT_PERFORMED)
  date: "2026-07-26"
  authority_decision: NOT_GRANTED
  production_deployed: false
  production_payments_enabled: false
  full_narrative: PRODUCTION_READINESS_ASSESSMENT_2026-07-21.md
  delta: PRODUCTION_READINESS_DELTA_2026-07-26.md

areas:
  product_scope: PARTIAL  # canon MVP + Design Engine (flags off); dual-path F2 done, F4/F5 residual
  architecture: PARTIAL  # modular monolith; inventory write still /api/racks; read alias /api/canon/rigs
  data_model: PARTIAL  # canon + VSI + design engine + device registry + registry slugs
  visual_ingestion: PARTIAL  # secure prep + mock provider; no live model
  module_classification: PARTIAL  # gallery + mock candidates; never self-confirm
  confirmation_workflow: PARTIAL  # multi-photo fusion UI; user confirm only
  device_registry: PARTIAL  # hierarchy + explorer; completeness metrics incomplete
  patch_compiler: PARTIAL  # deterministic compiler + native bridge IDs
  patch_validation: PASS  # unit coverage for graph + inventory gates
  patch_book_compiler: PARTIAL  # Design Engine on main; publication profile flag off
  design_engine: PARTIAL  # default flags false; staging walkthrough PASS (#147)
  exports: PARTIAL  # canon exports + pack download; fulfillment flag gated
  frontend: PARTIAL  # MVP routes + PDB explorer + type-safety #141; full page upgrade #96 open
  accessibility: PARTIAL  # graph pair + preflight; WCAG protocol not fully evidenced
  security: PARTIAL  # CI security workflow; prod-only npm high audit; no prod threat sign-off
  privacy: PARTIAL  # EXIF strip; retention policy incomplete
  testing: PASS  # unit/api/CI/e2e + acceptance-tests.yml + unified scripts/test/run
  migrations: PASS  # single head through 20260726_module_registry_slugs; deploy uses alembic
  deployment: NOT_COMPUTABLE  # no production access; entrypoint fixed for staging path
  backup_and_restore: PARTIAL  # local compose pg_dump/restore drill PASS (#145); durable env NOT_PERFORMED
  observability: FAIL  # no production SLOs/dashboards evidenced; /health/ready only
  billing: PARTIAL  # test-mode only; live activation forbidden
  support: FAIL  # no support channel evidence
  release_governance: PARTIAL  # VERSIONING + alpha tag; no RC freeze

known_exclusions:
  - audio_processing
  - hardware_control
  - live_stripe
  - community_social_default_on

summary:
  pass:
    - migrations_chain_discipline
    - patch_validation_unit_gates
    - payment_fail_closed_defaults
    - alembic_deploy_entrypoint
    - automated_acceptance_ci
  partial:
    - product_scope
    - design_engine
    - visual_ingestion
    - confirmation
    - exports
    - frontend
    - security_privacy
    - device_registry
    - local_compose_backup_restore
  fail:
    - observability
    - support
  not_computable:
    - deployment_named_host
    - durable_env_backup_restore
    - vision_accuracy_metrics
    - multi_tenant_load
  out_of_scope:
    - audio_dsp
    - midi_cv_activation
```

**Do not treat any percentage estimate as readiness.** This matrix supersedes informal readiness percentages in historical notes.

**After merging ops/beta-staging or any release candidate:** update `source_sha`, re-run gates, and append a dated row or new assessment file under `docs/evidence/`.

## Spec 008 walkthrough pin (T050)

```yaml
spec_008_design_walkthrough:
  walkthrough_source_sha: PENDING_OPERATOR_WALKTHROUGH
  walkthrough_receipt_sha256: PENDING_OPERATOR_WALKTHROUGH
  enablement_receipt_007_sha256: PENDING_OPERATOR_WALKTHROUGH
  unresolved_p0: PENDING_OPERATOR_WALKTHROUGH
  production_payments_enabled: false
  state: RECEIPT_PENDING  # BETA_ELIGIBLE only after core.ops.f5_cutover operator_pin accepts
```

The operator replaces each `PENDING_OPERATOR_WALKTHROUGH` value with the exact
values from the staging receipt written by
`scripts/staging/design_engine_walkthrough.py`. The pin validator
(`core.ops.f5_cutover.pin_readiness_docs`) rejects this file until it contains
the receipt's exact `source_commit_sha`. See
`specs/008-dual-path-f5-design-receipts/OPERATOR_NOTES.md`.
