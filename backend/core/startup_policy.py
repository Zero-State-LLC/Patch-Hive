"""Startup refusals for settings that are unsafe in the environment they start in."""

from __future__ import annotations

from typing import Any

# Decision providers write proposals that people confirm into canon. They are enabled
# only in staging, after an approved, receipt-bound evaluation (specs 005, 007); nothing
# yet gates them in production, so production refuses to start with any of them on.
DECISION_FLAGS = ("enable_decision_intelligence", "enable_clef_provider")


def validate_decision_startup_policy(app_settings: Any) -> None:
    env = str(getattr(app_settings, "environment", "development")).strip().lower()
    if env not in {"production", "prod"}:
        return
    on = [name for name in DECISION_FLAGS if bool(getattr(app_settings, name, False))]
    provider = str(getattr(app_settings, "decision_provider", "disabled") or "disabled").lower()
    if provider != "disabled":
        on.append(f"decision_provider={provider}")
    if on:
        raise RuntimeError(
            "refusing to start: decision providers are not enabled in production ("
            + ", ".join(on)
            + "); enable them in staging through the spec 007 receipt"
        )


def validate_stripe_mode_startup_policy(app_settings: Any) -> None:
    """Refuse STRIPE_TEST_MODE=false outside production (spec 004 FR-013, research R3).

    Live money belongs only to production, after the payment activation review
    (docs/SECURITY.md). The production rules live in ``validate_payment_startup_policy``
    (canon/routes.py); this covers every other environment, staging included.
    """
    env = str(getattr(app_settings, "environment", "development")).strip().lower()
    if env == "production":
        return
    if not bool(getattr(app_settings, "stripe_test_mode", True)):
        raise RuntimeError(
            f"refusing to start: STRIPE_TEST_MODE=false is allowed only in production "
            f"(ENVIRONMENT={env or 'unset'}); set STRIPE_TEST_MODE=true"
        )
