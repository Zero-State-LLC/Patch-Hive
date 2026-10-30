"""Canonical scope defaults must not expose historical product surfaces."""

from core.config import Settings


def test_historical_features_are_disabled_by_default(monkeypatch) -> None:
    for name in (
        "ENABLE_LEGACY_SOCIAL",
        "ENABLE_LEGACY_PUBLISHING",
        "ENABLE_LEGACY_LEADERBOARDS",
        "ENABLE_REFERRALS",
        "ENABLE_LEGACY_PATCHBOOK_DEBIT",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.enable_legacy_social is False
    assert settings.enable_legacy_publishing is False
    assert settings.enable_legacy_leaderboards is False
    assert settings.enable_referrals is False
    assert settings.enable_legacy_patchbook_debit is False
    assert settings.stripe_test_mode is True
    assert settings.allow_production_payments is False
