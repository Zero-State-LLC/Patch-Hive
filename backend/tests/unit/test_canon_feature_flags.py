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


def test_deprecated_referral_flag_is_accepted_ignored_and_warned(monkeypatch) -> None:
    import sys

    # Acceptance tests reload core.config; use the live module and its own Settings class.
    config = sys.modules["core.config"]
    Settings = config.Settings

    monkeypatch.delenv("ENABLE_REFERRALS", raising=False)
    monkeypatch.setenv("ENABLE_LEGACY_REFERRALS", "true")
    monkeypatch.setattr(config, "_warned_legacy_referrals", False)
    import logging

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    # Attach directly: other tests may reconfigure logging and disable propagation.
    log = config.logger
    handler = _Capture(level=logging.WARNING)
    monkeypatch.setattr(log, "disabled", False)
    log.addHandler(handler)
    try:
        settings = Settings(_env_file=None)
        Settings(_env_file=None)
    finally:
        log.removeHandler(handler)
    assert settings.enable_referrals is False
    warnings = [r for r in records if "ENABLE_REFERRALS" in r.getMessage()]
    assert len(warnings) == 1


def test_dotenv_with_deprecated_referral_flag_loads(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_LEGACY_REFERRALS", raising=False)
    monkeypatch.delenv("ENABLE_REFERRALS", raising=False)
    for value in ("false", "true"):
        env = tmp_path / ".env"
        env.write_text(f"ENABLE_LEGACY_REFERRALS={value}\n")
        settings = Settings(_env_file=str(env))
        assert settings.enable_referrals is False
