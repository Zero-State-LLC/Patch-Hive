"""What the signed-in user can buy and what they hold (spec 004 P1, P2, P5, T001 D8b).

Reads only. An offer appears only when its checkout gate passes, so with the flags off, the
default, there is nothing to buy. Tier prices live on the provider's Price objects and are not
ratified (OQ-1), so a plan offer says what it gives, and the provider's page shows the price.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from canon.checkout import MAX_CREDITS_PER_CHECKOUT, CheckoutUnavailableError, checkout_gate
from canon.entitlements import current_unlimited_grant
from canon.exports import _fair_use_exports
from canon.subscriptions import (
    CANCELABLE_STATUSES,
    SUBSCRIPTION_FLAG,
    SUBSCRIPTION_TIERS,
    _live_subscription,
    plan_for_tier,
    price_id_for_tier,
)
from canon.webhook_events import UnresolvedEventError


def _open(app_settings: Any, flag: str) -> bool:
    try:
        checkout_gate(app_settings, flag=flag)
    except CheckoutUnavailableError:
        return False
    return True


def _plan(app_settings: Any, tier: str) -> dict[str, Any] | None:
    try:
        plan = plan_for_tier(app_settings, tier)
    except UnresolvedEventError:
        return None
    return {
        "tier": plan.tier,
        "credits_per_period": plan.credits,
        "unlimited": plan.unlimited,
        "fair_use_exports_per_period": plan.fair_use_export_cap,
    }


def commerce_status(
    session: Session, *, user_id: int, app_settings: Any, now: datetime | None = None
) -> dict[str, Any]:
    subscriptions_open = _open(app_settings, SUBSCRIPTION_FLAG)
    live = _live_subscription(session, user_id)

    credit_offer = None
    if _open(app_settings, "enable_credit_checkout"):
        credit_offer = {
            "price_cents": app_settings.credit_price_cents,
            "minimum_charge_cents": app_settings.credit_minimum_charge_cents,
            "currency": app_settings.credit_currency,
            "max_credits": MAX_CREDITS_PER_CHECKOUT,
        }

    plan_offers = []
    if subscriptions_open and live is None:
        priced = [tier for tier in SUBSCRIPTION_TIERS if price_id_for_tier(app_settings, tier)]
        plan_offers = [plan for plan in (_plan(app_settings, tier) for tier in priced) if plan]

    subscription = None
    if live is not None:
        subscription = {
            "plan": _plan(app_settings, live.tier),
            "status": live.status,
            "cancel_at_period_end": bool(live.cancel_at_period_end),
            "current_period_end": live.current_period_end,
            "can_cancel": subscriptions_open
            and live.status in CANCELABLE_STATUSES
            and not live.cancel_at_period_end,
        }

    allowance = None
    grant = current_unlimited_grant(session, user_id, now or datetime.now(timezone.utc))
    if grant is not None:
        allowance = {
            "exports_used": _fair_use_exports(session, grant.id),
            "export_cap": int(grant.fair_use_export_cap or 0),
            "period_end": grant.period_end,
        }

    return {
        "test_mode": bool(app_settings.stripe_test_mode),
        "credit_offer": credit_offer,
        "plan_offers": plan_offers,
        "subscription": subscription,
        "allowance": allowance,
    }
