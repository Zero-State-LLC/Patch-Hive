"""SQLAlchemy persistence adapter for canonical immutable artifacts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    false,
)

from core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RigRevisionRecord(Base):
    __tablename__ = "rig_revisions"

    id = Column(String(64), primary_key=True)
    rig_id = Column(
        Integer, ForeignKey("racks.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    previous_revision_id = Column(
        String(64), ForeignKey("rig_revisions.id", ondelete="RESTRICT"), nullable=True
    )
    schema_version = Column(String(64), nullable=False)
    canonical_rig = Column(JSON, nullable=False)
    canonical_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class RigMetricsPacketRecord(Base):
    """One metrics packet per rig revision (spec 001 FR-027, T031). Append-only."""

    __tablename__ = "rig_metrics_packets"

    id = Column(String(64), primary_key=True)
    rig_revision_id = Column(
        String(64),
        ForeignKey("rig_revisions.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    packet = Column(JSON, nullable=False)
    canonical_hash = Column(String(64), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class GenerationRunRecord(Base):
    __tablename__ = "generation_runs"

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rig_revision_id = Column(
        String(64), ForeignKey("rig_revisions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    schema_version = Column(String(64), nullable=False)
    generator_version = Column(String(64), nullable=False)
    generation_seed = Column(Integer, nullable=False)
    normalized_input_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PatchLibraryRecord(Base):
    __tablename__ = "patch_libraries"

    id = Column(String(64), primary_key=True)
    run_id = Column(
        String(64),
        ForeignKey("generation_runs.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    artifact_manifest_hash = Column(String(64), nullable=False)
    canonical_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class GeneratedPatchRecord(Base):
    __tablename__ = "generated_patches"
    __table_args__ = (UniqueConstraint("patch_library_id", "position"),)

    id = Column(String(64), primary_key=True)
    patch_library_id = Column(
        String(64),
        ForeignKey("patch_libraries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    position = Column(Integer, nullable=False)
    name = Column(String(200), nullable=False)
    patch_graph = Column(JSON, nullable=False)
    patch_plan = Column(JSON, nullable=False)
    validation_report = Column(JSON, nullable=False)
    variations = Column(JSON, nullable=False, default=list)
    canonical_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class UserPatchAnnotationRecord(Base):
    __tablename__ = "user_patch_annotations"
    __table_args__ = (UniqueConstraint("user_id", "patch_id"),)

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patch_id = Column(
        String(64),
        ForeignKey("generated_patches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notes = Column(Text, nullable=True)
    favorite = Column(Boolean, nullable=False, default=False)
    tried = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ModuleRevisionRecord(Base):
    __tablename__ = "module_revisions"

    id = Column(String(64), primary_key=True)
    module_id = Column(
        Integer, ForeignKey("modules.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    previous_revision_id = Column(
        String(64), ForeignKey("module_revisions.id", ondelete="RESTRICT"), nullable=True
    )
    schema_version = Column(String(64), nullable=False)
    spec = Column(JSON, nullable=False)
    canonical_hash = Column(String(64), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class StageReceiptRecord(Base):
    __tablename__ = "stage_receipts"

    id = Column(String(64), primary_key=True)
    run_id = Column(
        String(64),
        ForeignKey("generation_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    stage = Column(String(100), nullable=False)
    operation = Column(String(150), nullable=False)
    operation_version = Column(String(64), nullable=False)
    determinism_class = Column(String(40), nullable=False)
    input_hash = Column(String(64), nullable=False)
    output_hash = Column(String(64), nullable=False)
    receipt = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ArtifactManifestRecord(Base):
    __tablename__ = "artifact_manifests"

    id = Column(String(64), primary_key=True)
    run_id = Column(
        String(64),
        ForeignKey("generation_runs.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    manifest = Column(JSON, nullable=False)
    canonical_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class GenerationJobRecord(Base):
    __tablename__ = "generation_jobs"

    id = Column(String(64), primary_key=True)
    request_id = Column(String(64), nullable=False, unique=True)
    run_id = Column(
        String(64),
        ForeignKey("generation_runs.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    status = Column(String(20), nullable=False, default="queued")
    attempts = Column(Integer, nullable=False, default=0)
    error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    __table_args__ = (CheckConstraint("attempts >= 0", name="ck_generation_jobs_attempts"),)


class UserStyleRecipeRecord(Base):
    """Mutable user-owned PatchBook style recipes (Design Engine library).

    Not append-only — users may rename/update/delete their own recipes.
    Export seals a snapshot of the request recipe JSON at debit time.
    """

    __tablename__ = "user_style_recipes"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_style_recipes_name"),)

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = Column(String(120), nullable=False)
    notes = Column(Text, nullable=True)
    recipe_json = Column(JSON, nullable=False)
    recipe_hash = Column(String(64), nullable=False, index=True)
    is_shared = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


# An export covered by a STUDIO period grant has no debit and costs nothing (T050).
EXPORT_GRANT_SHAPE = (
    "subscription_grant_id IS NULL OR (credit_cost = 0 AND ledger_entry_id IS NULL)"
)


class CanonicalExportRecord(Base):
    __tablename__ = "canonical_exports"

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_run_id = Column(
        String(64),
        ForeignKey("generation_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_rig_revision_id = Column(
        String(64), ForeignKey("rig_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    artifact_manifest_hash = Column(String(64), nullable=False)
    export_version = Column(String(64), nullable=False)
    license = Column(String(100), nullable=False)
    credit_cost = Column(Integer, nullable=False)
    ledger_entry_id = Column(String(64), nullable=True, unique=True)
    # Unique per user (UniqueConstraint below): one user's key never finds another's export.
    idempotency_key = Column(String(128), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    # Design Engine seal + fulfillment (nullable for legacy rows; KD-13)
    style_recipe_hash = Column(String(64), nullable=True)
    request_style_recipe_json = Column(JSON, nullable=True)
    resolved_style_recipe_json = Column(JSON, nullable=True)
    resolved_tier = Column(String(20), nullable=True)
    design_engine_version = Column(String(64), nullable=True)
    book_profile = Column(String(40), nullable=True)
    library_content_hash = Column(String(64), nullable=True)
    composition_hash = Column(String(64), nullable=True)
    pack_manifest_hash = Column(String(64), nullable=True)
    artifact_uri = Column(String(512), nullable=True)
    fulfill_attempts = Column(Integer, nullable=False, default=0)
    running_started_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(100), nullable=True)
    # Optional pointer to library row used at request time (audit only; not re-loaded for render)
    style_recipe_id = Column(
        String(64),
        ForeignKey("user_style_recipes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Spec 004 T050 (FR-004, OQ-8): the STUDIO period grant that covered this export in
    # place of a debit. Such an export costs no credits and counts against the grant's
    # ``fair_use_export_cap``.
    subscription_grant_id = Column(
        String(64),
        ForeignKey("subscription_period_grants.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    __table_args__ = (
        CheckConstraint("credit_cost >= 0", name="ck_canonical_exports_cost"),
        CheckConstraint(EXPORT_GRANT_SHAPE, name="ck_canonical_exports_grant_shape"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_canonical_exports_user_idempotency"),
    )


class CanonicalCreditLedgerEntryRecord(Base):
    __tablename__ = "canonical_credit_ledger"

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    delta = Column(Integer, nullable=False)
    entry_type = Column(String(20), nullable=False)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    export_id = Column(
        String(64),
        ForeignKey("canonical_exports.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class StripeEventRecordModel(Base):
    __tablename__ = "stripe_event_records"

    stripe_event_id = Column(String(128), primary_key=True)
    event_type = Column(String(100), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    livemode = Column(Boolean, nullable=False)
    # received (inside the intake transaction only), then processed, duplicate,
    # unresolved or ignored (canon.webhook_events, spec 004 FR-014).
    status = Column(String(20), nullable=False, default="received")
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    reason_code = Column(String(64), nullable=True)
    # The event's ``data.object.id`` (for a checkout event, the Checkout Session id),
    # stored at intake so an operator resolve can retrieve the object (T048b).
    object_id = Column(String(255), nullable=True, index=True)


class ProviderCustomerRecord(Base):
    """Spec 004 FR-020: each user maps to at most one payment-provider customer."""

    __tablename__ = "provider_customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    provider_customer_id = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


# Machine B states as stored on a payment record: ``open`` and ``pending`` (completed,
# payment not settled) are CheckoutOpen; ``credited`` is Credited; ``failed`` and
# ``abandoned`` are Abandoned.
PAYMENT_STATUSES = ("open", "pending", "credited", "failed", "abandoned")


class ProviderPaymentRecord(Base):
    """Spec 004 Machine B: one record per one-time credit checkout session.

    The server writes it when it creates the session, so the user, credit count and
    amount come from here, not from event metadata. ``provider_payment_id`` (the payment
    intent) is unique and set once the provider reports it (FR-012).

    Refunds (OQ-2, T053): ``refunded_cents`` is the highest cumulative refunded amount
    applied; ``refund_reversed_credits`` were taken back with canonical ``refund``
    entries and ``refund_unrecovered_credits`` were already spent and went to an
    operator. Their sum is always the credits proportional to ``refunded_cents``.
    """

    __tablename__ = "provider_payments"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'pending', 'credited', 'failed', 'abandoned', "
            "'partially_refunded', 'refunded')",
            name="ck_provider_payments_status",
        ),
        CheckConstraint("credits > 0", name="ck_provider_payments_credits_positive"),
        CheckConstraint("amount_cents > 0", name="ck_provider_payments_amount_positive"),
        CheckConstraint(
            "refunded_cents >= 0 AND refunded_cents <= amount_cents",
            name="ck_provider_payments_refunded_cents",
        ),
        CheckConstraint(
            "refund_reversed_credits >= 0 AND refund_unrecovered_credits >= 0 "
            "AND refund_reversed_credits + refund_unrecovered_credits <= credits",
            name="ck_provider_payments_refund_credits",
        ),
    )

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    checkout_session_id = Column(String(255), nullable=False, unique=True)
    provider_payment_id = Column(String(255), nullable=True, unique=True)
    credits = Column(Integer, nullable=False)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    credited_at = Column(DateTime(timezone=True), nullable=True)
    refunded_cents = Column(Integer, nullable=False, default=0, server_default="0")
    refund_reversed_credits = Column(Integer, nullable=False, default=0, server_default="0")
    refund_unrecovered_credits = Column(Integer, nullable=False, default=0, server_default="0")


# Spec 004 Machine C (T049). Tiers a subscription can carry, and the provider statuses
# stored verbatim (OQ-4 ``A_stripe_mapping`` maps them to entitlements in T050).
SUBSCRIPTION_TIERS = ("core", "pro", "studio")
SUBSCRIPTION_STATUSES = (
    "incomplete",
    "incomplete_expired",
    "trialing",
    "active",
    "past_due",
    "canceled",
    "unpaid",
    "paused",
)
_TIER_CHECK = "tier IN ('core', 'pro', 'studio')"


class ProviderSubscriptionRecord(Base):
    """Spec 004 Machine C (FR-015): one record per provider subscription.

    ``customer.subscription.*`` events keep the tier (from the provider price, OQ-7),
    the provider status, the current period and ``cancel_at_period_end`` in sync; they
    never grant. ``last_event_created`` is the provider ``created`` time of the newest
    event applied, so an older event delivered late cannot roll the record back.
    ``purchase_recorded_at`` is set when the first paid invoice went through
    ``record_purchase`` (OQ-3 ``A_both``).
    """

    __tablename__ = "provider_subscriptions"
    __table_args__ = (
        CheckConstraint(_TIER_CHECK, name="ck_provider_subscriptions_tier"),
        CheckConstraint(
            "status IN ("
            + ", ".join(f"'{status}'" for status in SUBSCRIPTION_STATUSES)
            + ")",
            name="ck_provider_subscriptions_status",
        ),
        CheckConstraint(
            "current_period_end > current_period_start",
            name="ck_provider_subscriptions_period",
        ),
    )

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider_subscription_id = Column(String(255), nullable=False, unique=True)
    provider_customer_id = Column(String(255), nullable=False)
    price_id = Column(String(255), nullable=False)
    tier = Column(String(16), nullable=False)
    status = Column(String(32), nullable=False)
    current_period_start = Column(DateTime(timezone=True), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False, server_default=false())
    last_event_created = Column(BigInteger, nullable=True)
    purchase_recorded_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


SUBSCRIPTION_CHECKOUT_STATUSES = ("open", "completed", "expired")


class SubscriptionCheckoutRecord(Base):
    """Spec 004 Machine C ``CheckoutOpen``: the user's outstanding subscription checkout.

    It reserves checkout per user, so a second request while one is open reuses that
    session instead of opening another subscription (T049). ``expires_at`` is the
    provider session's own expiry; past it the session can no longer be paid.
    ``completed`` carries the subscription the session created, which blocks a new
    checkout until that subscription is terminal.
    """

    __tablename__ = "subscription_checkouts"
    __table_args__ = (
        CheckConstraint(_TIER_CHECK, name="ck_subscription_checkouts_tier"),
        CheckConstraint(
            "status IN ('open', 'completed', 'expired')",
            name="ck_subscription_checkouts_status",
        ),
    )

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    checkout_session_id = Column(String(255), nullable=False, unique=True)
    checkout_url = Column(Text, nullable=False)
    tier = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False, default="open")
    provider_subscription_id = Column(String(255), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


SUBSCRIPTION_GRANT_SHAPE = (
    "(unlimited AND credits = 0 AND fair_use_export_cap >= 1 AND ledger_entry_id IS NULL) "
    "OR (NOT unlimited AND credits > 0 AND fair_use_export_cap IS NULL "
    "AND ledger_entry_id IS NOT NULL)"
)


class SubscriptionPeriodGrantRecord(Base):
    """Spec 004 FR-016 / SC-005: exactly one grant per subscription billing period.

    Written on ``invoice.paid`` only, keyed ``subscription-period:<subscription_id>:
    <period_start>``. CORE and PRO carry ``credits`` and the canonical ``grant`` entry
    with the same key. STUDIO carries no credits: ``unlimited`` is the explicit
    entitlement (FR-004, never a numeric sentinel) and ``fair_use_export_cap`` is the
    owner's fair-use cap for the period, copied from the setting when granted (OQ-8).
    """

    __tablename__ = "subscription_period_grants"
    __table_args__ = (
        UniqueConstraint(
            "subscription_record_id",
            "period_start",
            name="uq_subscription_period_grants_period",
        ),
        CheckConstraint(_TIER_CHECK, name="ck_subscription_period_grants_tier"),
        CheckConstraint(SUBSCRIPTION_GRANT_SHAPE, name="ck_subscription_period_grants_shape"),
        CheckConstraint(
            "period_end > period_start", name="ck_subscription_period_grants_period"
        ),
    )

    id = Column(String(64), primary_key=True)
    subscription_record_id = Column(
        String(64),
        ForeignKey("provider_subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    grant_key = Column(String(128), nullable=False, unique=True)
    provider_invoice_id = Column(String(255), nullable=False, unique=True)
    tier = Column(String(16), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    credits = Column(Integer, nullable=False)
    unlimited = Column(Boolean, nullable=False)
    fair_use_export_cap = Column(Integer, nullable=True)
    ledger_entry_id = Column(
        String(64),
        ForeignKey("canonical_credit_ledger.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class CanonicalAdminAuditEventRecord(Base):
    __tablename__ = "canonical_admin_audit_events"

    id = Column(String(64), primary_key=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    actor_role = Column(String(30), nullable=False)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(100), nullable=False)
    target_id = Column(String(100), nullable=False)
    before_hash = Column(String(64), nullable=True)
    after_hash = Column(String(64), nullable=True)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class PatchUserOverlayRecord(Base):
    """Mutable personal overlay for a patch (notes/favorite/tried).

    ``patch_ref`` is a dual-path key: ``legacy-patch-{int}`` or a canon generated
    patch id. No FK to generation tables so dual-path patches remain annotatable.
    """

    __tablename__ = "patch_user_overlays"
    __table_args__ = (UniqueConstraint("user_id", "patch_ref", name="uq_overlay_user_patch_ref"),)

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    patch_ref = Column(String(64), nullable=False, index=True)
    notes = Column(Text, nullable=True)
    favorite = Column(Boolean, nullable=False, default=False)
    tried = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class SystemInventoryRevisionRecord(Base):
    """Persisted immutable system inventory revision (VSI WP-06)."""

    __tablename__ = "system_inventory_revisions"

    id = Column(String(64), primary_key=True)
    system_id = Column(String(128), nullable=False, index=True)
    rack_id = Column(
        Integer, ForeignKey("racks.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    previous_revision_id = Column(
        String(64),
        ForeignKey("system_inventory_revisions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    schema_version = Column(String(64), nullable=False, default="patchhive.inventory.v1")
    items = Column(JSON, nullable=False, default=list)
    unresolved_candidate_ids = Column(JSON, nullable=False, default=list)
    canonical_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ImageAssetRecord(Base):
    """Secure image evidence asset with retention policy."""

    __tablename__ = "image_assets"

    id = Column(String(64), primary_key=True)
    rack_id = Column(
        Integer, ForeignKey("racks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    content_sha256 = Column(String(64), nullable=False, index=True)
    media_type = Column(String(64), nullable=False, default="image/jpeg")
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    byte_length = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False)
    retention_days = Column(Integer, nullable=False, default=30)
    retention_expires_at = Column(DateTime(timezone=True), nullable=False)
    consent_provider_processing = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ClassificationEvidenceRecord(Base):
    """Append-only classification evidence bound to an image asset."""

    __tablename__ = "classification_evidence_records"

    id = Column(String(64), primary_key=True)
    image_asset_id = Column(
        String(64),
        ForeignKey("image_assets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    inventory_revision_id = Column(
        String(64),
        ForeignKey("system_inventory_revisions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    evidence_packet = Column(JSON, nullable=False)
    provider = Column(String(64), nullable=False)
    pipeline_version = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="INFERRED")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


def _reject_mutation(_mapper, _connection, target) -> None:
    raise ValueError(f"{type(target).__name__} is append-only and cannot be mutated")


IMMUTABLE_RECORDS = (
    RigRevisionRecord,
    RigMetricsPacketRecord,
    GenerationRunRecord,
    PatchLibraryRecord,
    GeneratedPatchRecord,
    ModuleRevisionRecord,
    StageReceiptRecord,
    ArtifactManifestRecord,
    CanonicalCreditLedgerEntryRecord,
    CanonicalAdminAuditEventRecord,
    SubscriptionPeriodGrantRecord,
    SystemInventoryRevisionRecord,
    ClassificationEvidenceRecord,
)

for _record in IMMUTABLE_RECORDS:
    event.listen(_record, "before_update", _reject_mutation)
    event.listen(_record, "before_delete", _reject_mutation)
