"""Startup refusals for settings that must never reach production yet."""

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
