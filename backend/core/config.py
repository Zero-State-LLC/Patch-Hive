"""
Core configuration for PatchHive backend.
Uses pydantic-settings for environment-based configuration.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from core.version import read_package_version

logger = logging.getLogger(__name__)
_warned_legacy_referrals = False


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "PatchHive"
    app_version: str = read_package_version()
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql://patchhive:***@localhost:5432/patchhive"
    database_echo: bool = False
    # Dev/sqlite escape hatch only. Deploy/staging must use alembic upgrade head.
    allow_create_all: bool = False

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    # Access tokens are short-lived and held in memory by the SPA; a rotating refresh
    # token in an HttpOnly cookie restores and renews sessions (community/sessions.py).
    access_token_expire_minutes: int = 15
    refresh_token_days: int = 30

    # CORS — accepts JSON list or comma-separated env (docker-compose style).
    # NoDecode: pydantic-settings otherwise JSON-parses list env before validators.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # Frontend
    frontend_base_url: str = "http://localhost:5173"

    # Canonical scope gates. Historical surfaces are off unless explicitly enabled.
    enable_legacy_social: bool = False
    enable_legacy_publishing: bool = False
    enable_legacy_leaderboards: bool = False
    enable_referrals: bool = False
    # Deprecated, ignored. Declared only so an existing .env that still names
    # ENABLE_LEGACY_REFERRALS loads instead of failing extra_forbidden. Nothing reads it.
    enable_legacy_referrals: bool = False

    # Decision Intelligence. Provider integration remains fail-closed by default.
    enable_decision_intelligence: bool = False
    decision_provider: str = "disabled"
    typesafe_api_key: str = ""
    jev_base_url: str = "https://api.typesafe.ai"
    jev_model: str = ""
    decision_auto_propose_at: float = 0.90
    decision_user_review_at: float = 0.65
    decision_probability_margin: float = 0.10
    # Spec 006 Clef (Cloudflare Workers AI) adapter. Feature flag DEFAULT OFF and fail-closed:
    # selecting decision_provider="clef" with the flag off makes every call return
    # CLEF_DISABLED without any network call. Credentials come from env only.
    enable_clef_provider: bool = False
    clef_model: str = "clef"
    cloudflare_account_id: str = ""
    cloudflare_ai_api_token: str = ""
    clef_base_url: str = "https://api.cloudflare.com/client/v4"
    clef_timeout_seconds: float = 10.0
    # NVIDIA vision provider (API catalog), beside Clef. DEFAULT OFF and fail-closed like
    # Clef: decision_provider="nvidia" with the flag off answers NVIDIA_DISABLED without
    # a network call. The key comes from env only (staging secret NVIDIA_API_KEY).
    enable_nvidia_provider: bool = False
    nvidia_api_key: str = ""
    nvidia_model: str = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_timeout_seconds: float = 20.0
    decision_policy_version: str = "decision-policy-v1"
    # Spec 005 T080: outside development a decision provider runs only with a signed
    # spec 007 enablement receipt and its signature, read from these JSON files.
    decision_enablement_receipt_path: str = ""
    decision_enablement_signature_path: str = ""
    # The one bounded routing target (spec 005 R6): the existing confirmation UI. Empty
    # means no target, so a failed provider or a policy ESCALATE ends UNRESOLVED. The
    # default is empty because nothing lists or reads ESCALATE records yet, so an
    # ESCALATE would be a silent dead end. Set it (for example "human_review") once a
    # review queue consumes ESCALATE.
    decision_routing_target: str = ""

    # Patch Engine
    patch_engine_version: str = "1.0.0"
    # Compatibility alias used by some call sites / older tests.
    generation_version: str = "1.0.0"
    max_patches_per_generation: int = 20
    default_generation_seed: int = 42
    patchbook_export_cost: int = 3
    # Legacy POST /api/export/runs/{id}/patchbook debit path (transitional).
    # MVP UI and acceptance use /api/canon/exports; set false to hard-disable debit.
    enable_legacy_patchbook_debit: bool = False
    # Legacy two-page patch book (POST /api/export/patchbook). Its pages break the spec
    # 002 one-page rule; the Design Engine is the book path. Off unless explicitly set.
    enable_legacy_patchbook_export: bool = False
    stripe_test_mode: bool = True
    allow_production_payments: bool = False
    # Empty defaults: development may derive local secrets; production policy enforces real ones.
    stripe_webhook_secret: str = ""
    download_token_secret: str = ""
    # Spec 004 Machine B (T046): one-time credit checkout. Off by default (FR-019); sales
    # stay deferred until counsel drafts terms (OQ-13). The secret key must be a test key
    # (sk_test_/rk_test_) unless production payments are activated (T051).
    enable_credit_checkout: bool = False
    stripe_secret_key: str = ""
    stripe_api_base: str = "https://api.stripe.com"
    # OQ-1, ratified provisionally 2026-11-01: $0.20 per credit, $5.00 minimum charge, USD.
    credit_price_cents: int = 20
    credit_minimum_charge_cents: int = 500
    credit_currency: str = "usd"

    # File Storage
    export_dir: str = "./exports"
    export_store_root: str = "./exports"
    waveform_dir: str = "./waveforms"
    # Durable copy of the files above (core/storage.py). "local" keeps today's behavior;
    # "s3" mirrors to an S3-compatible bucket such as Cloudflare R2 and fails closed if
    # any S3_* value is missing.
    storage_backend: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_region: str = "auto"
    s3_key_prefix: str = ""

    # PatchBook Design Engine (presentation layer; defaults off — no behavior change)
    enable_patchbook_design_engine: bool = False
    enable_canon_export_fulfillment: bool = False
    enable_inline_export_fulfillment: bool = False
    enable_patchbook_publication_profile: bool = False
    require_sealed_generated_patches: bool = False
    design_engine_default_tier: str = "core"
    export_fulfill_max_attempts: int = 5
    preview_rate_limit_per_minute: int = 30

    # ABX-Core / SEED
    abx_core_version: str = "1.3"
    enforce_seed_traceability: bool = True

    # Test mode
    test_mode: bool = False

    # Git tracking (optional, for provenance)
    git_commit: str = ""  # Set by environment or CI/CD

    @field_validator("decision_provider")
    @classmethod
    def _validate_decision_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"disabled", "jev", "clef", "nvidia"}:
            raise ValueError("decision_provider must be 'disabled', 'jev', 'clef', or 'nvidia'")
        return normalized

    @field_validator("nvidia_model")
    @classmethod
    def _validate_nvidia_model(cls, value: str) -> str:
        # Mirrors intelligence.nvidia_provider.NVIDIA_MODELS (a test keeps them equal);
        # importing it here would cycle through core.database.
        allowed = ("nvidia/nemotron-3.5-super-vl-120b-a12b", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning")
        normalized = value.strip()
        if normalized not in allowed:
            raise ValueError("nvidia_model must be one of " + ", ".join(allowed))
        return normalized

    @field_validator("clef_model")
    @classmethod
    def _validate_clef_model(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"clef", "clef-flash"}:
            raise ValueError("clef_model must be 'clef' or 'clef-flash'")
        return normalized

    @model_validator(mode="after")
    def _warn_deprecated_referral_flag(self) -> "Settings":
        global _warned_legacy_referrals
        if self.enable_legacy_referrals and not _warned_legacy_referrals:
            _warned_legacy_referrals = True
            logger.warning(
                "ENABLE_LEGACY_REFERRALS is deprecated and ignored; set ENABLE_REFERRALS to enable referrals."
            )
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["http://localhost:5173", "http://localhost:3000"]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                parsed = json.loads(text)
                if not isinstance(parsed, list):
                    raise ValueError("cors_origins JSON must be a list of strings")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [part.strip() for part in text.split(",") if part.strip()]
        raise ValueError(f"Unsupported cors_origins type: {type(value)!r}")


# Global settings instance
settings = Settings()
