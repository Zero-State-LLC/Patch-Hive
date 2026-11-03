"""Server-side tier / Design Engine entitlements (KD-5, KD-18, spec 004 T050).

No client-supplied tier. A user's tier comes from their provider subscription record
(Machine C, ``canon/subscriptions.py``) when its provider status is one OQ-4
``A_stripe_mapping`` counts as entitled: ``active`` and ``trialing`` get the paid tier,
and ``past_due`` keeps it while the provider retries. A user whose subscriptions are all in
another status (``incomplete``, ``incomplete_expired``, ``unpaid``, ``paused``,
``canceled``) gets FREE, as OQ-4 maps them. A user with no subscription at all gets the
``design_engine_default_tier`` setting.

The stored tier is the one subscription sync took from the provider price (OQ-7
``A_next_period_no_proration``); what the user can spend follows the period grant, so a
tier change brings its credits or unlimited entitlement with the next paid period and
nothing is prorated here.

Spending (FR-004, OQ-8 ``A_flag_with_fair_use``): ``current_unlimited_grant`` finds the
user's STUDIO period grant covering a moment. An export covered by it takes no credits
and counts against the grant's ``fair_use_export_cap`` instead (``canon/exports.py``).
CORE and PRO keep the credit ledger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from canon.models import ProviderSubscriptionRecord, SubscriptionPeriodGrantRecord
from core.config import settings
from export.patchbook.design.recipe import TemplateFamilyId

TierName = Literal["free", "core", "pro", "studio"]

# Family floor table from design §D
_FAMILY_TIER_FLOOR: dict[TemplateFamilyId, TierName] = {
    TemplateFamilyId.SIGNAL_MANUAL: "free",
    TemplateFamilyId.MODULAR_FIELD_NOTES: "free",
    TemplateFamilyId.CIRCUIT_ARCHIVE: "free",
    TemplateFamilyId.HIVE_SYSTEMS_ATLAS: "core",
    TemplateFamilyId.OPEN_STATE: "core",
    TemplateFamilyId.OSCILLOSCOPE_JOURNAL: "core",
    TemplateFamilyId.PATENT_FUTURE: "core",
    TemplateFamilyId.MUSEUM_OF_SIGNAL: "pro",
    TemplateFamilyId.PATCH_CARTOGRAPHY: "pro",
    TemplateFamilyId.SONIC_BRUTALISM: "pro",
    TemplateFamilyId.RITUAL_MACHINE: "studio",
    TemplateFamilyId.IMPOSSIBLE_INSTRUMENT: "studio",
}

_TIER_RANK: dict[TierName, int] = {"free": 0, "core": 1, "pro": 2, "studio": 3}


@dataclass(frozen=True)
class DesignEntitlements:
    tier: TierName
    design_engine_enabled: bool
    fulfillment_enabled: bool
    publication_enabled: bool
    allowed_families: frozenset[TemplateFamilyId]


# OQ-4 ``A_stripe_mapping``: provider statuses that keep the subscription's paid tier.
ENTITLED_STATUSES: frozenset[str] = frozenset({"active", "trialing", "past_due"})


def default_tier() -> TierName:
    """The ``design_engine_default_tier`` setting; ``core`` if it names no tier."""

    override = (settings.design_engine_default_tier or "core").lower().strip()
    if override not in _TIER_RANK:
        return "core"
    return override  # type: ignore[return-value]


def entitled_subscription(session: Session, user_id: int) -> ProviderSubscriptionRecord | None:
    """The user's newest subscription whose provider status is entitled (OQ-4)."""

    return (
        session.query(ProviderSubscriptionRecord)
        .filter(
            ProviderSubscriptionRecord.user_id == user_id,
            ProviderSubscriptionRecord.status.in_(ENTITLED_STATUSES),
        )
        .order_by(
            ProviderSubscriptionRecord.created_at.desc(), ProviderSubscriptionRecord.id.desc()
        )
        .first()
    )


def resolve_user_tier(session: Session, user_id: int) -> TierName:
    """Resolve the user's tier. Client input never decides it.

    The entitled subscription's tier; FREE if the user has subscriptions but none is
    entitled (OQ-4); the default-tier setting if the user never subscribed.
    """

    record = entitled_subscription(session, user_id)
    if record is not None and record.tier in _TIER_RANK:
        return record.tier  # type: ignore[return-value]
    lapsed = (
        session.query(ProviderSubscriptionRecord.id)
        .filter(ProviderSubscriptionRecord.user_id == user_id)
        .first()
    )
    if lapsed is not None:
        return "free"
    return default_tier()


def current_unlimited_grant(
    session: Session, user_id: int, at: datetime
) -> SubscriptionPeriodGrantRecord | None:
    """The STUDIO period grant that covers ``at`` for the user's entitled subscription.

    ``None`` when the user has no entitled subscription, or its grant for the period
    covering ``at`` is missing (the period's invoice is not paid yet, for example while
    ``past_due``) or is not unlimited. Then the export pays from the credit ledger.
    """

    record = entitled_subscription(session, user_id)
    if record is None:
        return None
    return (
        session.query(SubscriptionPeriodGrantRecord)
        .filter(
            SubscriptionPeriodGrantRecord.subscription_record_id == record.id,
            SubscriptionPeriodGrantRecord.unlimited.is_(True),
            SubscriptionPeriodGrantRecord.period_start <= at,
            SubscriptionPeriodGrantRecord.period_end > at,
        )
        .order_by(SubscriptionPeriodGrantRecord.period_start.desc())
        .first()
    )


def tier_allows_family(tier: TierName, family: TemplateFamilyId) -> bool:
    floor = _FAMILY_TIER_FLOOR.get(family, "studio")
    return _TIER_RANK[tier] >= _TIER_RANK[floor]


def allowed_families_for_tier(tier: TierName) -> frozenset[TemplateFamilyId]:
    return frozenset(f for f in TemplateFamilyId if tier_allows_family(tier, f))


def get_design_entitlements(session: Session, user_id: int) -> DesignEntitlements:
    tier = resolve_user_tier(session, user_id)
    return DesignEntitlements(
        tier=tier,
        design_engine_enabled=bool(settings.enable_patchbook_design_engine),
        fulfillment_enabled=bool(settings.enable_canon_export_fulfillment),
        publication_enabled=bool(settings.enable_patchbook_publication_profile),
        allowed_families=allowed_families_for_tier(tier),
    )
